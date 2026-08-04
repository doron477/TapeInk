"""Device selection: CUDA when available, otherwise CPU."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DeviceInfo:
    device: str  # "cuda" | "cpu"
    compute_type: str  # faster-whisper compute type
    label: str


def _ensure_nvidia_dll_path() -> None:
    """Make pip-installed NVIDIA CUDA DLLs visible to CTranslate2 on Windows."""
    if sys.platform != "win32":
        return
    try:
        import nvidia  # type: ignore
    except Exception:
        return

    root = Path(nvidia.__path__[0])
    for pattern in ("*/bin", "*/*/bin"):
        for bin_dir in root.glob(pattern):
            if not bin_dir.is_dir():
                continue
            path_str = str(bin_dir)
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(path_str)
                except Exception:
                    pass
            current = os.environ.get("PATH", "")
            if path_str not in current.split(";"):
                os.environ["PATH"] = path_str + ";" + current


def detect_device(prefer_cuda: bool = True) -> DeviceInfo:
    """Pick the best available device for faster-whisper / CTranslate2."""
    _ensure_nvidia_dll_path()
    if prefer_cuda:
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                return DeviceInfo(
                    device="cuda",
                    compute_type="float16",
                    label="GPU (CUDA)",
                )
        except Exception:
            pass

    return DeviceInfo(
        device="cpu",
        compute_type="int8",
        label="CPU",
    )
