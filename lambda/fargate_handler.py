"""
Fargate handler for running inference as a standalone task.
This script is invoked when the container runs on ECS Fargate.

Usage: Fargate task passes environment variables:
  Local file:
    - AUDIO_KEY: S3 key of the audio file
    - BUCKET: S3 bucket name
    - TASK_ID: Unique task identifier for output
    - USER_ID: User identifier for WebSocket notifications
    - SOURCE_TYPE: "local" (default)
  
  YouTube:
    - YOUTUBE_URL: YouTube video URL
    - VIDEO_ID: YouTube video ID
    - TASK_ID: Unique task identifier for output
    - USER_ID: User identifier for WebSocket notifications
    - SOURCE_TYPE: "youtube"
    - BUCKET: S3 bucket name for storing output
"""

import os
import sys
import json
import shutil
import boto3
import librosa

from inference import (
    extract_tempo,
    generate_frame_level_attributes,
    predict_notes,
    predict_techniques,
    process_cqt,
)
from create_xml import preprocess_input, process_tied_notes, create_musicxml
import xml.etree.ElementTree as ET
import ast

s3_client = boto3.client("s3")
lambda_client = boto3.client("lambda")

# Configuration (same as handler.py)
CQT_HPARAMS = {
    "down_sampling_rate": 22050,
    "normalize_wave": True,
    "stft_type": "cqt",
    "bins_per_octave": 24,
    "total_n_bins": 192,
    "hop_length": 256,
    "db_scale": False,
    "normalize_cqt": False,
}
SPLIT_UNIT_IN_BARS = 4
SPLIT_HOP_BAR_LEN = 4

# Paths
SCRIPT_DIR = os.path.dirname(__file__)
TECH_MODEL_CHECKPOINT = os.path.join(SCRIPT_DIR, "solo_tech_epoch_099.ckpt")
NOTE_MODEL_CHECKPOINT = os.path.join(SCRIPT_DIR, "solo_trans_epoch_099.ckpt")

WORK_DIR = "/tmp"
DATA_DIR = os.path.join(WORK_DIR, "data")
OUTPUT_DIR = os.path.join(WORK_DIR, "output")
NOTE_PREDICTION_DIR = os.path.join(OUTPUT_DIR, "note_prediction")
PREDICTION_XML_DIR = os.path.join(OUTPUT_DIR, "prediction_xml")


# === Notification Functions ===


def notify_progress(user_id, progress, message):
    """Send progress update to user via WebSocket notification Lambda."""
    if not user_id or user_id == "anonymous":
        print(f"[NOTIFY] Skipping notification (no userId): {message}")
        return
    
    try:
        payload = {
            "userId": user_id,
            "type": "transcription_progress",
            "data": {
                "progress": progress,
                "message": message
            }
        }
        lambda_client.invoke(
            FunctionName="eg-solo-websocket-notification",
            InvocationType="Event",  # Async invocation
            Payload=json.dumps(payload)
        )
        print(f"[NOTIFY] Progress {progress}%: {message}")
    except Exception as e:
        print(f"[NOTIFY ERROR] Failed to send progress notification: {e}")


def notify_complete(user_id, result_url, filename, xml_url=None):
    """Send completion notification to user via WebSocket notification Lambda."""
    if not user_id or user_id == "anonymous":
        print(f"[NOTIFY] Skipping completion notification (no userId)")
        return
    
    try:
        result_data = {
            "resultUrl": result_url,
            "fileName": filename,
            "progress": 100,
            "message": "Generation completed successfully!"
        }
        
        # Add XML download URL if available
        if xml_url:
            result_data["xmlUrl"] = xml_url
        
        payload = {
            "userId": user_id,
            "type": "transcription_complete",
            "data": result_data
        }
        lambda_client.invoke(
            FunctionName="eg-solo-websocket-notification",
            InvocationType="Event",  # Async invocation
            Payload=json.dumps(payload)
        )
        print(f"[NOTIFY] Completion sent: {filename}")
    except Exception as e:
        print(f"[NOTIFY ERROR] Failed to send completion notification: {e}")


