@echo off
chcp 65001 >nul
title QKA 量化投研可视化控制台

echo =======================================================
echo 🚀 QKA (快量化) 可视化量化投研控制台启动工具 (Windows)
echo =======================================================

set PYTHON_BIN=python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    where py >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo ❌ 错误: 未检测到 Python，请先安装 Python 3.10+ 并勾选 Add to PATH
        pause
        exit /b 1
    ) else (
        set PYTHON_BIN=py
    )
)

echo 🐍 使用 Python: %PYTHON_BIN%
echo 🌐 正在启动 Web 控制台 (http://127.0.0.1:15002)...
start http://127.0.0.1:15002
%PYTHON_BIN% console\server.py %*
pause
