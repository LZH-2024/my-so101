# SO101 录制脚本
# 职责：读取 hardware.yaml 和 record.yaml，调用 LeRobot 的录制入口。

from pathlib import Path

import yaml  # 使用 PyYAML 安全读取配置文件。


# 一、路径与配置入口
# 从脚本位置确定项目根目录，不依赖启动脚本时的工作目录。
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PROJECT_ROOT / "robots/so101/config/record.yaml"
DEFAULT_HARDWARE_CONFIG = PROJECT_ROOT / "robots/so101/config/hardware.yaml"


def resolve_project_path(path: str | Path) -> Path:
    """解析校准或数据集目录：相对路径以项目根目录为基准。"""
    path = Path(path).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


# 二、读取与检查配置
# 读取 YAML，检查 leader、follower、cameras、dataset 等配置段。
# 配置文件缺失、格式错误或必要字段缺失时，给出明确提示。
def load_yaml_config(config_path: str | Path) -> dict:
    """读取单个 YAML 配置文件并检查顶层结构。"""
    config_path = resolve_project_path(config_path)  # 将配置文件的相对路径转换为项目下的路径。
    try:  # 捕获文件读取和 YAML 解析错误。
        with config_path.open("r", encoding="utf-8") as file:  # 使用 UTF-8 打开文件，并在读取后自动关闭。
            config = yaml.safe_load(file)  # 安全解析 YAML，支持配置中的锚点与别名。
    except FileNotFoundError as exc:  # 处理配置文件不存在的情况。
        raise FileNotFoundError(f"录制配置文件不存在：{config_path}") from exc  # 提示缺失文件的完整路径。
    except (yaml.YAMLError, UnicodeError) as exc:  # 处理 YAML 语法或文本编码错误。
        raise ValueError(f"录制配置格式错误，请检查 YAML 语法和 UTF-8 编码：{config_path}\n{exc}") from exc  # 保留具体解析错误。
    except OSError as exc:  # 处理权限不足、路径为目录等读取错误。
        raise OSError(f"无法读取录制配置：{config_path}\n{exc}") from exc  # 提示文件路径及读取失败原因。

    if not isinstance(config, dict):  # 空文件或顶层为列表、字符串时不能作为录制配置。
        raise ValueError("录制配置顶层必须是 YAML 字典，且不能为空文件。")  # 提示正确的配置结构。
    return config


def load_config(
    config_path: str | Path = DEFAULT_CONFIG,
    hardware_config_path: str | Path = DEFAULT_HARDWARE_CONFIG,
) -> dict:
    """从硬件配置读取设备参数，从录制配置读取数据集及录制选项。"""
    hardware = load_yaml_config(hardware_config_path)
    config = load_yaml_config(config_path)
    for section in ("leader", "follower", "cameras"):
        if section in config:
            raise ValueError(f"请在硬件配置中配置 {section}，不要在录制配置中重复配置。")
        if section in hardware:
            config[section] = hardware[section]

    for section in ("leader", "follower", "cameras", "dataset"):  # 逐一检查项目约定的配置段。
        if section not in config:  # 检查必要配置段是否缺失。
            raise ValueError(f"录制配置缺少必要配置段：{section}")  # 指明缺失的配置段。
        if not isinstance(config[section], dict):  # 每个配置段都必须使用字典结构，允许 cameras 为空字典。
            raise ValueError(f"录制配置中的 {section} 必须是字典。")  # 指明结构错误的位置。

    required_fields = {"leader": ("type", "port"), "follower": ("type", "port"), "dataset": ("repo_id", "single_task")}  # 定义基础必填字段，其余参数稍后交给 LeRobot 校验。
    for section, fields in required_fields.items():  # 遍历各配置段的基础必填字段。
        for field in fields:  # 逐一检查字段值。
            value = config[section].get(field)  # 获取字段值，缺失时返回 None。
            if not isinstance(value, str) or not value.strip():  # 必填字段必须是非空字符串。
                raise ValueError(f"录制配置中的 {section}.{field} 必须是非空字符串。")  # 指明缺失或无效的字段。

    for name, camera in config["cameras"].items():  # 检查各相机配置的基础结构。
        if not isinstance(camera, dict):  # 每台相机的参数必须是字典。
            raise ValueError(f"录制配置中的 cameras.{name} 必须是字典。")  # 指明无效的相机配置。
        camera_type = camera.get("type")  # 获取相机类型，具体类型对应的参数稍后交给 LeRobot 校验。
        if not isinstance(camera_type, str) or not camera_type.strip():  # 相机类型必须是非空字符串。
            raise ValueError(f"录制配置中的 cameras.{name}.type 必须是非空字符串。")  # 提示缺失或无效的相机类型。
    return config  # 返回原始配置字典，供后续配置转换步骤使用。


