Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
gui = "-m src.main"
logFile = scriptDir & "\启动错误.log"

pythonPath = ""
paths = Array( _
    "python", _
    "python3", _
    "D:\tools\Python12\python.exe", _
    "C:\Python\python.exe", _
    "C:\Python3\python.exe" _
)

For Each p In paths
    If pythonPath = "" Then
        If InStr(p, "\") > 0 Then
            If fso.FileExists(p) Then pythonPath = p
        Else
            pythonPath = p
        End If
    End If
Next

If pythonPath = "" Then
    Dim logF, msg
    msg = "[" & Now & "] Python not found." & vbCrLf
    Set logF = fso.OpenTextFile(logFile, 8, True)
    logF.Write msg
    logF.Close
    shell.Run "https://www.python.org/downloads/"
    MsgBox "Python not found. Download page opened. Please install Python 3.8+ with 'Add to PATH' checked, then restart.", 64, "Python Required"
    WScript.Quit 1
End If

shell.CurrentDirectory = scriptDir

On Error Resume Next
shell.Run """" & pythonPath & """ " & gui, 0, False
If Err.Number <> 0 Then
    Dim errMsg
    errMsg = "[" & Now & "] Launch failed: " & Err.Description & " (python=" & pythonPath & ")" & vbCrLf
    Set logF = fso.OpenTextFile(logFile, 8, True)
    logF.Write errMsg
    logF.Close
End If
