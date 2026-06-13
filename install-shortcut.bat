@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   Itranslation — 桌面快捷方式安装器
echo ============================================
echo.

set "PROJECT_DIR=%~dp0"
set "DESKTOP=%USERPROFILE%\Desktop"
set "LINK=%DESKTOP%\Itranslation.lnk"

:: 查找 uv 路径
for /f "delims=" %%i in ('where uv 2^>nul') do set "UV_PATH=%%i"
if "%UV_PATH%"=="" (
    echo [ERROR] 未找到 uv. 请先安装: pip install uv
    pause
    exit /b 1
)

echo   目标:  %PROJECT_DIR%desktop.py
echo   uv:     %UV_PATH%
echo.

:: 使用 PowerShell 创建 .lnk
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%LINK%'); $s.TargetPath = '%UV_PATH%'; $s.Arguments = 'run python desktop.py'; $s.WorkingDirectory = '%PROJECT_DIR%'; $s.WindowStyle = 7; $s.Description = 'Itranslation - AI 全书翻译'; $s.Save()"

if exist "%LINK%" (
    echo [OK] 快捷方式已创建: %LINK%
    echo       双击即可启动 (无终端窗口^)
) else (
    echo [ERROR] 创建失败
)

echo.
pause
