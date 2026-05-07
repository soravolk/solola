#!/usr/bin/env python3
"""
Test script: audio file → full-tech prediction TSV (input for XML creation).

Usage:
    python test_predict.py /path/to/audio.mp3
    python test_predict.py /path/to/audio.wav /path/to/output_dir
"""

import os
import sys
import subprocess
import librosa

from inference import (
    extract_tempo,
    generate_frame_level_attributes,
    predict_notes,
    predict_techniques,
    process_cqt,
)

# ── Config (mirrors fargate_handler.py) ──────────────────────────────────────
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TECH_MODEL_CHECKPOINT = os.path.join(SCRIPT_DIR, "solo_tech_epoch_099.ckpt")
NOTE_MODEL_CHECKPOINT = os.path.join(SCRIPT_DIR, "solo_trans_epoch_099.ckpt")

# ── CLI args ─────────────────────────────────────────────────────────────────
if len(sys.argv) < 2:
    print("Usage: python test_predict.py <audio_file> [output_dir] [--label-dir <dir>]")
    sys.exit(1)

audio_path = os.path.abspath(sys.argv[1])
track_name = os.path.splitext(os.path.basename(audio_path))[0]

# Parse optional positional output_dir and --label-dir flag
remaining = sys.argv[2:]
label_dir = None
output_dir_arg = None

i = 0
while i < len(remaining):
    if remaining[i] == "--label-dir" and i + 1 < len(remaining):
        label_dir = os.path.abspath(remaining[i + 1])
        i += 2
    elif not remaining[i].startswith("--") and output_dir_arg is None:
        output_dir_arg = os.path.abspath(remaining[i])
        i += 1
    else:
        i += 1

output_dir = output_dir_arg if output_dir_arg else os.path.join(SCRIPT_DIR, "output")

note_prediction_dir = os.path.join(output_dir, "note_prediction")

os.makedirs(os.path.join(output_dir, "cqt"), exist_ok=True)
os.makedirs(os.path.join(output_dir, "frame_level_note_attrib"), exist_ok=True)
os.makedirs(os.path.join(output_dir, "frame_level_full_tech_prediction"), exist_ok=True)
os.makedirs(os.path.join(output_dir, "full_tech_prediction"), exist_ok=True)
os.makedirs(note_prediction_dir, exist_ok=True)

print("=" * 60)
print("PREDICT: audio → full-tech prediction TSV")
print("=" * 60)
print(f"  Input : {audio_path}")
print(f"  Track : {track_name}")
print(f"  Output: {output_dir}")
print("=" * 60)

# ── Convert to WAV if needed ──────────────────────────────────────────────────
wav_path = os.path.join(output_dir, f"{track_name}.wav")
if not audio_path.endswith(".wav"):
    print("\n[1/5] Converting to WAV...")
    subprocess.run(
        ["ffmpeg", "-y", "-i", audio_path, "-ar", "22050", "-ac", "1", wav_path],
        check=True, capture_output=True,
    )
    local_audio_path = wav_path
else:
    local_audio_path = audio_path

# ── Load audio ────────────────────────────────────────────────────────────────
print("\n[1/5] Loading audio...")
audio, original_sr = librosa.load(local_audio_path, sr=None)
print(f"  Duration: {len(audio) / original_sr:.2f}s  SR: {original_sr}")

# ── Extract tempo ─────────────────────────────────────────────────────────────
print("\n[2/5] Extracting tempo...")
if label_dir:
    label_filename = os.path.join(label_dir, f"{track_name}.tsv")
    with open(label_filename, "r") as f:
        lines = [line.split() for line in f.read().split("\n")][:-1]
    label = [list(map(int, line)) for line in lines]
    song_dur = len(audio) / original_sr
    tempo = 60 * (label[-1][0] + ((label[-1][1] + label[-1][2]) / 48)) * 4 / song_dur
    print(f"  Tempo (from label): {tempo:.2f} BPM")
else:
    tempo = extract_tempo(audio, original_sr)
    print(f"  Tempo (librosa): {tempo:.2f} BPM")

# ── CQT segments ─────────────────────────────────────────────────────────────
print("\n[3/5] Generating CQT segments...")
process_cqt(
    audio=audio,
    tempo=tempo,
    original_sr=original_sr,
    track_name=track_name,
    split_unit_in_bars=SPLIT_UNIT_IN_BARS,
    split_hop_bar_len=SPLIT_HOP_BAR_LEN,
    hparams=CQT_HPARAMS,
    output_dir=output_dir,
)
print("  ✅ CQT done")

# ── Predict notes ─────────────────────────────────────────────────────────────
print("\n[4/5] Predicting notes...")
predict_notes(
    audio_file_path=local_audio_path,
    model_path=NOTE_MODEL_CHECKPOINT,
    tempo=tempo,
    output_dir=output_dir,
)
print("  ✅ Note prediction done")

# ── Frame-level attributes ────────────────────────────────────────────────────
print("  Generating frame-level attributes...")
generate_frame_level_attributes(
    audio=audio,
    tempo=tempo,
    original_sr=original_sr,
    track_name=track_name,
    split_unit_in_bars=SPLIT_UNIT_IN_BARS,
    split_hop_bar_len=SPLIT_HOP_BAR_LEN,
    hparams=CQT_HPARAMS,
    output_dir=output_dir,
    prediction_dir=note_prediction_dir,
)
print("  ✅ Frame attributes done")

# ── Predict techniques ────────────────────────────────────────────────────────
print("\n[5/5] Predicting techniques...")
predict_techniques(
    audio_file_path=local_audio_path,
    model_path=TECH_MODEL_CHECKPOINT,
    output_dir=output_dir,
)
print("  ✅ Technique prediction done")

# ── Report output TSV ─────────────────────────────────────────────────────────
tech_dir = os.path.join(output_dir, "full_tech_prediction")
tsv_files = [f for f in os.listdir(tech_dir) if f.endswith(".tsv") and track_name in f and "segment" not in f.lower()]

print("\n" + "=" * 60)
print("✅ DONE")
if tsv_files:
    tsv_path = os.path.join(tech_dir, tsv_files[0])
    print(f"  Prediction TSV: {tsv_path}")
    print(f"\nNext step — convert to XML:")
    print(f"  python test_create_xml.py \"{tsv_path}\"")
else:
    print(f"  Prediction TSVs written to: {tech_dir}")
print("=" * 60)
