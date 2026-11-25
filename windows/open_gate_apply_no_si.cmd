@echo off
rem FX3 (firmware 7.02): apply the default state without the XAVC S-I 4K step (XAVC HS 4K and XAVC S 4K only, as the first kit).
rem WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; on the A7S III the power switch did too.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing: run setup.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -I -B "tools\camera_tests\CT6_memory_read_check\fx3_apply.py" apply --no-si %*
echo.
pause
