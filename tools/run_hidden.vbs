' Starts a .bat without a window -- AURON's helpers (copiers, market feed, chart feed, laptop helper) run in
' the background instead of five console windows on the desktop (Brano, 2026-10-25). Their logs are in their
' .log files; tools\stop_helpers.bat stops them.
'   wscript.exe tools\run_hidden.vbs <path\to\script.bat> [arguments]
Dim sh, args, i
Set sh = CreateObject("WScript.Shell")
args = """" & WScript.Arguments(0) & """"
For i = 1 To WScript.Arguments.Count - 1
  args = args & " " & WScript.Arguments(i)
Next
sh.CurrentDirectory = "C:\Users\brani\JARVIS_os"
sh.Run "cmd.exe /c " & args, 0, False
