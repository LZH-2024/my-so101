# 功能：调用 LeRobot 命令行工具 lerobot-find-port，查找机械臂串口。

import shutil
import subprocess
import sys
import sysconfig


def main() -> int:
    # 1. 检查当前 Python 环境，避免误用其他环境中的 LeRobot。
    scripts_dir = sysconfig.get_path("scripts")
    executable = shutil.which("lerobot-find-port", path=scripts_dir)
    if executable is None:
        print(
            f"在当前 Python 环境的脚本目录 {scripts_dir} 中找不到 lerobot-find-port。\n"
            "请使用已安装 LeRobot 的 Python 环境运行本脚本。",
            file=sys.stderr,
        )
        return 1

    # 2. 提示准备工作；具体拔线和回车时机由 LeRobot 工具提示。
    print(
        "请先通过 USB 连接机械臂控制板。\n"
        "接下来按工具提示拔掉目标机械臂的 USB 线，再按回车。\n"
        "若连接了多个机械臂，每次只拔掉要查询的那一个。",
        flush=True,
    )

    # 3. 继承终端输入输出，保留 LeRobot 的交互提示和端口结果。
    try:
        result = subprocess.run([executable], check=False)
    except KeyboardInterrupt:
        print("\n端口查找已中断。", file=sys.stderr)
        return 130
    except OSError as exc:
        print(f"无法启动端口查找命令：{exc}", file=sys.stderr)
        return 1
    finally:
        # 无论成功或失败，都提醒用户恢复 USB 连接。
        print("如果已拔掉 USB 线，请重新插回。", flush=True)

    # 4. 保留命令退出状态，便于终端或其他脚本判断执行结果。
    if result.returncode != 0:
        print(f"端口查找失败，退出码：{result.returncode}", file=sys.stderr)
        return result.returncode if result.returncode > 0 else 128 - result.returncode

    print("请记下上方显示的机械臂端口。", flush=True)
    return 0


# 5. 脚本入口：python robots/so101/scripts/find_port.py
if __name__ == "__main__":
    raise SystemExit(main())
