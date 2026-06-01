@echo off
cd /d "%~dp0"

echo [%date% %time%] Starting... > xhs2pdf.log

set PY=
where python  >nul 2>&1 && set PY=python
where python3 >nul 2>&1 && if "%PY%"=="" set PY=python3
where py      >nul 2>&1 && if "%PY%"=="" set PY=py

if "%PY%"=="" (
    echo Python NOT FOUND >> xhs2pdf.log
    start https://www.python.org/downloads/
    echo.
    echo Python not found. Please install Python 3.7+ (check 'Add to PATH').
    echo Download page opened.
    echo.
    pause
    exit /b
)

echo Python: %PY% >> xhs2pdf.log

:: Check and install dependencies
echo Checking dependencies...
"%PY%" -c "import requests, PIL, tqdm, bs4, fpdf" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing dependencies... >> xhs2pdf.log
    echo Installing Python packages (one time, ~16MB)...
    "%PY%" -m pip install -q requests Pillow tqdm beautifulsoup4 fpdf2
    echo Done.
)

:: Launch
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    echo Using pythonw >> xhs2pdf.log
    start "" pythonw -m src.main
) else (
    echo Using python >> xhs2pdf.log
    start "" %PY% -m src.main
)
