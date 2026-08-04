"""Hebrew filler / discourse-marker cleanup for transcripts."""

from __future__ import annotations

import re
from typing import Iterable

# Default list — editable in Pro mode. Focus on spoken fillers, not real grammar.
DEFAULT_FILLERS: tuple[str, ...] = (
    "אה",
    "אמ",
    "אממ",
    "אמם",
    "אהמ",
    "המ",
    "הממ",
    "איזה",
    "כאילו",
    "יעני",
    "יענה",
    "כזה",
    "ככה",
    "נו",
    "אוקיי",
    "אוקי",
    "אוקיי אז",
    "טוב אז",
    "בעצם",
    "פשוט",
    "כאילו ש",
    "אמממ",
    "אהה",
    "אההה",
    "וואי",
    "וואלה",
    "תראה",
    "תשמע",
    "אתה יודע",
    "את יודעת",
)


def _token_pattern(filler: str) -> re.Pattern[str]:
    escaped = re.escape(filler)
    # Word-ish boundaries for Hebrew / Latin mix
    return re.compile(rf"(?<![\wא-ת]){escaped}(?![\wא-ת])", re.UNICODE)


def clean_text(text: str, fillers: Iterable[str] | None = None) -> str:
    """Remove filler phrases and tidy leftover punctuation/spaces."""
    if not text:
        return text

    words = sorted(set(fillers or DEFAULT_FILLERS), key=len, reverse=True)
    cleaned = text
    for filler in words:
        cleaned = _token_pattern(filler).sub(" ", cleaned)

    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"\[\s*\]", "", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
