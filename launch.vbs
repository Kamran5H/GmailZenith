' Gmail Zenith Pro - Instant Native App Launcher
' Kamran Ashraf (Kami) AI Suite
Option Explicit
Dim WshShell, FSO, CurrentDirectory, PythonExe, AppScript, CommandLine
Dim BrowserExe, TargetUrl, candidates, cand, i

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

CurrentDirectory = FSO.GetParentFolderName(WScript.ScriptFullName)
If Not FSO.FileExists(CurrentDirectory & "\backend\app.py") Then
    candidates = Array( _
        "C:\Users\chkam\OneDrive\Desktop\BrandFinder\GmailZenith", _
        "C:\Users\chkam\OneDrive\Desktop\GmailZenith", _
        "C:\Users\chkam\Desktop\BrandFinder\GmailZenith" _
    )
    For Each cand In candidates
        If FSO.FileExists(cand & "\backend\app.py") Then
            CurrentDirectory = cand
            Exit For
        End If
    Next
End If

WshShell.CurrentDirectory = CurrentDirectory
TargetUrl = "http://127.0.0.1:8767"

PythonExe = "C:\Users\chkam\AppData\Local\Programs\Python\Python314\python.exe"
If Not FSO.FileExists(PythonExe) Then
    PythonExe = "python"
End If

AppScript = CurrentDirectory & "\backend\app.py"
CommandLine = "cmd /c " & Chr(34) & Chr(34) & PythonExe & Chr(34) & " " & Chr(34) & AppScript & Chr(34) & " > " & Chr(34) & CurrentDirectory & "\launch.log" & Chr(34) & " 2>&1" & Chr(34)

If Not ServerUp() Then
    On Error Resume Next
    WshShell.Run CommandLine, 0, False
    On Error GoTo 0
End If

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

For i = 1 To 60
    If ServerUp() Then Exit For
    WScript.Sleep 500
Next

If BrowserExe <> "" Then
    WshShell.Run Chr(34) & BrowserExe & Chr(34) & " --app=" & TargetUrl, 1, False
Else
    WshShell.Run "cmd.exe /c start " & TargetUrl, 0, False
End If

Function ServerUp()
    Dim h
    ServerUp = False
    On Error Resume Next
    Set h = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    h.setTimeouts 1500, 1500, 1500, 1500
    h.Open "GET", TargetUrl & "/", False
    h.Send
    If Err.Number = 0 And h.Status = 200 Then ServerUp = True
    On Error GoTo 0
End Function
