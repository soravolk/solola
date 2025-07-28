import torch
import numpy as np
import os
import librosa
from src.models.hybrid_ctc_lit_module import HybridCTCLitModule

def process_cqt(
    audio,
    tempo,
    original_sr,
    track_name,
    split_unit_in_bars,
    split_hop_bar_len,
    hparams,
    output_dir,
):
    len_in_sec = librosa.get_duration(y=audio, sr=original_sr)
    len_in_bars = int(round((tempo * len_in_sec) / (4 * 60)))
    n_units = int(
        round((tempo * len_in_sec) / (split_hop_bar_len * split_unit_in_bars * 60))
        - ((split_unit_in_bars - split_hop_bar_len) // split_hop_bar_len)
    )
    audio = audio.astype(float)
    audio = librosa.resample(
        audio, orig_sr=original_sr, target_sr=hparams["down_sampling_rate"]
    )
    if hparams["normalize_wave"]:
        audio = librosa.util.normalize(audio)
    cqt = librosa.cqt(
        audio,
        hop_length=hparams["hop_length"],
        sr=hparams["down_sampling_rate"],
        n_bins=hparams["total_n_bins"],
        bins_per_octave=hparams["bins_per_octave"],
    )
    if hparams["db_scale"]:
        cqt = librosa.amplitude_to_db(np.abs(cqt))
    if hparams["normalize_cqt"]:
        cqt = z_score_normalize(cqt)
    cqt = np.abs(cqt).T

    for unit_n in range(n_units):
        cqt_filename = os.path.join(
            output_dir, "cqt", f"{track_name}_0{unit_n}.npy"
        )
        st = int(round(len(cqt) * unit_n * split_hop_bar_len / len_in_bars))
        end = (
            int(
                round(len(cqt))
                * ((unit_n * split_hop_bar_len + split_unit_in_bars) / len_in_bars)
            )
            if int(
                round(len(cqt))
                * ((unit_n * split_hop_bar_len + split_unit_in_bars) / len_in_bars)
            )
            <= len(cqt)
            else len(cqt)
        )
        np.save(cqt_filename, cqt[st:end])

def extract_tempo(
    audio,
    sr
):
    onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
    tempo, _ = librosa.beat.beat_track(y=audio, sr=sr, onset_envelope=onset_env)
    return float(tempo)

def z_score_normalize(x: any) -> any:
    mean, std = x.mean(), x.std()
    return (x-mean)/std

def preprocess_audio_for_note_inference(audio_file_path: str):
    cqt_hparams = {
            "down_sampling_rate": 22050,
            "normalize_wave": True,
            "stft_type": "cqt",
            "bins_per_octave": 24,
            "total_n_bins": 192,
            "hop_length": 256,
            "db_scale": False,
            "normalize_cqt": False,
        }
    split_unit_in_bars = 4
    split_hop_bar_len = 1
    output_dir = "."

    track_name = os.path.split(audio_file_path)[1][:-4]
    audio, original_sr = librosa.load(audio_file_path)
    print(f"audio: {audio}, original_sr: {original_sr}")

    tempo = extract_tempo(
        audio,
        original_sr,
    )
 
    process_cqt(audio, tempo, original_sr, track_name, split_unit_in_bars,
        split_hop_bar_len,
        cqt_hparams,
        output_dir,)

    return tempo

def predict_notes(audio_file_path: str, model_path: str) -> dict:
    """Run note prediction over all saved CQT segment files for the given audio.

    Steps:
      1. Ensure/refresh CQT segments via preprocessing (also detects tempo)
      2. Load each segment from ./cqt directory matching track name
      3. Pad & batch all segments
      4. Run a single model inference
      5. Convert tokens to tablature per segment & concatenate

    Returns dict with keys: segments, concatenated, tempo, segment_files
    """
    # Load model
    model = HybridCTCLitModule.load_from_checkpoint(model_path, prediction_dir="./prediction/", strict=False)
    model.eval()

    tempo = preprocess_audio_for_note_inference(audio_file_path)

    track_name = os.path.split(audio_file_path)[1][:-4]
    cqt_dir = os.path.join(".", "cqt")
    if not os.path.isdir(cqt_dir):
        raise FileNotFoundError(f"CQT directory not found: {cqt_dir}")

    # Gather segment files
    segment_files = [
        os.path.join(cqt_dir, f)
        for f in sorted(os.listdir(cqt_dir))
        if f.startswith(track_name + "_") and f.endswith(".npy")
    ]
    if not segment_files:
        raise RuntimeError(f"No CQT segments found for track {track_name} in {cqt_dir}")

    # Load segments
    cqt_segments = [np.load(f) for f in segment_files]
    feat_dim = cqt_segments[0].shape[1]
    for idx, seg in enumerate(cqt_segments):
        if seg.shape[1] != feat_dim:
            raise ValueError(
                f"Segment feature dim mismatch in {segment_files[idx]}: {seg.shape[1]} != {feat_dim}"
            )

    lengths = [seg.shape[0] for seg in cqt_segments]
    max_len = max(lengths)

    batch = torch.zeros((len(cqt_segments), max_len, feat_dim), dtype=torch.float32)
    cqt_lens = torch.tensor(lengths, dtype=torch.long)
    for i, seg in enumerate(cqt_segments):
        batch[i, : seg.shape[0]] = torch.from_numpy(seg).float()

    tempos = torch.full((len(cqt_segments),), float(tempo), dtype=torch.float32)

    with torch.no_grad():
        _, tr_preds_tokens = model.model_inference(batch, cqt_lens, tempos)

    segment_tabs = []
    for i in range(len(cqt_segments)):
        tab = model.tokenizer.tokens_to_tab([tr_preds_tokens[i]])
        tab = [[int(element) for element in row] for row in tab]
        segment_tabs.append(tab)
        # Save per-segment prediction
        seg_pred_path = os.path.join(model.prediction_dir, f"note_prediction_segment_{i:02d}.npy")
        np.save(seg_pred_path, np.array(tab, dtype=int))

    concatenated = [row for seg in segment_tabs for row in seg]

    os.makedirs(model.prediction_dir, exist_ok=True)
    prediction_path = os.path.join(model.prediction_dir, "note_prediction.npy")
    np.save(prediction_path, np.array(concatenated, dtype=int))

    return {
        "segments": segment_tabs,
        "concatenated": concatenated,
        "tempo": float(tempo),
        "segment_files": segment_files,
    }


if __name__ == "__main__":
    audio_file = "./data/20_1.wav"
    note_model_checkpoint = "./solo_trans_epoch_099.ckpt" 

    note_results = predict_notes(audio_file, note_model_checkpoint)