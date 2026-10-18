@echo off
setlocal
rem Resolve the project root from this script.
pushd "%~dp0..\..\.." || exit /b 1

if not exist ".venv\Scripts\lerobot-find-port.exe" (
  echo Cannot find .venv\Scripts\lerobot-find-port.exe. Install LeRobot in the Windows project virtual environment.
  popd
  exit /b 1
)

echo Connect the robot controller via USB before continuing.
echo Follow the tool prompts: unplug only the target controller, then press Enter.
".venv\Scripts\lerobot-find-port.exe"
set "FIND_PORT_EXIT_CODE=%ERRORLEVEL%"
echo Reconnect the USB cable if you unplugged it.
if "%FIND_PORT_EXIT_CODE%"=="0" echo Note the COM port displayed above.
popd
exit /b %FIND_PORT_EXIT_CODE%
