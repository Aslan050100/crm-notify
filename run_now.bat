@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Выполнить сценарии прямо сейчас (в режиме из .env: test или live)
.venv\Scripts\python -m crm_notify run %*
pause
