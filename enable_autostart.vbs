Option Explicit
Dim shell, fso, folder, shortcut, shortcutPath, host
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
host = fso.BuildPath(shell.ExpandEnvironmentStrings("%SystemRoot%"), "System32\wscript.exe")
shortcutPath = fso.BuildPath(shell.SpecialFolders("Startup"), "FishCatPlay.lnk")
Set shortcut = shell.CreateShortcut(shortcutPath)
shortcut.TargetPath = host
shortcut.Arguments = Chr(34) & fso.BuildPath(folder, "start.vbs") & Chr(34)
shortcut.WorkingDirectory = folder
shortcut.WindowStyle = 7
shortcut.Description = "Fish and cat desktop toys"
shortcut.Save
MsgBox "Auto-start enabled for your Windows account. Keep this folder in its current location. The fish and cat will appear after you sign in.", 64, "Fish & Cat"
shell.Run Chr(34) & host & Chr(34) & " " & Chr(34) & fso.BuildPath(folder, "start.vbs") & Chr(34), 0, False
