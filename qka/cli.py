"""
QKA命令行接口
"""
import argparse
import sys

def server_command(args):
    """启动ZeroMQ服务器"""
    from qka.server.zmq_server import main as server_main
    # 将args转换为列表以传递给main
    sys.argv = [sys.argv[0]] + args.extra_args
    server_main()

def main():
    parser = argparse.ArgumentParser(description="QKA量化交易框架命令行工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # server子命令
    server_parser = subparsers.add_parser("server", help="启动ZeroMQ服务器")
    server_parser.add_argument("extra_args", nargs=argparse.REMAINDER, help="传递给ZeroMQ服务器的额外参数")
    server_parser.set_defaults(func=server_command)
    
    # 解析参数
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    args.func(args)

if __name__ == "__main__":
    main()