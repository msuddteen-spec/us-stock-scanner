@echo off
setlocal
title US Paper Trading MVP
cd /d "%~dp0"

echo ==========================================
echo   US Paper Trading MVP - PAPER MODE ONLY
echo ==========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creating local Python environment...
    python -m venv .venv
    if errorlevel 1 goto :python_error
)

if not exist ".env" (
    echo Creating .env from .env.example...
    copy /Y ".env.example" ".env" >nul
    echo.
    echo Please edit .env and add your Alpaca PAPER API keys before using paper-scan.
    echo The dashboard can still open without keys.
    echo.
)

echo Installing or updating dashboard dependencies...
.venv\Scripts\python.exe -m pip install -e ".[dashboard,alpaca]"
if errorlevel 1 goto :install_error

echo.
echo Opening dashboard. Close this window to stop it.
.venv\Scripts\python.exe -m streamlit run dashboard_app.py
goto :end

:python_error
echo.
echo Python 3.11 or newer is required. Please install Python and try again.
pause
goto :end

:install_error
echo.
echo Dependency installation failed. Check your internet connection and try again.
pause

:end
endlocal
