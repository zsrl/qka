"""
QKA命令行接口
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="QKA量化交易框架命令行工具")
    parser.add_argument("--version", action="store_true", help="显示版本信息")

    subparsers = parser.add_subparsers(dest="subcommand", help="子命令")

    # console 子命令
    console_parser = subparsers.add_parser("console", help="启动可视化 Web 控制台")
    console_parser.add_argument("--port", type=int, default=15002, help="Web 端口 (默认: 15002)")
    console_parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    console_parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")

    args = parser.parse_args()
    if args.version:
        try:
            from qka import __version__
            print(f"qka {__version__}")
        except Exception:
            print("qka 0.1.0")
    elif args.subcommand == "console":
        from console.server import open_browser_delayed
        from console.app import app

        local_url = f"http://127.0.0.1:{args.port}"
        print("=" * 60)
        print("🚀 QKA (快量化) 可视化量化投研控制台")
        print(f"🌐 本地访问地址: {local_url}")
        print(f"📦 监听接口:     {args.host}:{args.port}")
        print("=" * 60)

        if not args.no_browser:
            open_browser_delayed(local_url)

        app.run(host=args.host, port=args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
