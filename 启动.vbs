Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
logFile = scriptDir & "\启动日志.log"
If fso.FileExists(logFile) Then fso.DeleteFile logFile

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
            Exit For
        End If
    Next
End If

If pythonPath = "" Then
    shell.Run "https://www.python.org/downloads/"
    MsgBox "Python not found. Download page opened." & vbCrLf & "Please install Python 3.8+ with 'Add to PATH' checked.", 64, "Python Required"
    WScript.Quit 1
End If

shell.CurrentDirectory = scriptDir
shell.Run """" & pythonPath & """ -m src.main", 0, False
