@echo off
chcp 65001 >nul
echo ============================================
echo   Itranslation — Shortcut Installer
echo ============================================
echo.

set "VBS=%~dp0book-translation.vbs"
set "DESKTOP=%USERPROFILE%\Desktop\Itranslation.vbs"

if not exist "%VBS%" (
    echo [ERROR] book-translation.vbs not found.
    echo         Expected: %VBS%
    pause
    exit /b 1
)

echo Target: %VBS%
echo.

choice /C YN /M "Install desktop shortcut?"
if errorlevel 2 goto :skip
if errorlevel 1 goto :install

:install
copy /Y "%VBS%" "%DESKTOP%" >nul
if exist "%DESKTOP%" (
    echo [OK] Shortcut created on Desktop: Itranslation.vbs
) else (
    echo [ERROR] Failed to create shortcut. Try running as Administrator.
)
goto :done

:skip
echo Skipped.

:done
echo.
echo After installation, double-click Itranslation.vbs on your Desktop.
echo The GUI will launch without a terminal window.
echo.
pause
