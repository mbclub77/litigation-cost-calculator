@echo off
chcp 65001 >nul
echo.
echo  ============================================
echo   한국어 맞춤법 검사 서버 설치 및 시작
echo  ============================================
echo.

REM Python 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo        https://www.python.org 에서 Python 3.8 이상을 설치하세요.
    pause
    exit /b 1
)

echo [1/2] 필요한 패키지 설치 중...
pip install flask flask-cors requests -q
if errorlevel 1 (
    echo [오류] 패키지 설치 실패. 인터넷 연결을 확인하세요.
    pause
    exit /b 1
)

echo [2/2] 서버 시작 중...
echo.
echo  맞춤법 검사기 HTML 파일을 열면 자동으로 연결됩니다.
echo  이 창을 닫으면 서버가 종료됩니다.
echo.
python spellcheck-server.py
pause
