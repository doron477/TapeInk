"""Pre-download the transcription model so the first run works offline."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    model_size = sys.argv[1] if len(sys.argv) > 1 else "small"

    from tapeink.device import detect_device

    device = detect_device(prefer_cuda=True)
    print(f"Downloading model '{model_size}' for {device.label} ...")

    try:
        from faster_whisper import WhisperModel

        WhisperModel(model_size, device=device.device, compute_type=device.compute_type)
    except Exception as exc:
        # A missing CUDA runtime must not fail the install; the app falls back to CPU.
        print(f"GPU load failed ({exc}); retrying on CPU ...")
        try:
            from faster_whisper import WhisperModel

            WhisperModel(model_size, device="cpu", compute_type="int8")
        except Exception as cpu_exc:
            print(f"Model download failed: {cpu_exc}")
            return 1

    print("Model ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
