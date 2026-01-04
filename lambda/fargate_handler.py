"""
Fargate handler for running inference as a standalone task.
This script is invoked when the container runs on ECS Fargate.

Usage: Fargate task passes environment variables:
  - AUDIO_KEY: S3 key of the audio file
  - BUCKET: S3 bucket name
  - TASK_ID: Unique task identifier for output
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

s3_client = boto3.client("s3")

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
SPLIT_HOP_BAR_LEN = 1

# Paths
SCRIPT_DIR = os.path.dirname(__file__)
TECH_MODEL_CHECKPOINT = os.path.join(SCRIPT_DIR, "solo_tech_epoch_099.ckpt")
NOTE_MODEL_CHECKPOINT = os.path.join(SCRIPT_DIR, "solo_trans_epoch_099.ckpt")

WORK_DIR = "/tmp"
DATA_DIR = os.path.join(WORK_DIR, "data")
OUTPUT_DIR = os.path.join(WORK_DIR, "output")
NOTE_PREDICTION_DIR = os.path.join(OUTPUT_DIR, "note_prediction")


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


def run_inference(bucket: str, audio_key: str, task_id: str = None):
    """Run the full inference pipeline."""
    print(f"=" * 60)
    print(f"Fargate Inference Task")
    print(f"=" * 60)
    print(f"Bucket: {bucket}")
    print(f"Audio Key: {audio_key}")
    print(f"Task ID: {task_id}")
    print(f"=" * 60)
    
    # 1. Prepare environment
    print("\n[1/6] Preparing environment...")
    _safe_mkdirs()

    # 2. Download Audio from S3
    print(f"\n[2/6] Downloading audio from S3...")
    local_audio_path = os.path.join(DATA_DIR, os.path.basename(audio_key))
    try:
        s3_client.download_file(bucket, audio_key, local_audio_path)
        print(f"  Downloaded to: {local_audio_path}")
    except Exception as e:
        print(f"  ERROR: Could not download audio: {e}")
        sys.exit(1)
    
    track_name = os.path.splitext(os.path.basename(local_audio_path))[0]
    print(f"  Track name: {track_name}")
    
    print(f"\n[3/6] Loading audio with librosa...")
    audio, original_sr = librosa.load(local_audio_path)
    print(f"  Duration: {len(audio) / original_sr:.2f}s, Sample rate: {original_sr}")
    
    # 3. Extract tempo
    print(f"\n[4/6] Extracting tempo...")
    tempo = extract_tempo(audio, original_sr)
    print(f"  Tempo: {tempo:.2f} BPM")

    # 4. Run Inference Pipeline
    print(f"\n[5/6] Running inference pipeline...")
    
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

    # 5. Upload Results to S3
    print(f"\n[6/6] Uploading results to S3...")
    output_prefix = f"inference_results/{task_id}" if task_id else "inference_results"
    uploaded_files = _upload_results_to_s3(bucket, output_prefix, track_name)

    # Write completion marker
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
    print(f"\n✅ Inference complete! Result: s3://{bucket}/{result_key}")
    
    return result


if __name__ == "__main__":
    # Read configuration from environment variables
    bucket = os.environ.get("BUCKET") or os.environ.get("S3_BUCKET_NAME")
    audio_key = os.environ.get("AUDIO_KEY")
    task_id = os.environ.get("TASK_ID", "default")
    
    if not bucket or not audio_key:
        print("ERROR: Missing required environment variables: BUCKET, AUDIO_KEY")
        print("  BUCKET:", bucket)
        print("  AUDIO_KEY:", audio_key)
        sys.exit(1)
    
    try:
        run_inference(bucket, audio_key, task_id)
    except Exception as e:
        print(f"\n❌ Inference failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
