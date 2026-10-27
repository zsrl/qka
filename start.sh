#!/usr/bin/env bash
# ==============================================================================
# QKA (快量化) - Web 可视化控制台启动脚本 (macOS / Linux)
# 用法:
#   ./start.sh              # 启动 Web 控制台并自动打开浏览器 (http://127.0.0.1:15002)
#   ./start.sh --port 15003 # 指定端口启动
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================="
echo "🚀 QKA (快量化) 可视化量化投研控制台启动工具"
echo "📂 项目工作目录: $SCRIPT_DIR"
echo "======================================================="

# 自动初始化配置文件 config.json
if [ ! -f "config.json" ] && [ -f "config.json.example" ]; then
    echo "📝 未检测到 config.json，正在从 config.json.example 自动初始化..."
    cp config.json.example config.json
fi

# 探测 Python 解释器
PYTHON_BIN=""
if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
    PYTHON_BIN="venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "❌ 错误: 未检测到 Python 环境，请先安装 Python 3.10+ (https://www.python.org/)"
    exit 1
fi

echo "🐍 使用 Python: $($PYTHON_BIN --version 2>&1) ($PYTHON_BIN)"

# 解析端口参数（默认 15002）
PORT=15002
ARGS=("$@")
for ((i=0; i<${#ARGS[@]}; i++)); do
    if [ "${ARGS[$i]}" = "--port" ] && [ $((i+1)) -lt ${#ARGS[@]} ]; then
        PORT="${ARGS[$((i+1))]}"
    fi
done

# 延迟打开默认浏览器
(
    sleep 1.5
    URL="http://127.0.0.1:${PORT}"
    if command -v open >/dev/null 2>&1; then
        open "$URL" >/dev/null 2>&1 || true
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$URL" >/dev/null 2>&1 || true
    fi
) &

echo "🌐 正在启动 Web 控制台: http://127.0.0.1:${PORT} (停止请按 Ctrl + C)..."
exec "$PYTHON_BIN" console/server.py "$@"
