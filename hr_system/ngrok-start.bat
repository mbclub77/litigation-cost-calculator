@echo off
echo ============================================
echo  HR System - ngrok External Access
echo ============================================
echo.
echo [1] Starting Flask server in background...
start /min cmd /c "python app.py"
timeout /t 2 /nobreak >nul

echo [2] Opening ngrok tunnel (port 5050)...
echo.
echo When ngrok shows a URL like:
echo   https://xxxx-xx-xx.ngrok-free.app
echo Share that URL with your clients!
echo.
ngrok http 5050
echo.
echo ngrok stopped. Press any key to exit.
pause >nul
