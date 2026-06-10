@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
setlocal
cd /d "%~dp0"

echo ========================================
echo Environment bootstrap / dependency install
echo ========================================
echo.

where powershell >nul 2>nul
if not "%ERRORLEVEL%"=="0" (
  echo PowerShell was not found on this computer.
  echo Please install Windows PowerShell or PowerShell, then run again.
  echo.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_env_bootstrap.ps1"
set "SETUP_EXIT=%ERRORLEVEL%"

echo.
echo ========================================
echo Setup process exited with code: %SETUP_EXIT%
echo Press any key to close this window.
echo ========================================
pause >nul
exit /b %SETUP_EXIT%
