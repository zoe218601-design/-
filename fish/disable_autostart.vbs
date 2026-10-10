Option Explicit
Dim shell, fso, shortcutPath
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
shortcutPath = fso.BuildPath(shell.SpecialFolders("Startup"), "MouseDryFish.lnk")
If fso.FileExists(shortcutPath) Then fso.DeleteFile shortcutPath, True
MsgBox "Auto-start disabled. To close the running ghost, right-click it and choose Exit.", 64, "Dry Fish"
