"""
Creates a desktop shortcut for Gmail Zenith Pro with custom icon.
"""

import os
from pathlib import Path
import sys

def create_shortcut():
    try:
        import win32com.client
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32"])
        import win32com.client

    desktop = Path(os.environ["USERPROFILE"]) / "OneDrive" / "Desktop"
    if not desktop.exists():
        desktop = Path(os.environ["USERPROFILE"]) / "Desktop"

    app_dir = Path("c:/Users/chkam/OneDrive/Desktop/BrandFinder/GmailZenith").resolve()
    vbs_path = app_dir / "launch.vbs"
    ico_path = app_dir / "gmail_zenith.ico"
    shortcut_path = desktop / "Gmail Zenith Pro - Kamran Ashraf.lnk"

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(shortcut_path))
    shortcut.TargetPath = "wscript.exe"
    shortcut.Arguments = f'"{str(vbs_path)}"'
    shortcut.WorkingDirectory = str(app_dir)
    shortcut.Description = "Gmail Zenith Pro — AI Inbox Optimizer & Triage Suite"
    if ico_path.exists():
        shortcut.IconLocation = f"{str(ico_path)},0"
    shortcut.Save()

    print(f"[OK] Desktop Shortcut created successfully at: {shortcut_path}")

if __name__ == "__main__":
    create_shortcut()
