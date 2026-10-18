# 功能：调用 LeRobot 命令行工具，查看摄像头信息并保存测试图片。

import argparse
import math
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig


def parse_args() -> argparse.Namespace:
    # 1. 提供与 LeRobot 命令对应的参数；相对输出路径以当前工作目录为准。
    parser = argparse.ArgumentParser(description="查看摄像头信息并通过 LeRobot 采集测试图片。")
    parser.add_argument(
        "camera_type", nargs="?", choices=["opencv", "realsense"],
        help="摄像头类型；省略时查找所有支持的类型。",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("outputs/captured_images"),
        help="测试图片保存目录（默认：outputs/captured_images）。",
    )
    parser.add_argument(
        "--record-time-s", type=float, default=2.0,
        help="每个摄像头的采集时长，单位秒（默认：2）。",
    )
    parser.add_argument(
        "--warmup-s", type=int, default=1,
        help="摄像头预热时长，单位秒（默认：1）。",
    )
    args = parser.parse_args()
    if not math.isfinite(args.record_time_s) or args.record_time_s <= 0:
        parser.error("--record-time-s 必须是大于零的有限数值。")
    if args.warmup_s < 0:
        parser.error("--warmup-s 必须是非负整数。")
    return args


def main() -> int:
    args = parse_args()

    # 2. 仅查找当前 Python 环境中的入口，避免误用其他环境的 LeRobot。
    scripts_dir = sysconfig.get_path("scripts")
    executable = shutil.which("lerobot-find-cameras", path=scripts_dir)
    if executable is None:
        print(
            f"在当前 Python 环境的脚本目录 {scripts_dir} 中找不到 lerobot-find-cameras。\n"
            "请使用已安装 LeRobot 的 Python 环境运行本脚本。",
            file=sys.stderr,
        )
        return 1

    # 3. 使用参数列表组装命令，由 LeRobot 完成设备发现、采集和图片保存。
    output_dir = args.output_dir.expanduser().resolve()
    command = [executable]
    if args.camera_type is not None:
        command.append(args.camera_type)
    command.extend([
        "--output-dir", str(output_dir),
        "--record-time-s", str(args.record_time_s),
        "--warmup-s", str(args.warmup_s),
    ])
    print(
        "请连接摄像头，并关闭可能占用摄像头的程序。\n"
        f"即将查看摄像头信息并采集测试图片，输出目录：{output_dir}",
        flush=True,
    )

    # 4. 继承终端输入输出，显示原始设备信息与错误日志。
    try:
        result = subprocess.run(command, check=False)
    except KeyboardInterrupt:
        print("\n摄像头测试已中断。", file=sys.stderr)
        return 130
    except OSError as exc:
        print(f"无法启动摄像头测试命令：{exc}", file=sys.stderr)
        return 1

    # 保留退出状态；通过信号终止时转换为终端常用的退出码。
    if result.returncode != 0:
        print(f"摄像头命令执行失败，退出码：{result.returncode}", file=sys.stderr)
        return result.returncode if result.returncode > 0 else 128 - result.returncode

    # LeRobot 在未发现设备或部分采集失败时也可能返回零，不能据此断言测试成功。
    print(
        f"摄像头命令已结束，请结合上方日志和 {output_dir} 中本次生成的图片确认测试结果。",
        flush=True,
    )
    return 0


# 5. 示例：python robots/so101/scripts/find_camera.py opencv --record-time-s 2
if __name__ == "__main__":
    raise SystemExit(main())
