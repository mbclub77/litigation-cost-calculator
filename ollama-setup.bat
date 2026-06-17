@echo off
echo.
echo  ================================================
echo   Ollama Korean AI Spell Checker Setup
echo  ================================================
echo.
echo  [Step 1] Opening Ollama download page...
echo           Install it, then come back to this window.
echo.
start "" "https://ollama.com/download/windows"
echo  After installation finishes, press any key to continue.
pause >nul
echo.
echo  [Step 2] Downloading Korean AI model (qwen2.5:7b, ~4.7GB)
echo           This may take a while. Please wait.
echo.
ollama pull qwen2.5:7b
if errorlevel 1 (
    echo.
    echo  [ERROR] 'ollama' command not found.
    echo          Make sure Ollama installation is complete,
    echo          then close this window and open a NEW cmd
    echo          window and run this file again.
    echo.
    pause >nul
    exit /b 1
)
echo.
echo  ================================================
echo   Done! Now open spellchecker-pro.html in your
echo   browser. The AI badge will connect automatically.
echo  ================================================
echo.
pause >nul
