@echo off
chcp 65001 >nul
echo.
echo  ================================================
echo   Ollama 한국어 AI 맞춤법 검사 환경 설정
echo  ================================================
echo.
echo [1단계] Ollama 공식 설치 페이지를 엽니다...
echo         설치 후 이 창으로 돌아오세요.
echo.
start "" "https://ollama.com/download/windows"
pause
echo.
echo [2단계] 한국어 AI 모델 다운로드 (qwen2.5:7b, 약 4.7GB)
echo         시간이 걸립니다. 완료될 때까지 기다리세요.
echo.
ollama pull qwen2.5:7b
if errorlevel 1 (
    echo.
    echo [오류] ollama 명령어를 찾을 수 없습니다.
    echo        Ollama 설치가 완료됐는지 확인하고 이 창을 닫은 후
    echo        새 cmd 창에서 다시 실행하세요.
    pause
    exit /b 1
)
echo.
echo  ================================================
echo   설치 완료! 이제 spellchecker-pro.html 을 열면
echo   자동으로 AI 연결됩니다.
echo  ================================================
echo.
pause
