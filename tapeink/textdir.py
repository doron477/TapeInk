"""Text direction handling for mixed Hebrew / English transcripts.

Tk on Windows already applies the Unicode BiDi algorithm when drawing text, so
strings must be passed through unchanged. Direction is used only to decide
alignment (right for Hebrew, left for English).
"""

from __future__ import annotations

AUTO = "auto"
RTL = "rtl"
LTR = "ltr"

RTL_LANGUAGES = frozenset({"he", "iw", "ar", "fa", "ur", "yi"})

_RTL_RANGES = (
    (0x0590, 0x05FF),  # Hebrew
    (0x0600, 0x06FF),  # Arabic
    (0xFB1D, 0xFDFF),  # Hebrew / Arabic presentation forms
)


def _is_rtl_char(ch: str) -> bool:
    code = ord(ch)
    return any(low <= code <= high for low, high in _RTL_RANGES)


def detect_direction(text: str, language: str | None = None) -> str:
    """Resolve RTL vs LTR from the language code, falling back to the text."""
    if language and language.lower() in RTL_LANGUAGES:
        return RTL

    rtl_count = sum(1 for ch in text if _is_rtl_char(ch))
    letter_count = sum(1 for ch in text if ch.isalpha())
    if letter_count and rtl_count / letter_count > 0.25:
        return RTL
    return LTR


def resolve_direction(mode: str, text: str, language: str | None = None) -> str:
    """Turn a UI choice (auto/rtl/ltr) into a concrete direction."""
    if mode in (RTL, LTR):
        return mode
    return detect_direction(text, language)


def justify_for(direction: str) -> str:
    """Tk justify value matching a direction."""
    return "right" if direction == RTL else "left"


def is_rtl(direction: str) -> bool:
    return direction == RTL
