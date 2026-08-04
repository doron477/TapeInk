"""Speech-to-text with faster-whisper (CPU or CUDA)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from tapeink.device import DeviceInfo, detect_device

ProgressCallback = Callable[[str], None]


@dataclass
class TranscriptResult:
    segments: list[dict[str, Any]]
    language: str
    language_probability: float
    device: DeviceInfo
    model_size: str


_model_cache: dict[tuple[str, str, str], Any] = {}


def _get_model(model_size: str, device: DeviceInfo):
    key = (model_size, device.device, device.compute_type)
    if key not in _model_cache:
        from faster_whisper import WhisperModel

        _model_cache[key] = WhisperModel(
            model_size,
            device=device.device,
            compute_type=device.compute_type,
        )
    return _model_cache[key]


def _collect_segments(
    model: Any,
    path: Path,
    *,
    language: str,
    on_progress: ProgressCallback | None,
) -> tuple[list[dict[str, Any]], Any]:
    segments_iter, info = model.transcribe(
        str(path),
        language=language or None,
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
    )

    segments: list[dict[str, Any]] = []
    for seg in segments_iter:
        words = []
        if seg.words:
            for w in seg.words:
                words.append(
                    {
                        "start": float(w.start or 0.0),
                        "end": float(w.end or 0.0),
                        "word": w.word,
                        "probability": float(w.probability or 0.0),
                    }
                )
        segments.append(
            {
                "start": float(seg.start),
                "end": float(seg.end),
                "text": (seg.text or "").strip(),
                "words": words,
                "speaker": None,
            }
        )
        if on_progress and len(segments) % 5 == 0:
            on_progress(f"מתמלל… ({len(segments)} קטעים)")
    return segments, info


def transcribe_file(
    audio_path: str | Path,
    *,
    model_size: str = "small",
    language: str = "he",
    prefer_cuda: bool = True,
    device: DeviceInfo | None = None,
    on_progress: ProgressCallback | None = None,
) -> TranscriptResult:
    """Transcribe an audio file to timestamped segments."""
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    device_info = device or detect_device(prefer_cuda=prefer_cuda)
    if on_progress:
        on_progress(f"טוען מודל ({model_size}) על {device_info.label}…")

    model = _get_model(model_size, device_info)

    if on_progress:
        on_progress("מתמלל…")

    try:
        segments, info = _collect_segments(
            model, path, language=language, on_progress=on_progress
        )
    except RuntimeError as exc:
        # Common on Windows: GPU driver present but CUDA runtime DLLs missing.
        message = str(exc).lower()
        if device_info.device == "cuda" and (
            "cublas" in message or "cuda" in message or "cudnn" in message
        ):
            if on_progress:
                on_progress("GPU לא זמין במלואו — עובר ל־CPU…")
            device_info = detect_device(prefer_cuda=False)
            model = _get_model(model_size, device_info)
            segments, info = _collect_segments(
                model, path, language=language, on_progress=on_progress
            )
        else:
            raise

    return TranscriptResult(
        segments=segments,
        language=info.language or language or "he",
        language_probability=float(info.language_probability or 0.0),
        device=device_info,
        model_size=model_size,
    )
