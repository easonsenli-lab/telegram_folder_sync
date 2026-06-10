@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
setlocal
cd /d "%~dp0"

echo ========================================
echo Telegram network diagnostics
echo ========================================
echo.

call "%~dp0_ensure_runtime.cmd"
if not "%ERRORLEVEL%"=="0" (
  echo.
  echo Environment is not ready. Press any key to close.
  pause >nul
  exit /b 1
)

if not exist "logs" mkdir "logs"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "LOG_TS=%%i"
set "LOG_FILE=logs\network-%LOG_TS%.log"

".venv\Scripts\python.exe" ".\network_check.py" > "%LOG_FILE%" 2>&1
set "CHECK_EXIT=%ERRORLEVEL%"
type "%LOG_FILE%"

echo.
echo ========================================
echo Diagnostic log: %LOG_FILE%
echo Finished. Press any key to close.
echo ========================================
pause >nul
exit /b %CHECK_EXIT%
