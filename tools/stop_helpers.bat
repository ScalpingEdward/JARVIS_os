@echo off
rem Stops AURON's background helpers (they run without a window, see tools\run_hidden.vbs):
rem the market feed, the chart feed, the laptop helper and the TV gate -- and the copiers only with "copiers".
rem   tools\stop_helpers.bat            helpers only
rem   tools\stop_helpers.bat copiers    also both copiers (check first that no trade is open!)
set PATTERN=market_feed^|chart_feed^|desk_runner^|tv_gate
if /i "%1"=="copiers" set PATTERN=market_feed^|chart_feed^|desk_runner^|tv_gate^|signal_copier.copier^|autostart.bat
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match '%PATTERN%' -and $_.ProcessId -ne $PID } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; 'stopped ' + $_.Name + ' ' + $_.ProcessId }"
