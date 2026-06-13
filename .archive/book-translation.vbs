' Itranslation — Silent GUI Launcher (no terminal window)
' Double-click this file to start the translation GUI.

Set fso = CreateObject("Scripting.FileSystemObject")
Set ws = CreateObject("Wscript.Shell")

' Determine project root (same directory as this script)
projectRoot = fso.GetParentFolderName(WScript.ScriptFullName)

' Change working directory to project root
ws.CurrentDirectory = projectRoot

' Launch silently (window style 0 = hidden, False = don't wait)
ws.Run "uv run python desktop.py", 0, False
