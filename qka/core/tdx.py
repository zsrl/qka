"""
通达信（TQ）数据源支持

qka 通过本机安装的「支持 TQ 策略」的通达信客户端取数：在进程内 ``import tqcenter``
（该模块随客户端自带），由 ``tqcenter`` 加载客户端目录下的 ``TPythClient.dll`` 与本机
运行中的 ``TdxW.exe`` 通信。因此本数据源：

- 仅支持 Windows；
- 要求用它的机器上装着 TQ 版通达信，且客户端在运行。

「通达信装在哪」是**这台机器怎么连上它**的问题，与「这次要取什么数据」（Data 的
symbols/period/adjust 等）无关，故独立于 Data 管理：优先用代码显式设置的，其次看
环境变量 ``QKA_TDX_ROOT``，最后自动从注册表识别。
"""

import os
import sys
import threading
from pathlib import Path
from typing import List, Optional

from qka.utils.logger import logger

# 环境变量：指向「支持 TQ 策略」的通达信安装目录
ENV_VAR = 'QKA_TDX_ROOT'

# 判定「是不是 TQ 版」的标志文件（相对安装目录）。普通版没有这个模块。
_TQ_MARKER = ('PYPlugins', 'user', 'tqcenter.py')

# 代码级设置（优先级最高，见 set_tdx_root）
_code_root: Optional[Path] = None

# 进程级复用：tqcenter 的 tq 是类级单例连接，全进程共用一个实例
_tq_client = None
_tq_lock = threading.Lock()


# ── 路径：识别 / 设置 / 查询 ────────────────────────────────────

def _is_tq_install(root: Path) -> bool:
    """目录是否是一套带 TQ 组件的通达信安装（依据标志文件是否存在）。"""
    try:
        return root.joinpath(*_TQ_MARKER).is_file()
    except OSError:
        return False


def _iter_registry_tdx_dirs() -> List[str]:
    """枚举注册表「卸载」表里所有含「通达信」的安装目录。

    覆盖 HKLM / HKCU 两个配置单元，并显式尝试 32 位与 64 位两个视图
    （TQ 版注册名形如「通达信金融终端64」）。非 Windows 或读不到时返回空列表。
    """
    try:
        import winreg
    except ImportError:
        return []

    sub = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    hives = (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER)
    views = (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY, 0)

    found: List[str] = []
    for hive in hives:
        for view in views:
            try:
                key = winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | view)
            except OSError:
                continue
            try:
                idx = 0
                while True:
                    try:
                        name = winreg.EnumKey(key, idx)
                    except OSError:
                        break
                    idx += 1
                    try:
                        sk = winreg.OpenKey(key, name)
                    except OSError:
                        continue
                    display = _reg_value(sk, "DisplayName")
                    location = _reg_value(sk, "InstallLocation")
                    if location and display and "通达信" in str(display):
                        found.append(str(location))
            finally:
                key.Close()
    return found


def _reg_value(key, name: str):
    """读一个注册表值，不存在返回 None。"""
    import winreg
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def set_tdx_root(path) -> Path:
    """显式指定「支持 TQ 策略」的通达信安装目录（优先级最高）。

    Args:
        path: 安装目录，如 ``r'D:\\new_tdx64'``

    Returns:
        Path: 规范化后的目录

    Raises:
        ValueError: 目录下没有 TQ 组件（``PYPlugins/user/tqcenter.py``）
    """
    global _code_root
    root = Path(path).expanduser()
    if not _is_tq_install(root):
        raise ValueError(
            f"{root} 不是支持 TQ 策略的通达信目录（未找到 "
            f"{Path(*_TQ_MARKER)}）。请指向装有 TQ 组件的那套安装。"
        )
    _code_root = root
    logger.info(f"已指定通达信安装目录: {root}")
    return root


def get_tdx_root_info() -> dict:
    """查询「当前会使用哪个通达信目录、以及它是怎么来的」。

    只做识别、**不建立连接**，因此可在客户端未启动时安全调用（如界面展示）。

    Returns:
        dict: ``{'root': str | None, 'source': 'code' | 'env' | 'auto' | None}``

        - ``source='code'``：代码里 ``set_tdx_root()`` 指定的
        - ``source='env'``：环境变量 ``QKA_TDX_ROOT`` 指定的
        - ``source='auto'``：从注册表自动识别到的
        - ``root=None``：以上都没有找到
    """
    if _code_root is not None:
        return {'root': str(_code_root), 'source': 'code'}

    env = os.environ.get(ENV_VAR)
    if env and _is_tq_install(Path(env)):
        return {'root': str(Path(env)), 'source': 'env'}

    for candidate in _iter_registry_tdx_dirs():
        root = Path(str(candidate).rstrip('\\/'))
        if _is_tq_install(root):
            return {'root': str(root), 'source': 'auto'}

    return {'root': None, 'source': None}


def resolve_tdx_root() -> Path:
    """取当前生效的通达信目录；找不到时给出可照做的三条出路。"""
    info = get_tdx_root_info()
    if info['root']:
        return Path(info['root'])
    raise RuntimeError(
        "未找到支持 TQ 策略的通达信安装目录。请任选其一：\n"
        "  1) 安装「支持 TQ 策略」的通达信（new_tdx64 版）\n"
        f"  2) 设置环境变量 {ENV_VAR} 指向其安装目录\n"
        "  3) 在代码里调用 qka.set_tdx_root(r'...')"
    )


# ── 连接：惰性加载 tqcenter 并初始化 ────────────────────────────

def get_tq():
    """惰性加载并返回通达信的 TQ 客户端（进程级复用、线程安全）。

    首次调用时：定位安装目录 → 把 ``PYPlugins/user`` 加入 sys.path → ``import tqcenter``
    → ``tq.initialize(...)``。之后复用同一实例。

    Returns:
        tqcenter.tq: 通达信数据访问类

    Raises:
        RuntimeError: 未找到安装目录 / 加载 TQ 模块失败 / 初始化失败（客户端未启动等）
    """
    global _tq_client
    if _tq_client is not None:
        return _tq_client

    with _tq_lock:
        if _tq_client is not None:
            return _tq_client

        root = resolve_tdx_root()
        plugin_dir = root.joinpath('PYPlugins', 'user')
        if str(plugin_dir) not in sys.path:
            sys.path.insert(0, str(plugin_dir))

        try:
            from tqcenter import tq
        except Exception as e:  # noqa: BLE001 - 原样上报给调用方
            raise RuntimeError(f"加载通达信 TQ 模块失败（{plugin_dir}）: {e}") from e

        # 初始化参数只是一个标识用的「策略文件路径」，不要求文件真实存在
        try:
            tq.initialize(str(Path(__file__).resolve()))
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                "通达信 TQ 初始化失败：请确认客户端（TdxW.exe）已启动。"
                f"\n原始错误: {e}"
            ) from e

        _tq_client = tq
        return _tq_client
