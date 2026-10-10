Option Explicit
Dim shell, fso, folder, shortcut, shortcutPath, host
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
host = fso.BuildPath(shell.ExpandEnvironmentStrings("%SystemRoot%"), "System32\wscript.exe")
shortcutPath = fso.BuildPath(shell.SpecialFolders("Startup"), "StrawberryDesktopCat.lnk")
Set shortcut = shell.CreateShortcut(shortcutPath)
shortcut.TargetPath = host
shortcut.Arguments = Chr(34) & fso.BuildPath(folder, "start.vbs") & Chr(34)
shortcut.WorkingDirectory = folder
shortcut.WindowStyle = 7
shortcut.Description = "Strawberry desktop cat"
shortcut.Save
MsgBox "Auto-start enabled for your Windows account. Keep this folder in its current location. The cat will appear after you sign in.", 64, "Desktop Cat"
shell.Run Chr(34) & host & Chr(34) & " " & Chr(34) & fso.BuildPath(folder, "start.vbs") & Chr(34), 0, False
