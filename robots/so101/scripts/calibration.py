# SO101 校准脚本
# 读取 hardware.yaml 中所选设备的配置，通过 LeRobot 命令完成交互式校准。

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

import yaml


# 一、路径与配置入口：相对路径统一以项目根目录为基准。
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PROJECT_ROOT / "robots/so101/config/hardware.yaml"
TARGET_PREFIXES = {"leader": "teleop", "follower": "robot"}
# 对应 requirements/base.txt 中 LeRobot 0.6.1 的 SO101 设备配置字段。
COMMON_FIELDS = {"type", "port", "id", "calibration_dir", "use_degrees", "num_read_retries"}
SUPPORTED_FIELDS = {
    "leader": COMMON_FIELDS,
    "follower": COMMON_FIELDS | {
        "disable_torque_on_disconnect", "max_relative_target",
        "position_p_coefficient", "position_i_coefficient", "position_d_coefficient",
    },
}


def resolve_project_path(path: str | Path) -> Path:
    """解析配置文件和校准目录的路径，不依赖启动时的工作目录。"""
    path = Path(path).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


# 二、选择校准目标：必须显式指定，每次只校准一台设备。
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="读取 hardware.yaml，调用 LeRobot 校准所选 SO101 设备。")
    parser.add_argument("--target", required=True, choices=TARGET_PREFIXES, help="校准目标：leader 或 follower")
    return parser.parse_args(argv)


# 三、读取与检查配置：仅检查所选目标，不依赖相机或录制配置。
def load_config(target: str, config_path: str | Path = DEFAULT_CONFIG) -> dict:
    """读取并返回所选设备配置，不修改原始 YAML 文件。"""
    if target not in TARGET_PREFIXES:
        raise ValueError("校准目标必须是 leader 或 follower。")
    config_path = resolve_project_path(config_path)
    try:
        with config_path.open("r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
    except (yaml.YAMLError, UnicodeError) as exc:
        raise ValueError(f"校准配置格式错误，请检查 YAML 语法和 UTF-8 编码：{config_path}\n{exc}") from exc
    except OSError as exc:
        raise OSError(f"无法读取校准配置：{config_path}\n{exc}") from exc

    if not isinstance(config, dict):
        raise ValueError("校准配置顶层必须是非空 YAML 字典。")
    device = config.get(target)
    if not isinstance(device, dict):
        raise ValueError(f"校准配置缺少 {target} 配置段，或该配置段不是字典。")
    for field in ("type", "port", "id", "calibration_dir"):
        value = device.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"校准配置中的 {target}.{field} 必须是非空字符串。")
    if device["type"] != f"so101_{target}":
        raise ValueError(f"{target}.type 必须为 so101_{target}，请检查校准目标。")
    # 相机不参与校准；其他未知字段报错，避免拼写错误被静默忽略。
    unknown = set(device) - SUPPORTED_FIELDS[target] - {"cameras"}
    if unknown:
        raise ValueError(f"{target} 包含不支持的校准配置字段：{', '.join(sorted(map(str, unknown)))}")
    return device


# 四、转换参数：保留字符串、布尔值、空值及字典的类型与参数边界。
def build_calibration_args(target: str, device: dict) -> list[str]:
    """将所选设备映射为 teleop 或 robot 参数，不传入相机配置。"""
    prefix = TARGET_PREFIXES[target]
    args = []
    for field, value in device.items():
        if field not in SUPPORTED_FIELDS[target]:
            continue
        if field == "calibration_dir":
            value = str(resolve_project_path(value))
        # type 先由 argparse choices 校验，不使用 JSON 字符串引号。
        serialized = value if field == "type" else json.dumps(value, ensure_ascii=False, allow_nan=False)
        args.append(f"--{prefix}.{field}={serialized}")
    return args


# 五、组装命令：仅查找当前 Python 环境的命令，避免混用其他环境。
def build_calibration_command(args: list[str]) -> list[str]:
    scripts_dir = sysconfig.get_path("scripts")
    executable = shutil.which("lerobot-calibrate", path=scripts_dir)
    if executable is None:
        raise FileNotFoundError(
            f"当前 Python 环境的脚本目录 {scripts_dir} 中找不到 lerobot-calibrate，"
            "请检查环境并安装 requirements/base.txt 中的依赖。"
        )
    return [executable, *args]


# 六、执行交互式校准：继承终端，由 LeRobot 负责设备操作及校准文件保存。
def run_calibration_command(command: list[str]) -> int:
    """执行命令并返回退出码；中断时等待设备清理，必要时终止子进程。"""
    if not command:
        raise ValueError("校准命令不能为空。")
    try:
        process = subprocess.Popen(command, cwd=PROJECT_ROOT, shell=False)
    except OSError as exc:
        raise RuntimeError(f"无法启动校准命令 {command[0]}：{exc}") from exc
    try:
        return_code = process.wait()
    except KeyboardInterrupt:
        # 终端 Ctrl+C 同时通知同一前台进程组中的 LeRobot 子进程。
        print("校准已中断，正在等待 LeRobot 断开设备；再次按 Ctrl+C 将终止进程。", file=sys.stderr, flush=True)
        try:
            process.wait()
        except KeyboardInterrupt:
            process.terminate()
            try:
                process.wait(timeout=5)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                process.kill()
                process.wait()
        return 130
    if return_code != 0:
        print(f"LeRobot 校准命令执行失败，退出码：{return_code}", file=sys.stderr, flush=True)
    return return_code


# 七、脚本主入口：导入模块时不连接设备或执行校准命令。
def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    try:
        device = load_config(options.target)
        args = build_calibration_args(options.target, device)
        command = build_calibration_command(args)
        print(
            f"校准目标：{options.target}\n设备端口：{device['port']}\n"
            f"校准保存目录：{resolve_project_path(device['calibration_dir'])}\n"
            f"即将执行校准命令：\n{shlex.join(command)}",
            flush=True,
        )
        return run_calibration_command(command)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"校准失败：{exc}", file=sys.stderr)
        return 1


# 用法：python robots/so101/scripts/calibration.py --target leader（或 follower）
if __name__ == "__main__":
    raise SystemExit(main())
