"""Entry point for launching TapeInk without a console window (pythonw)."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_FILE = ROOT / "tapeink_error.log"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    try:
        from app import main as run_app

        run_app()
    except Exception:
        # No console when started with pythonw, so persist the traceback.
        LOG_FILE.write_text(traceback.format_exc(), encoding="utf-8")
        try:
            from tkinter import messagebox

            messagebox.showerror(
                "TapeInk",
                f"שגיאה בהפעלה. פרטים נשמרו ב:\n{LOG_FILE}",
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
