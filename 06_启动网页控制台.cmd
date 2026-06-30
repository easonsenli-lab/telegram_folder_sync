@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
setlocal
cd /d "%~dp0"

echo ====================================================
echo             Telegram Web Control Panel
echo ====================================================
echo.

call "%~dp0_ensure_runtime.cmd"
if not "%ERRORLEVEL%"=="0" (
  echo.
  echo Environment is not ready. Press any key to close.
  pause >nul
  exit /b 1
)

".venv\Scripts\python.exe" ".\web_server.py"

echo.
echo ====================================================
echo Web server exited. Press any key to close.
echo ====================================================
pause >nul