def notify_error(user_id, error_message):
    """Send error notification to user via WebSocket notification Lambda."""
    if not user_id or user_id == "anonymous":
        print(f"[NOTIFY] Skipping error notification (no userId): {error_message}")
        return
    
    try:
        payload = {
            "userId": user_id,
            "type": "error",
            "data": {
                "error": error_message,
                "message": error_message
            }
        }
        lambda_client.invoke(
            FunctionName="eg-solo-websocket-notification",
            InvocationType="Event",  # Async invocation
            Payload=json.dumps(payload)
        )
        print(f"[NOTIFY] Error sent: {error_message}")
    except Exception as e:
        print(f"[NOTIFY ERROR] Failed to send error notification: {e}")


def download_youtube_audio(youtube_url: str, output_path: str, user_id: str = None) -> str:
    """
    Download audio from YouTube using multiple strategies.
    Tries different player clients to bypass YouTube bot detection from server IPs.
    
    Returns: Path to the downloaded audio file (MP3 format)
    """
    import yt_dlp
    
    notify_progress(user_id, 15, "Downloading audio from YouTube...")
    
    # Common options shared across all attempts
    base_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
        'no_warnings': False,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
    }
    
    # Strategies to try in order - different player clients that may bypass bot detection
    strategies = [
        {
            'name': 'tv_embedded client',
            'extractor_args': {'youtube': {'player_client': ['tv_embedded']}},
        },
        {
            'name': 'mediaconnect client',
            'extractor_args': {'youtube': {'player_client': ['mediaconnect']}},
        },
        {
            'name': 'android client with skip',
            'extractor_args': {'youtube': {'player_client': ['android'], 'skip': ['webpage']}},
        },
        {
            'name': 'web_creator client',
            'extractor_args': {'youtube': {'player_client': ['web_creator']}},
        },
        {
            'name': 'default (no override)',
            'extractor_args': {},
        },
    ]
    
    last_error = None
    for strategy in strategies:
        print(f"  Attempting download with strategy: {strategy['name']}")
        notify_progress(user_id, 18, f"Trying download method: {strategy['name']}...")
        
        opts = {**base_opts}
        if strategy['extractor_args']:
            opts['extractor_args'] = strategy['extractor_args']
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                video_title = info.get('title', 'unknown')
                print(f"  ✅ Downloaded: {video_title} (strategy: {strategy['name']})")
            
            # yt-dlp adds .mp3 extension
            final_path = f"{output_path}.mp3"
            if os.path.exists(final_path):
                return final_path
            
            # Sometimes the file has the original extension, check for common ones
            for ext in ['.mp3', '.m4a', '.webm', '.opus']:
                candidate = f"{output_path}{ext}"
                if os.path.exists(candidate):
                    # Convert to mp3 if needed
                    if ext != '.mp3':
                        import subprocess
                        mp3_path = f"{output_path}.mp3"
                        subprocess.run(['ffmpeg', '-i', candidate, '-vn', '-acodec', 'libmp3lame', '-q:a', '2', mp3_path], check=True)
                        os.remove(candidate)
                        return mp3_path
                    return candidate
            
            print(f"  ⚠️ Strategy {strategy['name']} completed but file not found")
            last_error = FileNotFoundError(f"Downloaded file not found at {final_path}")
            
        except Exception as e:
            last_error = e
            print(f"  ❌ Strategy {strategy['name']} failed: {str(e)[:200]}")
            continue
    
    # All strategies failed
    error_msg = (
        "Could not download YouTube audio. YouTube is blocking downloads from this server. "
        "Please download the audio manually and upload it as a file instead."
    )
    print(f"ERROR: {error_msg}")
    print(f"Last yt-dlp error: {last_error}")
    notify_error(user_id, error_msg)
    raise Exception(error_msg)


