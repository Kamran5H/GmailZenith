@echo off
title Gmail Zenith
cd /d "%~dp0"

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" -c "import fastapi, googleapiclient" 2>nul || (
    echo [SETUP] Installing requirements...
    "%PY%" -m pip install -r requirements.txt || goto :error
)

"%PY%" backend\app.py
if errorlevel 1 goto :error
goto :eof

:error
echo.
echo Gmail Zenith stopped with an error. See the message above.
pause
