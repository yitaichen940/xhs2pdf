@echo off
cd /d "%~dp0"

echo [%date% %time%] Starting... > xhs2pdf.log

set PY=
where python  >/dev/null 2>&1 && set PY=python
where python3 >/dev/null 2>&1 && if "%PY%"=="" set PY=python3
where py      >/dev/null 2>&1 && if "%PY%"=="" set PY=py

if "%PY%"=="" (
    echo Python NOT FOUND >> xhs2pdf.log
    start https://www.python.org/downloads/
    echo.
    echo Python not found.
    echo Please install Python 3.7+, check Add to PATH.
    echo.
    pause
    exit /b
)

echo Python: %PY% >> xhs2pdf.log

echo Checking dependencies...
"%PY%" -c "import requests, PIL, tqdm, bs4, fpdf" >/dev/null 2>&1
if %errorlevel% neq 0 (
    echo Installing dependencies... >> xhs2pdf.log
    echo Installing Python packages (about 16MB, one-time)...
    "%PY%" -m pip install -q requests Pillow tqdm beautifulsoup4 fpdf2
    echo Done.
)

echo Launching... >> xhs2pdf.log
start "" Æô¶¯.vbs