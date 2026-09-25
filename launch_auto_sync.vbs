' Gmail Zenith - silent background Auto-Clean daemon launcher.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = appDir

py = "pythonw"
If fso.FileExists(appDir & "\.venv\Scripts\pythonw.exe") Then py = appDir & "\.venv\Scripts\pythonw.exe"

sh.Run Chr(34) & py & Chr(34) & " " & Chr(34) & appDir & "\auto_sync_daemon.py" & Chr(34), 0, False
