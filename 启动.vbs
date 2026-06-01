Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
logFile = scriptDir & "\xhs2pdf.log"

Sub WriteLog(msg)
    Dim f
    Set f = fso.OpenTextFile(logFile, 8, True)
    f.WriteLine "[" & Now & "] " & msg
    f.Close
End Sub

WriteLog "=== Starting ==="
WriteLog "Script dir: " & scriptDir

pythonPath = ""

' Try PATH first
Dim testRet
testRet = shell.Run("python --version", 0, True)
If testRet = 0 Then pythonPath = "python"

If pythonPath = "" Then
    testRet = shell.Run("python3 --version", 0, True)
    If testRet = 0 Then pythonPath = "python3"
End If

If pythonPath = "" Then
    testRet = shell.Run("py --version", 0, True)
    If testRet = 0 Then pythonPath = "py"
End If

' Try specific paths
If pythonPath = "" Then
    Dim paths(7)
    paths(0) = "C:\Python312\python.exe"
    paths(1) = "C:\Python311\python.exe"
    paths(2) = "C:\Python310\python.exe"
    paths(3) = "C:\Python\python.exe"
    paths(4) = "C:\Python3\python.exe"
    paths(5) = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\python.exe"
    paths(6) = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python311\python.exe"
    paths(7) = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Microsoft\WindowsApps\python.exe"

    Dim p
    For Each p In paths
        If fso.FileExists(p) Then
            pythonPath = p
            WriteLog "Found at: " & p
            Exit For
        End If
    Next
End If

WriteLog "pythonPath: " & pythonPath

If pythonPath = "" Then
    WriteLog "Python NOT FOUND"
    shell.Run "https://www.python.org/downloads/"
    MsgBox "Python not found. Download page opened." & vbCrLf & "Please install Python 3.7+ with 'Add to PATH' checked.", 64, "Python Required"
    WScript.Quit 1
End If

shell.CurrentDirectory = scriptDir
WriteLog "Working dir: " & scriptDir

' Launch with visible console first to catch errors
Dim cmd : cmd = """" & pythonPath & """ -m src.main"
WriteLog "Running: " & cmd

On Error Resume Next
shell.Run cmd, 0, False
If Err.Number <> 0 Then
    WriteLog "Launch error: " & Err.Description
    MsgBox "Launch failed. See log: " & logFile, 48, "Error"
Else
    WriteLog "Launch OK"
End If
