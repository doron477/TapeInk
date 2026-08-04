r"""יוצר קובץ אודיו קצר בעברית לבדיקות (TTS מקוון של edge-tts).

שימוש:
    .\.venv\Scripts\python.exe scripts\make_sample_audio.py
"""

from __future__ import annotations

import asyncio
import tempfile
import wave
from pathlib import Path

import av
import edge_tts
import numpy as np

SAMPLE_RATE = 16_000
GAP_SECONDS = 0.6

LINES = [
    ("he-IL-AvriNeural", "שלום, זה מבחן קצר של טייפאינק. אני מקליט כמה משפטים בעברית."),
    ("he-IL-HilaNeural", "כן, אה, נשמע טוב. בוא נבדוק גם הפרדת דוברים וגם ניקוי מילות מילוי."),
    ("he-IL-AvriNeural", "מצוין. סיימנו את הבדיקה, תודה רבה."),
]

OUTPUT = Path(__file__).resolve().parent.parent / "samples" / "sample_he.wav"


async def synth(text: str, voice: str, dest: Path) -> None:
    await edge_tts.Communicate(text, voice).save(str(dest))


def decode_to_pcm(path: Path) -> np.ndarray:
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    chunks: list[np.ndarray] = []
    with av.open(str(path)) as container:
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)


async def main() -> None:
    gap = np.zeros(int(SAMPLE_RATE * GAP_SECONDS), dtype=np.int16)
    parts: list[np.ndarray] = []

    with tempfile.TemporaryDirectory() as tmp:
        for index, (voice, text) in enumerate(LINES):
            mp3 = Path(tmp) / f"line{index}.mp3"
            await synth(text, voice, mp3)
            parts.append(decode_to_pcm(mp3))
            parts.append(gap)

    audio = np.concatenate(parts)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUTPUT), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(audio.tobytes())

    print(f"{OUTPUT}  ({audio.size / SAMPLE_RATE:.1f}s, {OUTPUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    asyncio.run(main())
