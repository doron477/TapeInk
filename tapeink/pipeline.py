"""High-level transcription pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from tapeink.cleanup import DEFAULT_FILLERS, clean_text
from tapeink.device import DeviceInfo, detect_device
from tapeink.diarize import assign_speakers
from tapeink.export import save_exports, segments_to_plain
from tapeink.transcribe import DEFAULT_GLOSSARY, TranscriptResult, transcribe_file

ProgressCallback = Callable[[str], None]


@dataclass
class PipelineOptions:
    model_size: str = "small"
    language: str = "he"
    prefer_cuda: bool = True
    diarize: bool = True
    num_speakers: int | None = None
    clean_fillers: bool = True
    fillers: list[str] = field(default_factory=lambda: list(DEFAULT_FILLERS))
    glossary: list[str] = field(default_factory=lambda: list(DEFAULT_GLOSSARY))
    include_timestamps: bool = True
    include_speakers: bool = True
    export_formats: tuple[str, ...] = ("txt", "srt", "json")


@dataclass
class PipelineResult:
    segments: list[dict[str, Any]]
    plain_text: str
    transcript: TranscriptResult
    saved_files: list[Path]
    device: DeviceInfo


def run_pipeline(
    audio_path: str | Path,
    output_dir: str | Path,
    options: PipelineOptions | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    opts = options or PipelineOptions()
    audio_path = Path(audio_path)
    output_dir = Path(output_dir)

    device = detect_device(prefer_cuda=opts.prefer_cuda)
    transcript = transcribe_file(
        audio_path,
        model_size=opts.model_size,
        language=opts.language,
        prefer_cuda=opts.prefer_cuda,
        device=device,
        glossary=opts.glossary,
        on_progress=on_progress,
    )

    segments = transcript.segments
    if opts.diarize:
        segments = assign_speakers(
            audio_path,
            segments,
            num_speakers=opts.num_speakers,
            on_progress=on_progress,
        )

    if opts.clean_fillers:
        if on_progress:
            on_progress("מנקה מילות מילוי…")
        for seg in segments:
            seg["text_raw"] = seg.get("text", "")
            seg["text"] = clean_text(seg.get("text", ""), opts.fillers)

    plain = segments_to_plain(
        segments,
        include_timestamps=opts.include_timestamps,
        include_speakers=opts.include_speakers and opts.diarize,
        clean_fillers=False,  # already cleaned in segments
    )

    if on_progress:
        on_progress("שומר קבצים…")

    saved = save_exports(
        segments,
        output_dir,
        stem=audio_path.stem,
        include_timestamps=opts.include_timestamps,
        include_speakers=opts.include_speakers and opts.diarize,
        clean_fillers=False,
        fillers=opts.fillers,
        formats=opts.export_formats,
        meta={
            "source": str(audio_path),
            "model_size": transcript.model_size,
            "language": transcript.language,
            "device": device.label,
            "diarize": opts.diarize,
            "clean_fillers": opts.clean_fillers,
        },
    )

    if on_progress:
        on_progress("הושלם.")

    return PipelineResult(
        segments=segments,
        plain_text=plain,
        transcript=transcript,
        saved_files=saved,
        device=device,
    )
