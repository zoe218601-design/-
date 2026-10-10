Option Explicit
Dim shell, fso, folder, command, result
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = folder
command = "cmd.exe /d /c " & Chr(34) & "where pythonw.exe >nul 2>nul && (pythonw.exe bootstrap.pyw) || (where pyw.exe >nul 2>nul && (pyw.exe bootstrap.pyw) || exit /b 2)" & Chr(34)
result = shell.Run(command, 0, True)
If result <> 0 Then
    MsgBox "Python could not start. Run install.bat first, or use start.bat to see the error.", 48, "Dry Fish"
End If
