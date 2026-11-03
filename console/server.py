"""
QKA 控制台命令行启动服务 (Server Entrypoint)
"""

import sys
import time
import argparse
import webbrowser
import threading
from pathlib import Path

# 将项目根目录加入模块搜索路径
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from console.app import app


def open_browser_delayed(url: str, delay: float = 1.2):
    """延迟打开默认浏览器访问控制台"""
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()


def main():
    parser = argparse.ArgumentParser(description="QKA 量化控制台 Web 视觉平台")
    parser.add_argument("--port", type=int, default=15002, help="Web 服务监听端口 (默认: 15002)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Web 服务监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--no-browser", action="store_true", help="禁止自动打开默认浏览器")
    parser.add_argument("--debug", action="store_true", help="开启 Flask 调试模式")

    args = parser.parse_args()

    local_url = f"http://127.0.0.1:{args.port}"
    print("=" * 60)
    print("🚀 QKA (快量化) 可视化量化投研控制台")
    print(f"🌐 本地访问地址: {local_url}")
    print(f"📦 监听接口:     {args.host}:{args.port}")
    print("=" * 60)

    if not args.no_browser:
        open_browser_delayed(local_url)

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
