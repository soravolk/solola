import os
import json
import shutil
import boto3
import librosa
from typing import Any, Dict

from inference import (
    extract_tempo,
    generate_frame_level_attributes,
    predict_notes,
    predict_techniques,
    process_cqt,
)

s3_client = boto3.client("s3")

# Default config for CQT and segmentation
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

# Model checkpoints relative to the lambda folder
LAMBDA_ROOT = os.path.dirname(__file__)
TECH_MODEL_CHECKPOINT = os.path.join(LAMBDA_ROOT, "solo_tech_epoch_099.ckpt")
NOTE_MODEL_CHECKPOINT = os.path.join(LAMBDA_ROOT, "solo_trans_epoch_099.ckpt")

# !!! CRITICAL CHANGE: Write to /tmp (The only writable path in Lambda) !!!
WORK_DIR = "/tmp"
DATA_DIR = os.path.join(WORK_DIR, "data")
OUTPUT_DIR = os.path.join(WORK_DIR, "output")
NOTE_PREDICTION_DIR = os.path.join(OUTPUT_DIR, "note_prediction")


def _safe_mkdirs() -> None:
    # Clean up /tmp from previous invocations (Lambda containers are reused)
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
    """Uploads all generated files in OUTPUT_DIR to S3."""
    uploaded_files = {}
    for root, _, files in os.walk(OUTPUT_DIR):
        for file in files:
            local_path = os.path.join(root, file)
            # Create S3 key: prefix/track_name/subdir/filename
            rel_path = os.path.relpath(local_path, OUTPUT_DIR)
            s3_key = f"{prefix}/{track_name}/{rel_path}"
            
            s3_client.upload_file(local_path, bucket, s3_key)
            
            # Generate a presigned URL (valid for 1 hour)
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': s3_key},
                ExpiresIn=3600
            )
            uploaded_files[rel_path] = url
    return uploaded_files


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda Handler.
    Event: { "audio_key": "uploads/song.wav", "bucket": "my-bucket" }
    """
    bucket = event.get("bucket")
    audio_key = event.get("audio_key")
    
    if not bucket or not audio_key:
        return {"statusCode": 400, "body": "Error: Missing 'bucket' or 'audio_key'"}

    # 1. Prepare environment
    _safe_mkdirs()

    # 2. Download Audio from S3 to /tmp
    print(f"Downloading {audio_key} from {bucket}...")
    local_audio_path = os.path.join(DATA_DIR, os.path.basename(audio_key))
    try:
        s3_client.download_file(bucket, audio_key, local_audio_path)
    except Exception as e:
        return {"statusCode": 404, "body": f"Could not download audio: {str(e)}"}
    
    track_name = os.path.splitext(os.path.basename(local_audio_path))[0]
    audio, original_sr = librosa.load(local_audio_path)
    
    # 3. Calculate Tempo (On-the-fly)
    print("Extracting tempo...")
    tempo = extract_tempo(audio, original_sr)

    # 4. Run Inference Pipeline
    print("Running inference...")
    
    # Step 1: Generate CQT segments (required before predict_notes)
    print("Generating CQT segments...")
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
    print("Predicting notes...")
    predict_notes(
        audio_file_path=local_audio_path,
        model_path=NOTE_MODEL_CHECKPOINT,
        tempo=tempo,
        output_dir=OUTPUT_DIR,
    )

    # Step 3: Frame Attributes
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
    predict_techniques(
        audio_file_path=local_audio_path,
        model_path=TECH_MODEL_CHECKPOINT,
        output_dir=OUTPUT_DIR,
    )

    # 5. Upload Results to S3
    print("Uploading results...")
    output_prefix = "inference_results"
    urls = _upload_results_to_s3(bucket, output_prefix, track_name)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "success",
            "track": track_name,
            "tempo": float(tempo),
            "results": urls
        })
    }
