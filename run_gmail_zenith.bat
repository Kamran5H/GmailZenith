@echo off
title Gmail Zenith Pro - AI Inbox Optimizer ^& Triage
cd /d "%~dp0"

echo =======================================================
echo   GMAIL ZENITH PRO - AI INBOX OPTIMIZER & TRIAGE
echo   Kamran Ashraf AI Suite
echo =======================================================
echo.

if exist "..\.venv\Scripts\python.exe" (
    echo [INFO] Starting with virtual environment...
    "..\.venv\Scripts\python.exe" backend\app.py
) else (
    echo [INFO] Starting with Python...
    python backend\app.py
)

pause
