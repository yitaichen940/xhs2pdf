@echo off
cd /d "%~dp0"
echo [%date% %time%] Starting... > xhs2pdf.log
set PY=

python --version >/dev/null 2>&1
if not errorlevel 1 set PY=python
if "%PY%"=="" python3 --version >/dev/null 2>&1 && set PY=python3
if "%PY%"=="" py --version >/dev/null 2>&1 && set PY=py
if "%PY%"=="" if exist "D:\tools\Python12\python.exe" set PY=D:\tools\Python12\python.exe
if "%PY%"=="" if exist "C:\Python312\python.exe" set PY=C:\Python312\python.exe

if "%PY%"=="" (
    echo Python NOT FOUND
    start https://www.python.org/downloads/
    pause
    exit /b
)

echo Python: %PY% >> xhs2pdf.log

"%PY%" -c "import requests, PIL, tqdm, bs4, fpdf" >/dev/null 2>&1
if errorlevel 1 (
    echo Installing packages...
    "%PY%" -m pip install -q requests Pillow tqdm beautifulsoup4 fpdf2
)

echo Launching... >> xhs2pdf.log
start "" Æô¶¯.vbs