@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import pathlib, sys; expected=pathlib.Path(r'%CD%\.venv').resolve(); actual=pathlib.Path(sys.prefix).resolve(); raise SystemExit(0 if actual == expected else 99)" >nul 2>nul
  if "%ERRORLEVEL%"=="0" (
    exit /b 0
  )
)

echo Runtime is missing, incomplete, or copied from another computer.
echo Please run this file first:
echo 00_检测环境并安装依赖.cmd
echo.
exit /b 1
