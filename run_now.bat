@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Run scenarios right now (mode from .env: test or live). Example: run_now.bat --date 2026-11-05
.venv\Scripts\python -m crm_notify run %*
pause
