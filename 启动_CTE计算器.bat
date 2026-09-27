@echo off
chcp 65001 >nul
title CompModel
cd /d "%~dp0"

echo ============================================
echo   CompModel 复合材料有效性能建模
echo   Composite Effective Properties
echo ============================================
echo.
echo 工作目录: %CD%
echo 正在启动 Streamlit ...
echo 关闭本窗口将停止程序。
echo.

where py >nul 2>&1
if %ERRORLEVEL%==0 (
    py -3 -c "import streamlit" 1>nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo [提示] 未检测到 streamlit，请先双击「首次安装依赖.bat」
        echo.
        pause
        exit /b 1
    )
    py -3 -m streamlit run app.py --server.headless false
    goto :after
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
    python -c "import streamlit" 1>nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo [提示] 未检测到 streamlit，请先双击「首次安装依赖.bat」
        echo.
        pause
        exit /b 1
    )
    python -m streamlit run app.py --server.headless false
    goto :after
)

echo [错误] 未找到 Python。
echo 1^) 安装 Python 3.10+ 并加入 PATH
echo 2^) 双击 首次安装依赖.bat 或 install_deps.bat
echo 3^) 再运行本脚本
echo.
pause
exit /b 1

:after
if %ERRORLEVEL% neq 0 (
    echo.
    echo [错误] 启动失败。请先运行「首次安装依赖.bat」
    echo 或在本目录执行:  py -3 -m pip install -r requirements.txt
    echo.
    pause
)
exit /b %ERRORLEVEL%