# === Helper Functions ===


def _safe_mkdirs():
    """Create output directories, cleaning up any existing ones."""
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    if os.path.exists(DATA_DIR):
        shutil.rmtree(DATA_DIR)
        
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "cqt"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "frame_level_note_attrib"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "frame_level_full_tech_prediction"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "full_tech_prediction"), exist_ok=True)
    os.makedirs(NOTE_PREDICTION_DIR, exist_ok=True)
    os.makedirs(PREDICTION_XML_DIR, exist_ok=True)


def _upload_results_to_s3(bucket, prefix, track_name):
    """Upload all generated files to S3."""
    uploaded_files = {}
    for root, _, files in os.walk(OUTPUT_DIR):
        for file in files:
            local_path = os.path.join(root, file)
            rel_path = os.path.relpath(local_path, OUTPUT_DIR)
            s3_key = f"{prefix}/{track_name}/{rel_path}"
            
            s3_client.upload_file(local_path, bucket, s3_key)
            uploaded_files[rel_path] = f"s3://{bucket}/{s3_key}"
            print(f"  Uploaded: {s3_key}")
    return uploaded_files


def _generate_musicxml(track_name, output_dir):
    """Generate MusicXML file from the predicted notes."""
    try:
        # Find the concatenated prediction file (without "segment" in filename)
        tech_prediction_dir = os.path.join(output_dir, "full_tech_prediction")
        
        prediction_file = None
        for f in os.listdir(tech_prediction_dir):
            if f.endswith('.tsv') and track_name in f and 'segment' not in f.lower():
                prediction_file = os.path.join(tech_prediction_dir, f)
                break
        
        if not prediction_file:
            print(f"  ⚠️ No concatenated prediction file found for {track_name}")
            return None
        
        print(f"  Reading predictions from: {os.path.basename(prediction_file)}")
        
        # Parse the prediction file
        notes = []
        with open(prediction_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    # Each line is like: [0, 6, 74, 3, 7, 19]
                    note = ast.literal_eval(line)
                    notes.append(note)
        
        print(f"  Loaded {len(notes)} notes")
        
        # Process notes
        preprocessed = preprocess_input(notes)
        output_notes = process_tied_notes(preprocessed)
        print(f"  Processed into {len(output_notes)} output notes")
        
        # Create MusicXML
        tree = create_musicxml(output_notes)
        ET.indent(tree, space="  ", level=0)
        
        # Save to file in prediction_xml directory
        xml_filename = f"{track_name}.xml"
        xml_path = os.path.join(PREDICTION_XML_DIR, xml_filename)
        tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        
        print(f"  ✅ MusicXML saved: prediction_xml/{xml_filename}")
        return xml_filename  # Return filename for S3 key generation
        
    except Exception as e:
        print(f"  ❌ Error generating MusicXML: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_inference(bucket: str, audio_key: str, task_id: str = None, user_id: str = None):
    """Run the full inference pipeline with WebSocket notifications."""
    print(f"=" * 60)
    print(f"Fargate Inference Task")
    print(f"=" * 60)
    print(f"Bucket: {bucket}")
    print(f"Audio Key: {audio_key}")
    print(f"Task ID: {task_id}")
    print(f"User ID: {user_id}")
    print(f"=" * 60)
    
    try:
        # 1. Prepare environment
        print("\n[1/7] Preparing environment...")
        notify_progress(user_id, 10, "Preparing environment...")
        _safe_mkdirs()

        # 2. Download Audio from S3
        print(f"\n[2/7] Downloading audio from S3...")
        notify_progress(user_id, 20, "Downloading audio file...")
        local_audio_path = os.path.join(DATA_DIR, os.path.basename(audio_key))
        try:
            s3_client.download_file(bucket, audio_key, local_audio_path)
            print(f"  Downloaded to: {local_audio_path}")
        except Exception as e:
            error_msg = f"Could not download audio: {e}"
            print(f"  ERROR: {error_msg}")
            notify_error(user_id, error_msg)
            sys.exit(1)
        
        track_name = os.path.splitext(os.path.basename(local_audio_path))[0]
        print(f"  Track name: {track_name}")
        
        # 3. Load audio with librosa
        print(f"\n[3/7] Loading audio with librosa...")
        notify_progress(user_id, 30, "Loading and analyzing audio...")
        audio, original_sr = librosa.load(local_audio_path)
        print(f"  Duration: {len(audio) / original_sr:.2f}s, Sample rate: {original_sr}")
        
        # 4. Extract tempo
        print(f"\n[4/7] Extracting tempo...")
        notify_progress(user_id, 40, "Extracting tempo...")
        tempo = extract_tempo(audio, original_sr)
        print(f"  Tempo: {tempo:.2f} BPM")

        # 5. Run Inference Pipeline
        print(f"\n[5/7] Running inference pipeline...")
        notify_progress(user_id, 50, "Processing audio with AI models...")
        
        # Step 1: Generate CQT segments
        print("  - Generating CQT segments...")
        process_cqt(
            audio=audio,
            tempo=tempo,
            original_sr=original_sr,
            track_name=track_name,
            split_unit_in_bars=SPLIT_UNIT_IN_BARS,
            split_hop_bar_len=SPLIT_HOP_BAR_LEN,
            hparams=CQT_HPARAMS,
            output_dir=OUTPUT_DIR,
        )
        
        # Step 2: Predict Notes
        print("  - Predicting notes...")
        predict_notes(
            audio_file_path=local_audio_path,
            model_path=NOTE_MODEL_CHECKPOINT,
            tempo=tempo,
            output_dir=OUTPUT_DIR,
        )

        # Step 3: Frame Attributes
        print("  - Generating frame-level attributes...")
        generate_frame_level_attributes(
            audio=audio,
            tempo=tempo,
            original_sr=original_sr,
            track_name=track_name,
            split_unit_in_bars=SPLIT_UNIT_IN_BARS,
            split_hop_bar_len=SPLIT_HOP_BAR_LEN,
            hparams=CQT_HPARAMS,
            output_dir=OUTPUT_DIR,
            prediction_dir=NOTE_PREDICTION_DIR,
        )

        # Step 4: Predict Techniques
        print("  - Predicting techniques...")
        predict_techniques(
            audio_file_path=local_audio_path,
            model_path=TECH_MODEL_CHECKPOINT,
            output_dir=OUTPUT_DIR,
        )

        # Step 5: Generate MusicXML
        print("  - Generating MusicXML...")
        notify_progress(user_id, 75, "Converting to MusicXML format...")
        xml_filename = _generate_musicxml(track_name, OUTPUT_DIR)

        # 6. Upload Results to S3
        print(f"\n[6/7] Uploading results to S3...")
        notify_progress(user_id, 85, "Uploading generated files...")
        output_prefix = f"inference_results/{task_id}" if task_id else "inference_results"
        uploaded_files = _upload_results_to_s3(bucket, output_prefix, track_name)

        # 7. Write completion marker
        print(f"\n[7/7] Finalizing results...")
        notify_progress(user_id, 95, "Finalizing results...")
        result = {
            "status": "success",
            "track": track_name,
            "tempo": float(tempo),
            "files": uploaded_files
        }
        
        result_key = f"{output_prefix}/{track_name}/_result.json"
        s3_client.put_object(
            Bucket=bucket,
            Key=result_key,
            Body=json.dumps(result, indent=2),
            ContentType="application/json"
        )
        
        # Generate presigned URL for the result JSON
        result_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': result_key},
            ExpiresIn=3600  # 1 hour
        )
        
        # Generate presigned URL for the XML file if it was created
        xml_url = None
        if xml_filename:
            xml_s3_key = f"{output_prefix}/{track_name}/prediction_xml/{xml_filename}"
            xml_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': xml_s3_key},
                ExpiresIn=3600  # 1 hour
            )
            print(f"  MusicXML download URL generated")
        
        print(f"\n✅ Inference complete! Result: s3://{bucket}/{result_key}")
        
        # Send completion notification with XML URL
        notify_complete(user_id, result_url, track_name, xml_url)
        
        return result
    
    except Exception as e:
        error_msg = f"Inference failed: {str(e)}"
        print(f"\n❌ {error_msg}")
        import traceback
        traceback.print_exc()
        notify_error(user_id, error_msg)
        raise


