@echo off
echo.
echo  ================================================
echo   Korean Spell Checker (Naver Engine)
echo  ================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python is not installed.
    echo          Please install Python 3.8+ from https://www.python.org
    echo          Make sure to check "Add Python to PATH" during install.
    pause >nul
    exit /b 1
)

echo  [1/2] Installing py-hanspell (first run only)...
pip install py-hanspell -q
if errorlevel 1 (
    echo  [ERROR] pip install failed. Check your internet connection.
    pause >nul
    exit /b 1
)

echo  [2/2] Launching spell checker...
echo.
python "%~dp0spellcheck_app.py"

if errorlevel 1 (
    echo.
    echo  [ERROR] App crashed. See message above.
    pause >nul
)
