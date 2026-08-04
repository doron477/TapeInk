"""Windows taskbar and title-bar icon helpers."""

from __future__ import annotations

import sys
from pathlib import Path

APP_USER_MODEL_ID = "doron477.TapeInk.1"


def set_process_app_id() -> None:
    """Give this process its own taskbar identity on Windows.

    Without this, pythonw.exe groups every Tk app under the Python icon even
    when iconbitmap is set on the window.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def apply_window_icon(window, icon_path: Path) -> None:
    """Set both the title-bar and taskbar icon for a Tk root window."""
    if not icon_path.exists():
        return
    path = str(icon_path.resolve())
    for setter in (
        lambda: window.iconbitmap(default=path),
        lambda: window.iconbitmap(path),
    ):
        try:
            setter()
            break
        except Exception:
            continue

    try:
        from PIL import Image, ImageTk

        img = Image.open(icon_path)
        if getattr(img, "n_frames", 1) > 1:
            img.seek(0)
        best = img
        best_area = img.size[0] * img.size[1]
        for index in range(getattr(img, "n_frames", 1)):
            img.seek(index)
            area = img.size[0] * img.size[1]
            if 32 <= max(img.size) <= 256 and area >= best_area:
                best = img.copy()
                best_area = area
        if max(best.size) > 64:
            resample = getattr(Image, "Resampling", Image).LANCZOS
            best = best.resize((64, 64), resample)
        photo = ImageTk.PhotoImage(best)
        window.iconphoto(True, photo)
        window._tapeink_icon_photo = photo  # type: ignore[attr-defined]
    except Exception:
        pass
