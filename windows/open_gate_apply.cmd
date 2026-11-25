@echo off
rem FX3 (firmware 7.02): apply the default state: 3840x2560 open gate in XAVC HS 4K, XAVC S 4K and XAVC S-I 4K (24p), and the rear screen at 3:2 with De-Squeeze Display set for it (five steps, then one read-only session). Open gate and the screen ran on FX3s; the S-I step is new.
rem WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; on the A7S III the power switch did too.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing: run setup.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -I -B "tools\camera_tests\CT6_memory_read_check\fx3_apply.py" apply %*
echo.
pause
