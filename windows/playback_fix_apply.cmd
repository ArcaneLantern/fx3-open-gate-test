@echo off
rem FX3 (firmware 7.02): OPTIONAL, NOT RUN ON ANY CAMERA: in-camera playback of 3840x2560 clips with the A7 IV's decode channel (changes 4 instructions and 1 table word of av-cam.bin; refuses unless the caches can be made to fetch them).
rem WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; on the A7S III the power switch did too.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing: run setup.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -I -B "tools\camera_tests\CT6_memory_read_check\fx3_apply.py" playback %*
echo.
pause
