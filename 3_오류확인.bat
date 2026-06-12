@echo off
chcp 65001 >nul
cd /d "%~dp0"
title GPC IP Lens - 오류 확인

echo ============================================
echo  GPC IP Lens 환경 점검
echo ============================================
echo.

echo [1] Python 확인
python --version
if errorlevel 1 echo  - Python이 설치되어 있지 않습니다.
echo.

echo [2] 가상환경 확인
if exist venv (echo  - 가상환경 있음) else (echo  - 가상환경 없음: "1_처음설치.bat"을 먼저 실행하세요.)
echo.

if exist venv call venv\Scripts\activate.bat

echo [3] 설치된 프로그램 확인
pip list 2>nul | findstr /i "streamlit pandas requests openpyxl python-dotenv"
echo.

echo [4] 설정 파일 확인
if exist .env (echo  - .env 있음) else (echo  - .env 없음: .env.example을 복사해 .env를 만드세요.)
echo.

echo [5] 프로그램 불러오기 점검 (오류가 있으면 아래에 표시됩니다)
python -c "import app" > 오류로그.txt 2>&1
if errorlevel 1 (
    echo  - 오류가 발견되었습니다. 내용:
    type 오류로그.txt
) else (
    echo  - 정상입니다.
)
echo.
echo 점검 결과는 "오류로그.txt" 파일에서도 확인할 수 있습니다.
pause
