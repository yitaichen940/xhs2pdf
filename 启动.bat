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
    echo Python not found.
    echo Please install Python 3.8+ (check 'Add to PATH' during install)
    echo The download page has been opened for you.
    echo.
    pause
    exit /b
)

echo Using: %PY% >> xhs2pdf.log

where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    echo Using pythonw (no console) >> xhs2pdf.log
    start "" pythonw -m src.main
) else (
    echo Using python (console) >> xhs2pdf.log
    start "" %PY% -m src.main
)
