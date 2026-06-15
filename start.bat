@echo off
chcp 65001 >nul 2>&1
title WeChatBot v2.0
setlocal enabledelayedexpansion

echo ============================================================
echo   WeChatBot v2.0 - Windows 快速启动脚本
echo ============================================================
echo.

REM ──────────────────────────────────────────────
REM 1. 检查 Python
REM ──────────────────────────────────────────────
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] 未找到 Python！请先安装 Python 3.11
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时务必勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

REM 检查 Python 版本
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python %PYVER%

REM 检查 Python 版本是否 3.9~3.11
python -c "import sys; exit(0 if (3,9) <= (sys.version_info.major, sys.version_info.minor) <= (3,11) else 1)" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Python 版本可能不兼容！wcferry 推荐 Python 3.9~3.11
    echo 当前版本: %PYVER%
    echo.
)

REM ──────────────────────────────────────────────
REM 2. 创建/激活虚拟环境
REM ──────────────────────────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] 正在创建虚拟环境...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] 创建虚拟环境失败！
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境已创建
)

call .venv\Scripts\activate.bat

REM ──────────────────────────────────────────────
REM 3. 安装/检查依赖
REM ──────────────────────────────────────────────
python -c "import wcferry" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] 正在安装依赖（使用清华镜像加速）...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %ERRORLEVEL% NEQ 0 (
        echo [WARNING] 清华镜像安装失败，尝试阿里云镜像...
        pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
    )
) else (
    echo [OK] 依赖已安装
)

REM ──────────────────────────────────────────────
REM 4. 检查数据目录
REM ──────────────────────────────────────────────
if not exist "data" mkdir data

REM ──────────────────────────────────────────────
REM 5. 检查配置文件
REM ──────────────────────────────────────────────
if not exist "config.yaml" (
    echo [INFO] 配置文件不存在，正在生成默认配置...
    python main.py --init
    echo.
    echo [重要] 请先编辑 config.yaml 修改以下配置后再启动：
    echo   1. webhook.token  - 修改为随机字符串（必须！）
    echo   2. group_filter.mode - 可先设为 "all" 监控所有群
    echo.
    notepad config.yaml
    echo.
    echo 配置修改完毕后，重新运行 start.bat
    pause
    exit /b 0
)

REM ──────────────────────────────────────────────
REM 6. 解析命令行参数
REM ──────────────────────────────────────────────
set CONFIG=config.yaml
set ACTION=start

:parse_args
if "%1"=="" goto end_parse
if "%1"=="--check" set ACTION=check
if "%1"=="--init" set ACTION=init
if "%1"=="-c" (
    set CONFIG=%2
    shift
)
shift
goto parse_args
:end_parse

REM ──────────────────────────────────────────────
REM 7. 执行操作
REM ──────────────────────────────────────────────
echo.

if "%ACTION%"=="check" (
    echo [INFO] 检查微信登录状态...
    echo.
    python main.py --check -c %CONFIG%
    echo.
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo [排查建议]
        echo   1. 确认微信已打开并登录
        echo   2. 确认微信版本为 3.9.12.51
        echo   3. 以管理员权限运行此脚本
    )
) else if "%ACTION%"=="init" (
    echo [INFO] 生成默认配置文件...
    python main.py --init -c %CONFIG%
    echo.
    echo [重要] 请编辑 %CONFIG% 修改配置后再启动！
    notepad %CONFIG%
) else (
    echo [INFO] 正在启动 WeChatBot...
    echo [INFO] 配置文件: %CONFIG%
    echo [INFO] 按 Ctrl+C 停止
    echo ============================================================
    echo.
    python main.py -c %CONFIG%
    
    REM 异常退出检测
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo [WARNING] Bot 异常退出，退出码: %ERRORLEVEL%
        echo.
        echo [排查建议]
        echo   1. 检查微信是否已登录
        echo   2. 检查微信版本是否为 3.9.12.51
        echo   3. 检查 config.yaml 配置是否正确
        echo   4. 查看日志: data\wechat_bot.log
        echo   5. 以管理员权限重新运行
    )
)

echo.
pause
