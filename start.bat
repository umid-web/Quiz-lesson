@echo off
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.10 yoki yangiroq versiyasini ornating va Add Python to PATH ni belgilang.
  pause
  exit /b 1
)
if not exist "data\quiz.sqlite3" (
  python setup_admin.py
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
python server.py
pause
