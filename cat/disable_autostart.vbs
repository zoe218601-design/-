Option Explicit
Dim shell, fso, shortcutPath
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
shortcutPath = fso.BuildPath(shell.SpecialFolders("Startup"), "StrawberryDesktopCat.lnk")
If fso.FileExists(shortcutPath) Then fso.DeleteFile shortcutPath, True
MsgBox "Auto-start disabled. To close the running cat, right-click it and choose Exit.", 64, "Desktop Cat"
