@echo off
chcp 65001 >nul
cd /d "%~dp0"
title GPC IP Lens

if not exist venv (
    echo 먼저 "1_처음설치.bat"을 실행하세요.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo GPC IP Lens를 실행합니다. 잠시 후 브라우저가 열립니다.
echo 종료하려면 이 창을 닫으세요.
streamlit run app.py
pause
