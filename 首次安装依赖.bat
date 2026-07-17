@echo off
chcp 65001 >nul
title CTE Calculator - Install dependencies
cd /d "%~dp0"

echo ============================================
echo   首次安装依赖 / Install dependencies
echo ============================================
echo 目录: %CD%
echo.

where py >nul 2>&1
if %ERRORLEVEL%==0 (
    echo 使用: py -3 -m pip ...
    py -3 -m pip install --upgrade pip
    py -3 -m pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 goto fail
    echo.
    echo [成功] 依赖已安装。请双击「启动_CTE计算器.bat」
    pause
    exit /b 0
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
    echo 使用: python -m pip ...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 goto fail
    echo.
    echo [成功] 依赖已安装。请双击「启动_CTE计算器.bat」
    pause
    exit /b 0
)

echo [错误] 未找到 Python。
echo 请先安装 Python 3.10+ 并勾选 "Add python.exe to PATH"
echo 下载: https://www.python.org/downloads/
echo.
pause
exit /b 1

:fail
echo.
echo [错误] pip 安装失败。请检查网络后重试。
pause
exit /b 1
