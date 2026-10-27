@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Started by Windows Task Scheduler: runs only what is due today and not yet done.
.venv\Scripts\python -m crm_notify due
