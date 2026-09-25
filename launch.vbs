' Gmail Zenith - silent launcher (double-click, or use the desktop shortcut).
' Starts the server in the background if needed, then opens the dashboard window.
Option Explicit
Dim sh, fso, appDir, py, url, i

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = appDir
url = "http://127.0.0.1:8767"

' Prefer a local virtual environment, then pythonw on PATH.
If fso.FileExists(appDir & "\.venv\Scripts\pythonw.exe") Then
    py = appDir & "\.venv\Scripts\pythonw.exe"
Else
    py = "pythonw"
End If

If Not ServerUp() Then
    sh.Run Chr(34) & py & Chr(34) & " " & Chr(34) & appDir & "\backend\app.py" & Chr(34) & " --no-browser", 0, False
    For i = 1 To 60
        If ServerUp() Then Exit For
        WScript.Sleep 500
    Next
End If

If Not ServerUp() Then
    MsgBox "Gmail Zenith could not start. Run run_gmail_zenith.bat to see the error.", 48, "Gmail Zenith"
    WScript.Quit 1
End If

' Open as an app window in Chrome/Edge if available, else the default browser.
Dim candidates, c
candidates = Array( _
    "C:\Program Files\Google\Chrome\Application\chrome.exe", _
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe", _
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", _
    "C:\Program Files\Microsoft\Edge\Application\msedge.exe")
For Each c In candidates
    If fso.FileExists(c) Then
        sh.Run Chr(34) & c & Chr(34) & " --app=" & url, 1, False
        WScript.Quit 0
    End If
Next
sh.Run url, 1, False

Function ServerUp()
    Dim h
    ServerUp = False
    On Error Resume Next
    Set h = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    h.setTimeouts 1000, 1000, 1000, 1000
    h.Open "GET", url & "/api/health", False
    h.Send
    If Err.Number = 0 Then
        If h.Status = 200 Then ServerUp = True
    End If
    On Error GoTo 0
End Function
