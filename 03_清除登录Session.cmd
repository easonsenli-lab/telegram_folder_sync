@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
setlocal
cd /d "%~dp0"

echo ========================================
echo Clear Telegram login session
echo ========================================
echo.

call "%~dp0_ensure_runtime.cmd"
if not "%ERRORLEVEL%"=="0" (
  echo.
  echo Environment is not ready. Press any key to close.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" ".\clear_session.py"

echo.
echo ========================================
echo Finished. Press any key to close.
echo ========================================
pause >nul