# 三、将项目配置转换为命令行参数
# 将 leader 映射为 --teleop.*，将 follower 映射为 --robot.*。
# 将顶层 cameras 整体序列化为 --robot.cameras 的参数值。
# 将 dataset 中的配置转换为 --dataset.*，嵌套字段使用点号连接。
# 将 resume、display_data、play_sounds 等顶层选项转换为同名参数。
# 校准目录和数据集目录沿用项目根目录作为相对路径基准。
# 按命令行解析器要求处理字符串、布尔值、空值及字典，保留任务文本中的空格。
# 生成独立参数组成的列表，每个元素形如 --参数名=参数值。
def build_record_args(config: dict) -> list[str]:  # 将已读取的项目配置转换为录制命令的参数列表。
    from copy import deepcopy  # 复制嵌套配置，避免修改调用方的数据。
    import json  # 使用兼容 YAML 的 JSON 表示保留字符串、布尔值、空值和集合类型。

    options = deepcopy(config)  # 在独立副本上进行字段映射和路径转换。
    if "robot" in options or "teleop" in options:  # 检查项目字段与命令行字段是否重复。
        raise ValueError("请使用 leader 和 follower，不要同时配置 robot 或 teleop。")  # 提示冲突配置。
    options["teleop"] = options.pop("leader")  # 将主臂参数映射到遥操作器参数。
    options["robot"] = options.pop("follower")  # 将从臂参数映射到机器人参数。
    if "cameras" in options["robot"]:  # 防止覆盖从臂中的重复相机配置。
        raise ValueError("请在顶层 cameras 中配置相机，不要在 follower 中重复配置。")  # 提示相机配置位置。
    options["robot"]["cameras"] = options.pop("cameras")  # 将相机字典放入机器人参数中。
    for section, field in (("teleop", "calibration_dir"), ("robot", "calibration_dir"), ("dataset", "root")):  # 遍历需要统一基准的目录。
        value = options[section].get(field)  # 获取目录值，未设置的目录继续使用库的默认行为。
        if value is not None:  # 保留显式空值，不将其转换成路径。
            options[section][field] = str(resolve_project_path(value))  # 将相对目录转换成项目根目录下的绝对路径。

    args = []  # 保存独立参数，后续可直接传给子进程。
    nested_configs = {"teleop", "robot", "dataset", "dataset.rgb_encoder", "dataset.depth_encoder"}  # 这些配置对象展开为点号参数，字典字段则整体传递。

    def append_args(prefix: str, value: object) -> None:  # 递归展开配置对象并序列化叶子参数。
        if prefix in nested_configs and isinstance(value, dict):  # 仅展开配置对象，保留相机、各电机限幅和编码器额外选项等字典。
            for key, item in value.items():  # 按配置中的顺序遍历嵌套字段。
                append_args(f"{prefix}.{key}", item)  # 使用点号连接字段名称。
        else:  # 普通值、列表和字典作为一个完整参数传递。
            if prefix in {"teleop.type", "robot.type"} and isinstance(value, str):
                serialized = value  # 类型先经过 argparse choices 校验，不能包含 JSON 字符串的双引号。
            else:
                serialized = json.dumps(value, ensure_ascii=False, allow_nan=False)  # 其余参数由 YAML 解析，保留字符串、布尔值、空值及集合类型。
            args.append(f"--{prefix}={serialized}")  # 不添加 shell 引号，空格和特殊字符保留在同一个列表元素中。

    for key, value in options.items():  # 遍历映射后的所有顶层选项，保留录制开关和数据集参数。
        append_args(key, value)  # 将每个选项转换为一个或多个命令行参数。
    return args  # 返回参数列表，此处不组装命令或启动录制。


