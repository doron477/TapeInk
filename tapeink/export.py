"""Export transcripts to TXT / SRT / JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tapeink.cleanup import clean_text


def format_timestamp(seconds: float, srt: bool = False) -> str:
    if seconds < 0:
        seconds = 0.0
    millis = int(round(seconds * 1000))
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    sep = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{ms:03d}"


def segments_to_plain(
    segments: list[dict[str, Any]],
    *,
    include_timestamps: bool = True,
    include_speakers: bool = True,
    clean_fillers: bool = False,
    fillers: list[str] | None = None,
) -> str:
    lines: list[str] = []
    for seg in segments:
        text = seg.get("text", "").strip()
        if clean_fillers:
            text = clean_text(text, fillers)
        if not text:
            continue

        parts: list[str] = []
        if include_timestamps:
            start = format_timestamp(float(seg.get("start", 0.0)))
            end = format_timestamp(float(seg.get("end", 0.0)))
            parts.append(f"[{start} → {end}]")
        if include_speakers and seg.get("speaker"):
            parts.append(f"{seg['speaker']}:")
        parts.append(text)
        lines.append(" ".join(parts))
    return "\n".join(lines).strip() + ("\n" if lines else "")


def segments_to_display(
    segments: list[dict[str, Any]],
    *,
    rtl: bool,
    include_timestamps: bool = True,
    include_speakers: bool = True,
) -> str:
    """Screen-friendly transcript that opens each segment with its timestamp.

    The timestamp gets a header line of its own because a long segment wraps,
    and an inline timestamp would drift onto the last wrapped row instead of
    staying where the segment begins.

    Tk has no paragraph base direction: it reorders characters within a run but
    always lays the runs themselves out left to right. On a right-to-left line
    the run written last is therefore the one drawn at the right edge, where a
    Hebrew reader starts. Hence the header is built speaker-then-stamp for RTL,
    so that it reads stamp-then-speaker on screen. Exported files are unaffected.
    """
    blocks: list[str] = []
    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue

        speaker = seg.get("speaker") if include_speakers else None
        stamp = ""
        if include_timestamps:
            start = format_timestamp(float(seg.get("start", 0.0)))
            end = format_timestamp(float(seg.get("end", 0.0)))
            stamp = f"{start}–{end}" if rtl else f"{start} → {end}"

        header_parts = [speaker, stamp] if rtl else [stamp, speaker]
        header = " · ".join(p for p in header_parts if p)
        blocks.append(f"{header}\n{text}" if header else text)

    return "\n\n".join(blocks) + ("\n" if blocks else "")


def segments_to_srt(
    segments: list[dict[str, Any]],
    *,
    include_speakers: bool = True,
    clean_fillers: bool = False,
    fillers: list[str] | None = None,
) -> str:
    blocks: list[str] = []
    index = 1
    for seg in segments:
        text = seg.get("text", "").strip()
        if clean_fillers:
            text = clean_text(text, fillers)
        if not text:
            continue
        if include_speakers and seg.get("speaker"):
            text = f"{seg['speaker']}: {text}"
        start = format_timestamp(float(seg.get("start", 0.0)), srt=True)
        end = format_timestamp(float(seg.get("end", 0.0)), srt=True)
        blocks.append(f"{index}\n{start} --> {end}\n{text}\n")
        index += 1
    return "\n".join(blocks)


def segments_to_json(
    segments: list[dict[str, Any]],
    *,
    clean_fillers: bool = False,
    fillers: list[str] | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    payload_segments = []
    for seg in segments:
        item = dict(seg)
        if clean_fillers and "text" in item:
            item["text"] = clean_text(item["text"], fillers)
            item["text_raw"] = seg.get("text", "")
        payload_segments.append(item)
    payload = {"meta": meta or {}, "segments": payload_segments}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def save_exports(
    segments: list[dict[str, Any]],
    destination: Path,
    *,
    stem: str,
    include_timestamps: bool = True,
    include_speakers: bool = True,
    clean_fillers: bool = False,
    fillers: list[str] | None = None,
    formats: tuple[str, ...] = ("txt", "srt", "json"),
    meta: dict[str, Any] | None = None,
) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if "txt" in formats:
        path = destination / f"{stem}.txt"
        path.write_text(
            segments_to_plain(
                segments,
                include_timestamps=include_timestamps,
                include_speakers=include_speakers,
                clean_fillers=clean_fillers,
                fillers=fillers,
            ),
            encoding="utf-8",
        )
        written.append(path)

    if "srt" in formats:
        path = destination / f"{stem}.srt"
        path.write_text(
            segments_to_srt(
                segments,
                include_speakers=include_speakers,
                clean_fillers=clean_fillers,
                fillers=fillers,
            ),
            encoding="utf-8",
        )
        written.append(path)

    if "json" in formats:
        path = destination / f"{stem}.json"
        path.write_text(
            segments_to_json(
                segments,
                clean_fillers=clean_fillers,
                fillers=fillers,
                meta=meta,
            ),
            encoding="utf-8",
        )
        written.append(path)

    return written
