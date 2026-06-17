@echo off
echo.
echo  ================================================
echo   Fix Ollama connection for the spell checker
echo   (allow browser requests via OLLAMA_ORIGINS)
echo  ================================================
echo.
echo  [1/3] Setting OLLAMA_ORIGINS=* permanently...
setx OLLAMA_ORIGINS "*"
echo.
echo  [2/3] Stopping any running Ollama...
taskkill /F /IM ollama.exe >nul 2>&1
taskkill /F /IM "ollama app.exe" >nul 2>&1
timeout /t 2 /nobreak >nul
echo.
echo  [3/3] Starting Ollama with the new setting...
set OLLAMA_ORIGINS=*
start "" ollama serve
timeout /t 3 /nobreak >nul
echo.
echo  ================================================
echo   Done! Keep this running, then refresh
echo   spellchecker-pro.html in your browser.
echo   The AI badge should turn green within ~15 sec.
echo  ================================================
echo.
pause >nul
