"""Basic smoke tests for TapeInk helpers."""

from tapeink.cleanup import clean_text
from tapeink.export import format_timestamp, segments_to_plain, segments_to_srt


def test_clean_fillers():
    text = "שלום אה כאילו מה נשמע אממ היום"
    cleaned = clean_text(text)
    assert "אה" not in cleaned.split()
    assert "כאילו" not in cleaned
    assert "שלום" in cleaned
    assert "מה נשמע" in cleaned


def test_export_formats():
    segments = [
        {"start": 0.0, "end": 1.5, "text": "שלום", "speaker": "דובר 1"},
        {"start": 1.5, "end": 3.0, "text": "מה נשמע", "speaker": "דובר 2"},
    ]
    plain = segments_to_plain(segments)
    assert "דובר 1" in plain
    assert "00:00:00" in plain
    srt = segments_to_srt(segments)
    assert "-->" in srt
    assert format_timestamp(65.5) == "00:01:05.500"


if __name__ == "__main__":
    test_clean_fillers()
    test_export_formats()
    print("tests ok")
