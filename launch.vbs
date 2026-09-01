' Gmail Zenith Pro - Instant Native App Launcher
' Kamran Ashraf (Kami) AI Suite

Option Explicit
Dim WshShell, FSO, CurrentDirectory, PythonExe, AppScript, CommandLine
Dim BrowserExe, TargetUrl

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

CurrentDirectory = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = CurrentDirectory

TargetUrl = "http://127.0.0.1:8765"

' 1. Determine Python Executable
PythonExe = "C:\Users\chkam\AppData\Local\Programs\Python\Python314\python.exe"
If Not FSO.FileExists(PythonExe) Then
    PythonExe = "python"
End If

AppScript = CurrentDirectory & "\backend\app.py"
CommandLine = Chr(34) & PythonExe & Chr(34) & " " & Chr(34) & AppScript & Chr(34)

' Launch Python server silently
On Error Resume Next
WshShell.Run CommandLine, 0, False
On Error GoTo 0

' 2. Find Chrome or Edge for instant native app window
BrowserExe = ""
If FSO.FileExists("C:\Program Files\Google\Chrome\Application\chrome.exe") Then
    BrowserExe = "C:\Program Files\Google\Chrome\Application\chrome.exe"
ElseIf FSO.FileExists("C:\Program Files (x86)\Google\Chrome\Application\chrome.exe") Then
    BrowserExe = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
ElseIf FSO.FileExists("C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe") Then
    BrowserExe = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ElseIf FSO.FileExists("C:\Program Files\Microsoft\Edge\Application\msedge.exe") Then
    BrowserExe = "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
End If

' Brief pause to let server bind port
WScript.Sleep 600

' Launch browser window directly
If BrowserExe <> "" Then
    WshShell.Run Chr(34) & BrowserExe & Chr(34) & " --app=" & TargetUrl, 1, False
Else
    WshShell.Run "cmd.exe /c start " & TargetUrl, 0, False
End If
