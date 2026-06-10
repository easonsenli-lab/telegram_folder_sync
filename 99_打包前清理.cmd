@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ========================================
echo Clean before packaging
echo ========================================
echo.

if exist ".venv" rmdir /s /q ".venv"
if exist "__pycache__" rmdir /s /q "__pycache__"
if exist "sessions" rmdir /s /q "sessions"
if exist "logs" rmdir /s /q "logs"
if exist "state" rmdir /s /q "state"
if exist "data" rmdir /s /q "data"

mkdir accounts
mkdir sessions
mkdir logs
mkdir state
mkdir data

echo Cleaned local runtime files.
echo Do not include .venv in the zip package.
echo.
echo Finished. Press any key to close.
pause >nul
