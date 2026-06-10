@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
setlocal
cd /d "%~dp0"

echo ========================================
echo Telegram login / account check
echo ========================================
echo.

call "%~dp0_ensure_runtime.cmd"
if not "%ERRORLEVEL%"=="0" (
  echo.
  echo Environment is not ready. Press any key to close.
  pause >nul
  exit /b 1
)

".venv\Scripts\python.exe" ".\account_login.py"

echo.
echo ========================================
echo Finished. Press any key to close.
echo ========================================
pause >nul
