@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Этот файл запускает планировщик Windows. Выполняет только то, чьё время пришло и что ещё не сделано сегодня.
.venv\Scripts\python -m crm_notify due