if __name__ == "__main__":
    # Read configuration from environment variables
    source_type = os.environ.get("SOURCE_TYPE", "local")
    bucket = os.environ.get("BUCKET") or os.environ.get("S3_BUCKET_NAME")
    task_id = os.environ.get("TASK_ID", "default")
    user_id = os.environ.get("USER_ID", "anonymous")
    
    print(f"=" * 60)
    print(f"Fargate Inference Task")
    print(f"=" * 60)
    print(f"Source Type: {source_type}")
    print(f"Task ID: {task_id}")
    print(f"User ID: {user_id}")
    print(f"=" * 60)
    
    if source_type == "local":
        audio_key = os.environ.get("AUDIO_KEY")
        
        if not bucket or not audio_key:
            print("ERROR: Missing required environment variables for local source: BUCKET, AUDIO_KEY")
            print("  BUCKET:", bucket)
            print("  AUDIO_KEY:", audio_key)
            sys.exit(1)
        
        print(f"Audio Key: {audio_key}")
        print(f"Bucket: {bucket}")
        
        try:
            run_inference(bucket, audio_key, task_id, user_id)
        except Exception as e:
            error_msg = f"Inference failed: {str(e)}"
            print(f"\n❌ {error_msg}")
            import traceback
            traceback.print_exc()
            notify_error(user_id, error_msg)
            sys.exit(1)
    
    elif source_type == "youtube":
        youtube_url = os.environ.get("YOUTUBE_URL")
        video_id = os.environ.get("VIDEO_ID", "unknown")
        
        if not youtube_url or not bucket:
            print("ERROR: Missing required environment variables for YouTube source: YOUTUBE_URL, BUCKET")
            print("  YOUTUBE_URL:", youtube_url)
            print("  BUCKET:", bucket)
            sys.exit(1)
        
        print(f"YouTube URL: {youtube_url}")
        print(f"Video ID: {video_id}")
        print(f"Bucket: {bucket}")
        
        try:
            # Download YouTube audio to local temp file
            print("\n[1/2] Downloading audio from YouTube...")
            notify_progress(user_id, 10, "Downloading audio from YouTube...")
            
            # Create data directory if it doesn't exist
            os.makedirs(DATA_DIR, exist_ok=True)
            
            # Download audio (without extension, yt-dlp will add .mp3)
            temp_audio_base = os.path.join(DATA_DIR, f"youtube_{video_id}")
            local_audio_path = download_youtube_audio(youtube_url, temp_audio_base, user_id)
            
            print(f"  Downloaded to: {local_audio_path}")
            
            # Upload to S3 so it can be referenced later
            audio_key = f"youtube/{video_id}.mp3"
            print(f"\n  Uploading to S3: {audio_key}")
            s3_client.upload_file(local_audio_path, bucket, audio_key)
            
            print(f"\n[2/2] Running inference...")
            # Run inference with the downloaded file
            run_inference(bucket, audio_key, task_id, user_id)
            
        except Exception as e:
            error_msg = str(e)
            print(f"\n❌ {error_msg}")
            import traceback
            traceback.print_exc()
            # Only notify if it's not already a clean user-facing message
            # (download_youtube_audio already sends notify_error for known failures)
            if "Please download the audio manually" not in error_msg:
                notify_error(user_id, f"YouTube transcription failed: {error_msg}")
            sys.exit(1)
    
    else:
        print(f"ERROR: Unknown source type: {source_type}")
        sys.exit(1)
