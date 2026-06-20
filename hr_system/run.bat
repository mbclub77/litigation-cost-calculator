@echo off
echo.
echo  ================================================
echo   HR Management System for Labor Attorneys
echo  ================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found.
    echo  Install from https://www.python.org (check Add to PATH)
    pause >nul
    exit /b 1
)

echo  [1/2] Installing dependencies...
pip install flask flask-cors -q
if errorlevel 1 (
    echo  [ERROR] pip install failed. Check internet connection.
    pause >nul
    exit /b 1
)

echo  [2/2] Starting server...
echo.
echo  Open browser: http://127.0.0.1:5050
echo  Press Ctrl+C to stop.
echo.
start "" "http://127.0.0.1:5050"
python "%~dp0app.py"
pause >nul
