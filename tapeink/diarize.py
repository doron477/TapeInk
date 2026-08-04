"""Speaker diarization via MFCC embeddings + clustering (no C++ build deps)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import numpy as np

ProgressCallback = Callable[[str], None]


def _load_wav_mono_16k(path: Path) -> tuple[np.ndarray, int]:
    import librosa

    wav, sr = librosa.load(str(path), sr=16000, mono=True)
    return wav.astype(np.float32), 16000


def _slice_wav(wav: np.ndarray, sr: int, start: float, end: float) -> np.ndarray:
    i0 = max(0, int(start * sr))
    i1 = min(len(wav), int(end * sr))
    if i1 <= i0:
        return np.zeros(0, dtype=np.float32)
    return wav[i0:i1]


def _embed_chunk(chunk: np.ndarray, sr: int) -> np.ndarray | None:
    """Compact speaker-ish embedding from MFCCs + deltas."""
    import librosa

    if len(chunk) < int(0.25 * sr):
        return None
    # Light normalization
    peak = np.max(np.abs(chunk)) + 1e-9
    chunk = chunk / peak
    mfcc = librosa.feature.mfcc(y=chunk, sr=sr, n_mfcc=20)
    delta = librosa.feature.delta(mfcc)
    feats = np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1), delta.mean(axis=1)])
    norm = np.linalg.norm(feats)
    if norm < 1e-9:
        return None
    return (feats / norm).astype(np.float32)


def assign_speakers(
    audio_path: str | Path,
    segments: list[dict[str, Any]],
    *,
    num_speakers: int | None = None,
    min_speakers: int = 1,
    max_speakers: int = 8,
    on_progress: ProgressCallback | None = None,
) -> list[dict[str, Any]]:
    """
    Attach speaker labels (דובר 1, דובר 2, …) to transcript segments.

    Uses librosa MFCC embeddings and agglomerative clustering.
    Works fully offline on CPU without Hugging Face or Visual C++.
    """
    if not segments:
        return segments

    path = Path(audio_path)
    if on_progress:
        on_progress("מחלץ מאפייני קול לדוברים…")

    wav, sr = _load_wav_mono_16k(path)

    embeddings: list[np.ndarray] = []
    usable_indices: list[int] = []

    for idx, seg in enumerate(segments):
        chunk = _slice_wav(wav, sr, float(seg["start"]), float(seg["end"]))
        emb = _embed_chunk(chunk, sr)
        if emb is None:
            continue
        embeddings.append(emb)
        usable_indices.append(idx)

    if len(usable_indices) < 2:
        for seg in segments:
            seg["speaker"] = "דובר 1"
        return segments

    matrix = np.vstack(embeddings)
    n = len(matrix)

    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score

    if on_progress:
        on_progress("מקבץ דוברים…")

    if num_speakers is not None:
        k = max(1, min(num_speakers, n))
    else:
        best_k = 1
        best_score = -1.0
        upper = min(max_speakers, n)
        lower = max(1, min_speakers)
        for k_try in range(lower, upper + 1):
            if k_try == 1:
                best_k = 1
                continue
            clustering = AgglomerativeClustering(
                n_clusters=k_try, metric="cosine", linkage="average"
            )
            labels = clustering.fit_predict(matrix)
            if len(set(labels)) < 2:
                continue
            try:
                score = float(silhouette_score(matrix, labels, metric="cosine"))
            except Exception:
                continue
            if score > best_score:
                best_score = score
                best_k = k_try
        k = best_k

    if k <= 1:
        labels = np.zeros(n, dtype=int)
    else:
        clustering = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average")
        labels = clustering.fit_predict(matrix)

    label_map = {idx: int(lab) for idx, lab in zip(usable_indices, labels)}
    labeled_times = [(float(segments[i]["start"]), label_map[i]) for i in label_map]

    for i, seg in enumerate(segments):
        if i in label_map:
            speaker_id = label_map[i]
        elif labeled_times:
            start = float(seg["start"])
            speaker_id = min(labeled_times, key=lambda t: abs(t[0] - start))[1]
        else:
            speaker_id = 0
        seg["speaker"] = f"דובר {speaker_id + 1}"

    return segments
