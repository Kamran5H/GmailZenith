"""
Creates a "Gmail Zenith" desktop shortcut (Windows) that runs launch.vbs silently.
Usage: python create_desktop_shortcut.py
"""

import os
from pathlib import Path
import subprocess
import sys

APP_DIR = Path(__file__).resolve().parent


def desktop_dir() -> Path:
    home = Path(os.environ.get("USERPROFILE", Path.home()))
    for candidate in (home / "OneDrive" / "Desktop", home / "Desktop"):
        if candidate.exists():
            return candidate
    return home


def create_shortcut() -> None:
    if os.name != "nt":
        sys.exit("Desktop shortcuts are only supported on Windows.")
    try:
        import win32com.client
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32"])
        import win32com.client

    shortcut_path = desktop_dir() / "Gmail Zenith.lnk"
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(shortcut_path))
    shortcut.TargetPath = "wscript.exe"
    shortcut.Arguments = f'"{APP_DIR / "launch.vbs"}"'
    shortcut.WorkingDirectory = str(APP_DIR)
    shortcut.Description = "Gmail Zenith - inbox cleanup dashboard"
    icon = APP_DIR / "gmail_zenith.ico"
    if icon.exists():
        shortcut.IconLocation = f"{icon},0"
    shortcut.Save()
    print(f"[OK] Shortcut created: {shortcut_path}")


if __name__ == "__main__":
    create_shortcut()
