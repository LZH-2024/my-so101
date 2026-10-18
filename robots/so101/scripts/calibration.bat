@echo off
setlocal
rem Set the Windows COM ports before running (for example COM3 and COM4).
rem Use the same ports as record.bat. Linux /dev/ttyACM paths do not apply.
set "LEADER_PORT="
set "FOLLOWER_PORT="

rem Usage: calibration.bat leader
rem        calibration.bat follower
if /i "%~1"=="leader" goto leader
if /i "%~1"=="follower" goto follower
echo Usage: %~nx0 leader ^| follower
exit /b 1

:leader
if not defined LEADER_PORT goto missing_port
pushd "%~dp0..\..\.." || exit /b 1
rem Parameters copied from config/hardware.yaml.
".venv\Scripts\lerobot-calibrate.exe" ^
  --teleop.type=so101_leader ^
  --teleop.port=%LEADER_PORT% ^
  --teleop.id=leader01 ^
  --teleop.calibration_dir=robots/so101/calibration/leader ^
  --teleop.use_degrees=true
goto finish

:follower
if not defined FOLLOWER_PORT goto missing_port
pushd "%~dp0..\..\.." || exit /b 1
rem Parameters copied from config/hardware.yaml.
".venv\Scripts\lerobot-calibrate.exe" ^
  --robot.type=so101_follower ^
  --robot.port=%FOLLOWER_PORT% ^
  --robot.id=follower01 ^
  --robot.calibration_dir=robots/so101/calibration/follower ^
  --robot.use_degrees=true ^
  --robot.disable_torque_on_disconnect=true ^
  --robot.max_relative_target=null
goto finish

:finish
set "CALIBRATION_EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %CALIBRATION_EXIT_CODE%

:missing_port
echo Set the selected device's LEADER_PORT or FOLLOWER_PORT in this file.
exit /b 1