# 四、组装 LeRobot 录制命令
# 使用 LeRobot 提供的 lerobot-record 命令作为录制入口。
# 确认使用当前 Python 环境中的命令，找不到时提示检查安装和环境。
# 将命令路径与上述参数列表组合，形成可交给子进程执行的完整命令。
# 启动前展示便于人工核对的命令文本，实际执行仍使用参数列表。
def build_record_command(args: list[str]) -> list[str]:  # 接收录制参数并返回可供子进程执行的完整命令列表。
    import os  # 判断操作系统，以选择适合的命令显示方式。
    import shlex  # 为类 Unix 终端生成带有正确引号的命令展示文本。
    import shutil  # 查找脚本目录中可执行的录制命令。
    import subprocess  # 使用 Windows 命令行规则格式化展示文本。
    import sysconfig  # 获取当前 Python 环境的脚本安装目录。

    scripts_dir = sysconfig.get_path("scripts")  # 获取当前环境的 bin 或 Scripts 目录，避免误用其他环境中的命令。
    executable = shutil.which("lerobot-record", path=scripts_dir)  # 仅在当前环境的脚本目录中查找可执行入口。
    if executable is None:  # 当前环境未安装录制命令或入口不可执行时停止组装。
        raise FileNotFoundError(f"当前 Python 环境的脚本目录 {scripts_dir} 中找不到 lerobot-record，请检查环境并安装 requirements/base.txt 中的依赖。")  # 提示检查当前环境与依赖安装。
    command = [executable, *args]  # 保持各参数独立，不通过字符串拼接改变参数边界。
    display_command = subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)  # 根据操作系统生成便于核对的命令文本。
    print(f"即将执行录制命令：\n{display_command}", flush=True)  # 输出完整命令供核对，此处仅展示而不执行。
    return command  # 返回原始命令列表，供后续子进程执行步骤使用。


# 五、通过子进程执行录制脚本
# 使用 subprocess 启动命令，不通过 shell 拼接执行。
# 将工作目录设为项目根目录，并让子进程继承终端输入、输出和错误输出。
# 设备连接、采集、保存和退出清理由 LeRobot 录制脚本负责。
# 处理命令启动失败、非零退出码及用户中断，避免中断后遗留录制进程。
# 将录制命令的执行结果反馈给调用方。
def run_record_command(command: list[str]) -> int:  # 执行完整录制命令，返回退出码供主入口处理。
    import subprocess  # 使用子进程启动 LeRobot 的命令行脚本。
    import sys  # 将失败和中断提示写入标准错误输出。

    if not command:  # 避免使用空命令启动子进程。
        raise ValueError("录制命令不能为空。")  # 提示调用方先组装完整命令。
    try:  # 捕获命令不存在、无执行权限等启动错误。
        process = subprocess.Popen(command, cwd=PROJECT_ROOT, shell=False)  # 使用项目根目录并继承终端输入输出及前台进程组。
    except OSError as exc:  # 处理操作系统报告的命令启动失败。
        raise RuntimeError(f"无法启动录制命令 {command[0]}：{exc}") from exc  # 保留失败原因，便于排查环境。

    try:  # 等待录制脚本完成，正常退出前不返回。
        return_code = process.wait()  # 获取子进程退出码，期间保持终端交互可用。
    except KeyboardInterrupt:  # 终端 Ctrl+C 会同时通知同一前台进程组中的录制脚本。
        print("录制已中断，正在等待 LeRobot 保存数据并退出；再次按 Ctrl+C 将强制停止。", file=sys.stderr, flush=True)  # 提示用户等待脚本完成清理。
        try:  # 优先允许 LeRobot 自行完成保存和设备断开。
            process.wait()  # 不设置保存超时，避免视频编码尚未完成时提前终止。
        except KeyboardInterrupt:  # 用户再次中断时主动停止仍在运行的录制进程。
            process.terminate()  # 请求终止子进程，Windows 下会直接终止进程。
            try:  # 为终止操作预留短暂等待时间。
                process.wait(timeout=5)  # 等待子进程结束并回收进程资源。
            except (subprocess.TimeoutExpired, KeyboardInterrupt):  # 子进程未及时退出或用户继续中断时强制结束。
                process.kill()  # 强制停止仍未退出的录制进程。
                process.wait()  # 回收已停止的子进程，避免遗留进程资源。
        return 130  # 使用约定的中断退出码向主入口反馈用户取消。

    if return_code != 0:  # 对录制脚本的失败结果给出明确提示。
        print(f"LeRobot 录制命令执行失败，退出码：{return_code}", file=sys.stderr, flush=True)  # 详细错误由继承的子进程终端输出提供。
    return return_code  # 原样返回录制脚本退出码，不将失败伪装成成功。


# 六、脚本主入口
# 按“读取并检查配置 → 转换命令行参数 → 组装命令 → 执行录制脚本”的顺序组织流程。
# 仅在直接运行本脚本时启动命令，导入模块时不执行录制。
def main() -> int:  # 串联录制启动流程，并返回命令执行的退出码。
    config = load_config()  # 读取并检查默认的 hardware.yaml 和 record.yaml 配置。
    args = build_record_args(config)  # 将项目配置转换为 LeRobot 命令行参数列表。
    command = build_record_command(args)  # 定位当前环境中的录制命令并组合参数。
    return run_record_command(command)  # 执行录制脚本，将成功、失败或中断的退出码返回调用方。


if __name__ == "__main__":  # 仅直接运行脚本时进入此分支，导入模块时不启动录制。
    raise SystemExit(main())  # 将主入口返回的退出码传递给终端。
