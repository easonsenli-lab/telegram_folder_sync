@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ========================================
echo QuickQ / Telegram network diagnostics
echo No Python required
echo ========================================
echo.

where powershell >nul 2>nul
if not "%ERRORLEVEL%"=="0" (
  echo PowerShell was not found on this computer.
  echo Cannot run diagnostics.
  echo.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0quickq_network_check.ps1"
set "CHECK_EXIT=%ERRORLEVEL%"

echo.
echo ========================================
echo Diagnostic exited with code: %CHECK_EXIT%
echo Press any key to close.
echo ========================================
pause >nul
exit /b %CHECK_EXIT%
