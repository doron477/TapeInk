"""Create a Windows shortcut for TapeInk with the app icon.

The shortcut runs pythonw.exe so no console window appears.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHONW = ROOT / ".venv" / "Scripts" / "pythonw.exe"
ENTRY = ROOT / "TapeInk.pyw"
ICON = ROOT / "assets" / "tapeink.ico"

PS_TEMPLATE = """
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut('{target_lnk}')
$shortcut.TargetPath = '{python}'
$shortcut.Arguments = '"{entry}"'
$shortcut.WorkingDirectory = '{workdir}'
$shortcut.IconLocation = '{icon}'
$shortcut.WindowStyle = 1
$shortcut.Description = 'TapeInk - Hebrew audio transcription'
$shortcut.Save()
"""


def create_shortcut(destination: Path) -> Path:
    for required in (PYTHONW, ENTRY, ICON):
        if not required.exists():
            raise FileNotFoundError(f"Missing: {required}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    script = PS_TEMPLATE.format(
        target_lnk=destination,
        python=PYTHONW,
        entry=ENTRY,
        workdir=ROOT,
        icon=ICON,
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True,
        capture_output=True,
    )
    return destination


def main() -> None:
    targets = [ROOT / "TapeInk.lnk"]
    if "--desktop" in sys.argv:
        targets.append(Path.home() / "Desktop" / "TapeInk.lnk")

    for target in targets:
        print(f"created: {create_shortcut(target)}")


if __name__ == "__main__":
    main()
