@echo off
setlocal
cd /d "%~dp0"
title IP3 (IP Cube)

echo ============================================================
echo   IP3 (IP Cube) - Idea to Patent Intelligence
echo ============================================================
echo.

rem find python command (prefer py launcher)
set "PY=python"
where py >nul 2>nul && set "PY=py"

%PY% --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not installed.
    echo         Install Python 3.11+ from https://www.python.org/downloads
    echo         On the first install screen, check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

rem first run only: install required packages if streamlit is missing
%PY% -c "import streamlit" >nul 2>nul
if errorlevel 1 (
    echo First run: installing required components. This may take a few minutes...
    echo.
    %PY% -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Install failed. Check your internet connection and retry.
        pause
        exit /b 1
    )
)

echo.
echo The browser will open shortly. Close this window to stop the app.
echo.
%PY% -m streamlit run app.py
pause
