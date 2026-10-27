@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Установка crm-notify ===
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version || (echo Python не найден. Установите Python 3.11+ с python.org, отметив "Add python.exe to PATH". & pause & exit /b 1)
if not exist .venv %PY% -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip -q
.venv\Scripts\python -m pip install -r requirements.txt -q
if not exist .env copy .env.example .env >nul & echo Создан файл .env — откройте его и впишите токен amoCRM и ключ Wazzup.
echo Готово.
pause
