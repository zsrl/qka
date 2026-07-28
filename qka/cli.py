"""
QKA命令行接口
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="QKA量化交易框架命令行工具")
    parser.add_argument("--version", action="store_true", help="显示版本信息")

    args = parser.parse_args()
    if args.version:
        from qka import __version__
        print(f"qka {__version__}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
