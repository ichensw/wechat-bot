@echo off
chcp 65001 >nul 2>&1
title WeChatBot v2.0

echo ============================================================
echo   WeChatBot v2.0 - Windows 快速启动脚本
echo ============================================================
echo.

REM Check Python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found! Please install Python 3.11
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check venv
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
) else (
    call .venv\Scripts\activate.bat
)

REM Check data directory
if not exist "data" mkdir data

REM Parse arguments
set CONFIG=config.yaml
set ACTION=start

:parse_args
if "%1"=="--check" set ACTION=check
if "%1"=="--init" set ACTION=init
if "%1"=="-c" (
    set CONFIG=%2
    shift
)
shift
if not "%1"=="" goto parse_args

REM Execute
if "%ACTION%"=="check" (
    echo [INFO] Checking WeChat login status...
    python main.py --check -c %CONFIG%
) else if "%ACTION%"=="init" (
    echo [INFO] Creating default config...
    python main.py --init -c %CONFIG%
    echo [INFO] Edit %CONFIG% before starting the bot!
) else (
    echo [INFO] Starting WeChatBot...
    echo [INFO] Config: %CONFIG%
    echo [INFO] Press Ctrl+C to stop
    echo.
    python main.py -c %CONFIG%
)

pause
