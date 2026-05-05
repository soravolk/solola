import torch
import numpy as np
import os
from typing import Tuple, List, Optional
import librosa
from src.models.hybrid_ctc_lit_module import HybridCTCLitModule
from src.models.cnn_lit_module import CNNLitModule
from scipy.spatial.distance import cdist


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
    """Generate CQT segments and save segment metadata.
    
    This function generates CQT segments and saves metadata for later use by
    generate_frame_level_attributes().
    
    Args:
        audio: Audio signal array
        tempo: Detected tempo (BPM)
        original_sr: Original sample rate
        track_name: Name of the track (without extension)
        split_unit_in_bars: Number of bars per segment
        split_hop_bar_len: Hop length in bars
        hparams: CQT hyperparameters dict
        output_dir: Output directory for CQT segments
        
    Returns:
        Number of segments generated
    """
    len_in_sec = librosa.get_duration(y=audio, sr=original_sr)
    len_in_bars = int(round((tempo * len_in_sec) / (4 * 60)))
    n_units = int(
        round((tempo * len_in_sec) / (split_hop_bar_len * split_unit_in_bars * 60))
        - ((split_unit_in_bars - split_hop_bar_len) // split_hop_bar_len)
    )
    
    # Process audio
    audio = audio.astype(float)
    audio = librosa.resample(
        audio, orig_sr=original_sr, target_sr=hparams["down_sampling_rate"]
    )
    if hparams["normalize_wave"]:
        audio = librosa.util.normalize(audio)
    
    # Compute CQT
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
    
    os.makedirs(os.path.join(output_dir, "cqt"), exist_ok=True)

    # Store segment metadata for later use by generate_frame_level_attributes
    segment_metadata = []
    
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
        
        cqt_segment = cqt[st:end]
        np.save(cqt_filename, cqt_segment)
        
        # Save segment metadata (start, end indices for onset envelope alignment)
        segment_metadata.append({
            'unit_n': unit_n,
            'st': st,
            'end': end,
            'length': len(cqt_segment)
        })
    
    # Save metadata for later use by generate_frame_level_attributes
    metadata_filename = os.path.join(output_dir, "cqt", f"{track_name}_segments.npy")
    np.save(metadata_filename, segment_metadata)
    
    return n_units

def generate_frame_level_attributes(
    audio,
    tempo,
    original_sr,
    track_name,
    split_unit_in_bars,
    split_hop_bar_len,
    hparams,
    output_dir,
    prediction_dir,
):
    """Generate frame-level note attributes using existing CQT segments and note predictions.
    
    This is a lightweight function that only generates frame-level attributes without
    recomputing CQT. It loads segment metadata to avoid recalculating boundaries.
    
    Args:
        audio: Audio signal array
        tempo: Detected tempo (BPM)
        original_sr: Original sample rate
        track_name: Name of the track (without extension)
        split_unit_in_bars: Number of bars per segment (unused, kept for API compatibility)
        split_hop_bar_len: Hop length in bars (unused, kept for API compatibility)
        hparams: CQT hyperparameters dict
        output_dir: Output directory for frame-level attributes
        prediction_dir: Directory containing note predictions
        
    Returns:
        Number of segments processed
    """
    # Load segment metadata saved by process_cqt
    metadata_filename = os.path.join(output_dir, "cqt", f"{track_name}_segments.npy")
    if not os.path.exists(metadata_filename):
        raise FileNotFoundError(
            f"Segment metadata not found: {metadata_filename}. "
            f"Please run process_cqt first to generate CQT segments and metadata."
        )
    
    segment_metadata = np.load(metadata_filename, allow_pickle=True)
    
    # Process audio for onset detection only
    audio = audio.astype(float)
    audio = librosa.resample(
        audio, orig_sr=original_sr, target_sr=hparams["down_sampling_rate"]
    )
    if hparams["normalize_wave"]:
        audio = librosa.util.normalize(audio)
    
    # Calculate onset envelope for DTW alignment
    onset_env = librosa.onset.onset_strength(
        y=audio,
        sr=hparams["down_sampling_rate"],
        hop_length=hparams["hop_length"],
    )
    
    os.makedirs(os.path.join(output_dir, "frame_level_note_attrib"), exist_ok=True)
    
    # Use stored metadata instead of recalculating
    for seg_info in segment_metadata:
        unit_n = seg_info['unit_n']
        st = seg_info['st']
        end = seg_info['end']
        T = seg_info['length']
        
        cqt_filename = os.path.join(
            output_dir, "cqt", f"{track_name}_0{unit_n}.npy"
        )
        frame_level_note_attrib_filename = os.path.join(
            output_dir, "frame_level_note_attrib", f"{track_name}_0{unit_n}.npy"
        )
        
        # Verify CQT file exists (should always be true if metadata exists)
        if not os.path.exists(cqt_filename):
            print(f"Warning: CQT file not found: {cqt_filename}. Skipping segment {unit_n}.")
            continue

        note_attrib_path = os.path.join(prediction_dir, f"{track_name}_note_prediction_segment_{unit_n:02d}.npy")
        if not os.path.exists(note_attrib_path):
            print(f"Warning: Note prediction file not found: {note_attrib_path}. Skipping segment {unit_n}.")
            continue
        
        raw_attrs = np.load(note_attrib_path)
        if raw_attrs.ndim == 1:
            raw_attrs = raw_attrs.reshape(-1, 1)
        
        # Check if we have onset information (column 1)
        has_onset = raw_attrs.shape[1] > 1 and np.any(raw_attrs[:, 1] == 1)
        
        if has_onset:
            # Use DTW alignment with onset information
            tatum_len = raw_attrs.shape[0]
            onset_tatum = [i for i in range(tatum_len) if raw_attrs[i, 1] == 1]
            if len(onset_tatum) == 0:
                onset_tatum = list(range(tatum_len))
            
            tatum_frames = [round(t * T / tatum_len) for t in onset_tatum]
            tatum_frames = np.clip(np.array(tatum_frames, dtype=int), 0, max(0, T - 1))
            
            # Hybrid cost matrix using position and onset strength
            cost_matrix = cdist(tatum_frames[:, None], np.arange(T)[:, None], metric='euclidean')
            onset_segment = onset_env[st:end]
            onset_cost_matrix = cdist(onset_segment[tatum_frames][:, None], onset_segment[:][:, None], metric='euclidean')
            alpha = 0.5
            hybrid_cost = alpha * cost_matrix + (1 - alpha) * onset_cost_matrix
            _, wp = librosa.sequence.dtw(C=hybrid_cost)
            wp = np.flip(wp, axis=0)
            
            # Build frame-level attributes from DTW path
            frame_level_tech = np.zeros((T, 3), dtype=float)
            filled = np.zeros((T,), dtype=bool)
            for tech_idx, frame_idx in wp:
                vals = raw_attrs[onset_tatum[tech_idx]]
                if vals.shape[0] >= 3:
                    vals = vals[-3:]
                else:
                    vals = np.zeros(3)
                frame_level_tech[frame_idx] = vals
                filled[frame_idx] = True
            
            # Forward-fill unfilled frames
            last = np.zeros(3)
            for i in range(T):
                if filled[i]:
                    last = frame_level_tech[i]
                else:
                    frame_level_tech[i] = last
        else:
            # No onset info: naive upsampling
            last3 = raw_attrs[:, -3:] if raw_attrs.shape[1] >= 3 else np.zeros((raw_attrs.shape[0], 3))
            idx = np.linspace(0, last3.shape[0] - 1, T)
            idx = np.round(idx).astype(int)
            frame_level_tech = last3[idx]
        
        np.save(frame_level_note_attrib_filename, frame_level_tech)
    
    return len(segment_metadata)

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

def preprocess_audio_for_tech_inference(cqt_file_path: str, frame_level_attrib_path: str, note_attrib_path: str) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Prepare inputs for technique inference from preprocessed CQT and frame-level attributes.

    Args:
        cqt_file_path: Path to the CQT .npy file (frames x features).
        frame_level_attrib_path: Path to frame-level attribute file (.npy) generated by generate_frame_level_attributes.
        note_attrib_path: Path to note-level attribute file (.npy) from note prediction.

    Returns:
        Tuple of (cqt_tensor [T x F], note_attrib_tensor [N x D or T x D],
        frame_level_note_attrib_tensor [T x D]).
    """
    # Load precomputed CQT (frames x features)
    if not str(cqt_file_path).lower().endswith(".npy"):
        raise ValueError("preprocess_audio_for_tech_inference expects a .npy CQT file path")
    cqt = np.load(cqt_file_path)
    if cqt.ndim != 2:
        raise ValueError(f"CQT file must be 2D (frames x features), got shape {cqt.shape}")
    cqt_features = cqt

    T = len(cqt_features)
    
    # Load frame-level attributes (generated by generate_frame_level_attributes)
    frame_level_tech = np.load(frame_level_attrib_path)
    
    # Load note-level attributes from note prediction
    raw_attrs = np.load(note_attrib_path)
    if raw_attrs.ndim == 1:
        raw_attrs = raw_attrs.reshape(-1, 1)

    # Prepare note attributes tensor (pad or truncate to 5 columns)
    note_attributes = raw_attrs
    if note_attributes.shape[1] < 5:
        pad = np.zeros((note_attributes.shape[0], 5 - note_attributes.shape[1]))
        note_attributes = np.concatenate([note_attributes, pad], axis=1)
    elif note_attributes.shape[1] > 5:
        note_attributes = note_attributes[:, :5]

    cqt_tensor = torch.from_numpy(cqt_features).float()
    note_attrib_tensor = torch.from_numpy(note_attributes).long()
    frame_level_tensor = torch.from_numpy(frame_level_tech).float()

    return (cqt_tensor, note_attrib_tensor, frame_level_tensor)

def predict_notes(audio_file_path: str, model_path: str, tempo: float, output_dir: str) -> dict:
    """Run note prediction over all saved CQT segment files for the given audio.

    Steps:
      1. Load CQT segments from ./cqt directory (must be pre-generated)
      2. Pad & batch all segments
      3. Run a single model inference
      4. Convert tokens to tablature per segment & concatenate

    Args:
        audio_file_path: Path to the audio file (used to derive track name)
        model_path: Path to the note prediction model checkpoint
        tempo: Pre-detected tempo of the audio

    Returns dict with keys: segments, concatenated, tempo, segment_files
    """
    # Load model
    prediction_path = os.path.join(output_dir, "note_prediction")
    model = HybridCTCLitModule.load_from_checkpoint(model_path, prediction_dir=prediction_path, strict=False)
    model.eval()

    track_name = os.path.split(audio_file_path)[1][:-4]
    cqt_dir = os.path.join(output_dir, "cqt")
    if not os.path.isdir(cqt_dir):
        raise FileNotFoundError(f"CQT directory not found: {cqt_dir}")

    # Gather segment files (exclude metadata file)
    segment_files = [
        os.path.join(cqt_dir, f)
        for f in sorted(os.listdir(cqt_dir))
        if f.startswith(track_name + "_") and f.endswith(".npy") and not f.endswith("_segments.npy")
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
        tr_preds_tokens, _ = model.model_inference(batch, cqt_lens, tempos)

    segment_tabs = []
    for i in range(len(cqt_segments)):
        tab = model.tokenizer.tokens_to_tab([tr_preds_tokens[i]])
        tab = [[int(element) for element in row] for row in tab]
        segment_tabs.append(tab)
        # Save per-segment prediction
        seg_pred_path = os.path.join(model.prediction_dir, f"{track_name}_note_prediction_segment_{i:02d}.npy")
        np.save(seg_pred_path, np.array(tab, dtype=int))

    concatenated = [row for seg in segment_tabs for row in seg]

    os.makedirs(model.prediction_dir, exist_ok=True)
    prediction_path = os.path.join(model.prediction_dir, "note_prediction.npy")
    np.save(prediction_path, np.array(concatenated, dtype=int))

    # Save simple manifest for downstream usage
    try:
        import json
        manifest = {
            "audio_file": audio_file_path,
            "tempo": float(tempo),
            "segments": [
                {
                    "index": i,
                    "cqt_file": segment_files[i],
                    "prediction_file": os.path.join(
                        model.prediction_dir, f"{track_name}_note_prediction_segment_{i:02d}.npy"
                    ),
                    "frames": lengths[i],
                }
                for i in range(len(segment_files))
            ],
            "concatenated_prediction": prediction_path,
        }
        with open(os.path.join(model.prediction_dir, "note_prediction_manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        # Non-fatal; continue even if manifest write fails
        pass

    return {
        "segments": segment_tabs,
        "concatenated": concatenated,
        "tempo": float(tempo),
        "segment_files": segment_files,
    }

def predict_techniques(audio_file_path: str, model_path: str, output_dir: str) -> dict:
    """Predict techniques using stored per-segment note predictions.

    Steps:
      1. Ensure CQT segments exist.
      2. Load CQT segment files for track.
      3. Load per-segment note predictions from ./prediction.
      4. Upsample note attributes to frame level.
      5. Batch + infer techniques.
      6. Convert to note-level and save aggregate outputs.
    """
    # Load model
    model = CNNLitModule.load_from_checkpoint(model_path, strict=False)
    model.eval()

    # Small helper to write rows (scalars or lists) as TSV
    def _write_tsv(path: str, rows) -> None:
        with open(path, 'w') as f:
            for line in rows:
                f.write(f"{line}\n")
        f.close()

    # Determine all segment files produced by note prediction
    track_name = os.path.splitext(os.path.basename(audio_file_path))[0]
    cqt_dir = os.path.join(output_dir, "cqt")
    pred_dir = os.path.join(output_dir, "note_prediction")
    tech_prediction_dir = os.path.join(output_dir, "full_tech_prediction")
    frame_level_dir = os.path.join(output_dir, "frame_level_note_attrib")
    if not os.path.isdir(cqt_dir):
        raise FileNotFoundError(f"CQT directory not found: {cqt_dir}")

    segment_files = [
        os.path.join(cqt_dir, f)
        for f in sorted(os.listdir(cqt_dir))
        if f.startswith(track_name + "_") and f.endswith(".npy") and not f.endswith("_segments.npy")
    ]
    if not segment_files:
        raise RuntimeError(f"No CQT segments found for track {track_name} in {cqt_dir}")

    # Load and collect per-segment tensors
    cqt_list: list[torch.Tensor] = []
    fl_attr_list: list[torch.Tensor] = []
    note_attr_list: list[torch.Tensor] = []
    cqt_lens_list: list[int] = []
    note_lens_list: list[int] = []

    feat_dim = None
    for i, cqt_seg_path in enumerate(segment_files):
        # Get segment index from filename
        seg_name = os.path.basename(cqt_seg_path)[:-4]  # Remove .npy

        note_attr_path = os.path.join(pred_dir, f"{track_name}_note_prediction_segment_{i:02d}.npy")
        frame_level_path = os.path.join(frame_level_dir, f"{seg_name}.npy")
            
        cqt, note_attrib, frame_level_note_attrib = preprocess_audio_for_tech_inference(
            cqt_seg_path, frame_level_path, note_attr_path
        )

        if feat_dim is None:
            feat_dim = cqt.shape[1]
        elif cqt.shape[1] != feat_dim:
            raise ValueError(f"Segment feature dim mismatch in {cqt_seg_path}: {cqt.shape[1]} != {feat_dim}")

        cqt_list.append(cqt)
        fl_attr_list.append(frame_level_note_attrib)
        note_attr_list.append(note_attrib)
        cqt_lens_list.append(cqt.shape[0])
        note_lens_list.append(note_attrib.shape[0])

    batch_size = len(cqt_list)
    cqt_max_len = max(cqt_lens_list)
    note_max_len = max(note_lens_list) if note_lens_list else 0

    padded_cqt = torch.zeros((batch_size, cqt_max_len, feat_dim))
    cqt_lens = torch.tensor(cqt_lens_list, dtype=torch.long)
    frame_level_note_attribs = torch.zeros((batch_size, cqt_max_len, fl_attr_list[0].shape[1]))
    note_attribs = torch.zeros((batch_size, note_max_len, note_attr_list[0].shape[1]))

    for i in range(batch_size):
        T_i = cqt_list[i].shape[0]
        N_i = note_attr_list[i].shape[0]
        padded_cqt[i, :T_i] = cqt_list[i]
        frame_level_note_attribs[i, :T_i] = fl_attr_list[i]
        note_attribs[i, :N_i] = note_attr_list[i]
    
    _, _, final_tech_preds, frame_level_final_tech_preds = model.model_inference(padded_cqt, cqt_lens, frame_level_note_attribs, note_attribs)

    # Ensure output dirs exist
    os.makedirs(tech_prediction_dir, exist_ok=True)
    os.makedirs(frame_level_dir, exist_ok=True)

    all_note_level: list[int] = []
    all_frame_level: list[int] = []

    for i in range(len(final_tech_preds)):
        # Slice to actual lengths to avoid padding artifacts
        T_i = int(cqt_lens[i].item())
        N_i = int(note_lens_list[i]) if note_lens_list else 0
        frame_level_note_attribs_i = frame_level_note_attribs[i, :T_i].tolist()
        frame_level_note_attribs_i = [[int(element) for element in row] for row in frame_level_note_attribs_i]
        note_attribs_i = note_attribs[i, :N_i].tolist()
        note_attribs_i = [[int(element) for element in row] for row in note_attribs_i]
        dur = []
        count = 0
        for _, onset, _, _, _ in note_attribs_i:
            if onset == 1 and count != 0:
                dur.append(count)
                count = 0
            count += 1
        dur.append(count)

        final_tech_prediction = [final_tech_preds[i]]
        final_tech_prediction = [int(element) for row in final_tech_prediction for element in row]
        pitch_string_fret = [row[2:] for row in note_attribs_i]
        final_tech_prediction_note_level = model.tatum_to_note(final_tech_prediction, dur, pitch_string_fret)
        frame_level_final_tech_prediction = [frame_level_final_tech_preds[i]]
        frame_level_final_tech_prediction = [int(element) for row in frame_level_final_tech_prediction for element in row]
        frame_level_full_attribs = [
            sublist + [element]
            for sublist, element in zip(
                frame_level_note_attribs_i, frame_level_final_tech_prediction
            )
        ]

        # Save per-segment outputs (TSV)
        seg_note_tsv = os.path.join(tech_prediction_dir, f"{track_name}_note_level_final_tech_full_prediction_segment_{i:02d}.tsv")
        _write_tsv(seg_note_tsv, final_tech_prediction_note_level)

        seg_frame_tsv = os.path.join(frame_level_dir, f"{track_name}_frame_level_final_tech_prediction_segment_{i:02d}.tsv")
        _write_tsv(seg_frame_tsv, frame_level_full_attribs)

        # Accumulate for concatenated outputs
        all_note_level.extend(final_tech_prediction_note_level)
        all_frame_level.extend(frame_level_final_tech_prediction)

    # Save concatenated outputs (TSV)
    concat_note_tsv = os.path.join(
        tech_prediction_dir,
        f"{track_name}_note_level_final_tech_full_prediction.tsv",
    )
    _write_tsv(concat_note_tsv, all_note_level)

    concat_frame_tsv = os.path.join(
        frame_level_dir,
        f"{track_name}_frame_level_final_tech_prediction.tsv",
    )
    _write_tsv(concat_frame_tsv, all_frame_level)

    return final_tech_preds, frame_level_final_tech_preds

if __name__ == "__main__":
    audio_file = "./idea-20250609.mp3"
    tech_model_checkpoint = "./solo_tech_epoch_099.ckpt"
    note_model_checkpoint = "./solo_trans_epoch_099.ckpt" 

    # Common CQT hyperparameters
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
    split_hop_bar_len = 4
    output_dir = "./output"

    print("="*60)
    print("Step 1: Loading audio and generating CQT segments...")
    print("="*60)
    track_name = os.path.split(audio_file)[1][:-4]
    audio, original_sr = librosa.load(audio_file)
    print(f"Loaded audio: sr={original_sr}, duration={len(audio)/original_sr:.2f}s")
    
    tempo = extract_tempo(audio, original_sr)
    print(f"Detected tempo: {tempo:.2f} BPM")
    
    # Generate CQT segments and metadata
    n_segments = process_cqt(
        audio=audio,
        tempo=tempo,
        original_sr=original_sr,
        track_name=track_name,
        split_unit_in_bars=split_unit_in_bars,
        split_hop_bar_len=split_hop_bar_len,
        hparams=cqt_hparams,
        output_dir=output_dir,
    )
    print(f"Generated {n_segments} CQT segments.")
    
    print("\n" + "="*60)
    print("Step 2: Predicting notes...")
    print("="*60)
    note_results = predict_notes(audio_file, note_model_checkpoint, tempo, output_dir)
    print(f"Note prediction complete. {len(note_results['segments'])} segments processed.")
    
    print("\n" + "="*60)
    print("Step 3: Generating frame-level note attributes...")
    print("="*60)
    # Generate ONLY frame-level attributes (CQT already exists from Step 1)
    n_segments = generate_frame_level_attributes(
        audio=audio,
        tempo=tempo,
        original_sr=original_sr,
        track_name=track_name,
        split_unit_in_bars=split_unit_in_bars,
        split_hop_bar_len=split_hop_bar_len,
        hparams=cqt_hparams,
        output_dir=output_dir,
        prediction_dir="./output/note_prediction",
    )
    print(f"Frame-level attributes generated for {n_segments} segments.")
    
    print("\n" + "="*60)
    print("Step 4: Predicting techniques...")
    print("="*60)
    final_tech_preds, frame_level_final_tech_preds = predict_techniques(audio_file, tech_model_checkpoint, output_dir)
    print("Technique prediction complete.")
    print("="*60)