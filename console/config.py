"""
QKA 全局配置管理模块 (Configuration Manager)
统一管理行情数据源、交易费率、回测基准与控制台服务的所有可配置项。
"""

import os
import json
from pathlib import Path
from typing import Dict, Any

CONFIG_FILE_NAME = "config.json"
ROOT_DIR = Path(__file__).resolve().parent.parent

# 优先在项目根目录查找/保存 config.json，其次在 ~/.qka/config.json
PROJECT_CONFIG_PATH = ROOT_DIR / CONFIG_FILE_NAME
USER_CONFIG_PATH = Path.home() / ".qka" / CONFIG_FILE_NAME

DEFAULT_CONFIG: Dict[str, Any] = {
    # 1. 行情与数据源配置 (Data & Market)
    "data": {
        "source": "tickflow",              # 默认行情源: tickflow / baostock / tdx
        "adjust": "qfq",                   # 默认复权方式: qfq / hfq / bfq
        "period": "1d",                    # 默认数据周期: 1d
        "tickflow_api_key": "",            # Tickflow 专有 API 密钥 (空为免费档)
        "tdx_root": "",                    # 通达信客户端本地安装目录 (Windows)
        "datadir": "",                     # 本地缓存目录路径 (留空则自动使用 ~/.qka 或 ./datadir)
        "factor_cache": False,             # 是否开启因子纵向持久化落盘
        "fill_suspended": False,           # 是否开启停牌日前向平滑补齐
        "warmup": 20                       # 默认因子预热天数
    },
    # 2. 交易撮合与费率模型 (Trading & Broker)
    "broker": {
        "commission_rate": 0.00025,        # 佣金费率 (万分之 2.5)
        "min_commission": 5.0,             # 最低佣金 (5 元起步)
        "stamp_duty_rate": 0.0005,         # 印花税率 (万分之 5，仅卖出)
        "slippage": 0.001,                 # 滑点比率 (千分之 1)
        "initial_cash": 200000.0           # 默认回测初始本金 (元)
    },
    # 3. 回测与基准设置 (Backtest & Benchmark)
    "backtest": {
        "benchmark": "000300.SH",          # 默认基准指数 (000300.SH 沪深300)
        "risk_free_rate": 0.03,            # 年化无风险利率 (3%)
        "periods_per_year": 252            # 年化交易日基数 (252 天)
    },
    # 4. 控制台服务设置 (Console Server)
    "server": {
        "port": 15002,                     # 监听端口
        "host": "0.0.0.0",                 # 监听地址
        "auto_open_browser": True          # 启动时是否自动打开浏览器
    }
}


def get_config_path() -> Path:
    """获取配置文件路径"""
    if PROJECT_CONFIG_PATH.exists():
        return PROJECT_CONFIG_PATH
    if USER_CONFIG_PATH.exists():
        return USER_CONFIG_PATH
    return PROJECT_CONFIG_PATH


def load_config() -> Dict[str, Any]:
    """读取配置，若不存在则返回默认配置"""
    path = get_config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                user_conf = json.load(f)
            # 深度合并默认值，确保新字段不缺失
            merged = json.loads(json.dumps(DEFAULT_CONFIG))
            for section, values in user_conf.items():
                if section in merged and isinstance(values, dict):
                    merged[section].update(values)
                else:
                    merged[section] = values
            return merged
        except Exception as e:
            print(f"[WARN] 读取配置文件 {path} 失败: {e}，使用默认配置")
    return json.loads(json.dumps(DEFAULT_CONFIG))


def save_config(new_config: Dict[str, Any]) -> bool:
    """保存配置并应用到当前运行时"""
    path = get_config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(new_config, f, indent=2, ensure_ascii=False)

        # 尝试应用到 qka 进程级配置
        apply_config_to_runtime(new_config)
        return True
    except Exception as e:
        print(f"[ERROR] 保存配置失败: {e}")
        return False


def apply_config_to_runtime(config: Dict[str, Any]):
    """将配置应用到 QKA 运行时模块"""
    data_conf = config.get("data", {})
    tf_key = data_conf.get("tickflow_api_key", "").strip()
    tdx_root = data_conf.get("tdx_root", "").strip()

    try:
        from qka.core.data import set_tickflow_api_key
        set_tickflow_api_key(tf_key if tf_key else None)
    except Exception:
        pass

    if tdx_root:
        try:
            from qka.core.tdx import set_tdx_root
            set_tdx_root(tdx_root)
        except Exception:
            pass


# 首次导入时自动应用已有配置
apply_config_to_runtime(load_config())
