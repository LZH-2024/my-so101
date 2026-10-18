@echo off
setlocal
rem OpenCV matches config/hardware.yaml; timing and output match find_camera.py defaults.
pushd "%~dp0..\..\.." || exit /b 1

if not exist ".venv\Scripts\lerobot-find-cameras.exe" (
  echo Cannot find .venv\Scripts\lerobot-find-cameras.exe. Install LeRobot in the Windows project virtual environment.
  popd
  exit /b 1
)

echo Connect the cameras and close other programs using them.
".venv\Scripts\lerobot-find-cameras.exe" opencv ^
  --output-dir "outputs\captured_images" ^
  --record-time-s 2 ^
  --warmup-s 1
set "FIND_CAMERA_EXIT_CODE=%ERRORLEVEL%"
echo Check the logs and newly captured images in outputs\captured_images.
echo Note the camera indices for WRIST_CAMERA_INDEX and FRONT_CAMERA_INDEX in record.bat.
popd
exit /b %FIND_CAMERA_EXIT_CODE%
