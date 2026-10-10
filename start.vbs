Option Explicit
Dim shell, fso, folder, host
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
host = fso.BuildPath(shell.ExpandEnvironmentStrings("%SystemRoot%"), "System32\wscript.exe")
shell.Run Chr(34) & host & Chr(34) & " " & Chr(34) & fso.BuildPath(folder,"cat\start.vbs") & Chr(34), 0, False
shell.Run Chr(34) & host & Chr(34) & " " & Chr(34) & fso.BuildPath(folder,"fish\start.vbs") & Chr(34), 0, False
