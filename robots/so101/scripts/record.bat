@echo off
setlocal
rem Set Windows device identifiers below before running.
rem Linux leader /dev/ttyACM1 -> Windows COM port (for example COM3).
rem Linux follower /dev/ttyACM0 -> Windows COM port (for example COM4).
rem Camera indices must be checked on Windows; Linux video numbers do not map directly.
set "LEADER_PORT="
set "FOLLOWER_PORT="
set "WRIST_CAMERA_INDEX="
set "FRONT_CAMERA_INDEX="

if not defined LEADER_PORT goto missing_devices
if not defined FOLLOWER_PORT goto missing_devices
if not defined WRIST_CAMERA_INDEX goto missing_devices
if not defined FRONT_CAMERA_INDEX goto missing_devices

rem Resolve project root from this script, including paths containing spaces.
pushd "%~dp0..\..\.." || exit /b 1
rem Parameters copied from config/hardware.yaml and config/record.yaml.
".venv\Scripts\lerobot-record.exe" ^
  --teleop.type=so101_leader ^
  --teleop.port=%LEADER_PORT% ^
  --teleop.id=leader01 ^
  --teleop.calibration_dir=robots/so101/calibration/leader ^
  --teleop.use_degrees=true ^
  --robot.type=so101_follower ^
  --robot.port=%FOLLOWER_PORT% ^
  --robot.id=follower01 ^
  --robot.calibration_dir=robots/so101/calibration/follower ^
  --robot.use_degrees=true ^
  --robot.disable_torque_on_disconnect=true ^
  --robot.max_relative_target=null ^
  "--robot.cameras={wrist: {type: opencv, index_or_path: %WRIST_CAMERA_INDEX%, width: 640, height: 480, fps: 30}, front: {type: opencv, index_or_path: %FRONT_CAMERA_INDEX%, width: 640, height: 480, fps: 30}}" ^
  --dataset.repo_id=local/wrist_demo_001 ^
  --dataset.root=data/wrist_demo_001 ^
  "--dataset.single_task=Pick up the cube and place it in the box." ^
  --dataset.fps=20 ^
  --dataset.num_episodes=10 ^
  --dataset.episode_time_s=60 ^
  --dataset.reset_time_s=60 ^
  --dataset.video=true ^
  --dataset.rgb_encoder.vcodec=h264 ^
  --dataset.push_to_hub=false ^
  --dataset.no_stamp=true ^
  --resume=false ^
  --display_data=false ^
  --play_sounds=false
set "RECORD_EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %RECORD_EXIT_CODE%

:missing_devices
echo Set LEADER_PORT, FOLLOWER_PORT, WRIST_CAMERA_INDEX and FRONT_CAMERA_INDEX in this file.
exit /b 1
