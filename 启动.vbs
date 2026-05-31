Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
gui = """" & scriptDir & "\gui.py" & """"

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
    MsgBox "Python not found. Please install Python first.", 48, "Error"
    WScript.Quit 1
End If

shell.CurrentDirectory = scriptDir
shell.Run """" & pythonPath & """ " & gui, 0, False
