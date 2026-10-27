@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Установка crm-notify ===
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
%PY% --version || (echo Python не найден. Установите Python 3.11+ с python.org, отметив "Add python.exe to PATH". & pause & exit /b 1)
echo.
echo [1/3] Создаю окружение .venv ...
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
if not exist .venv\Scripts\python.exe (echo ОШИБКА: не удалось создать окружение .venv & pause & exit /b 1)
echo [2/3] Устанавливаю библиотеки (1-3 минуты, не закрывайте окно) ...
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
echo [3/3] Проверяю ...
.venv\Scripts\python -c "import requests, yaml, tzdata; print(Библиотеки установлены)"
if errorlevel 1 (echo. & echo ОШИБКА: библиотеки не установились. Пришлите скрин этого окна. & pause & exit /b 1)
if not exist .env (copy .env.example .env >nul & echo Создан файл .env — откройте его в Блокноте и впишите токен amoCRM и ключ Wazzup.)
echo.
echo ГОТОВО. Дальше: заполните .env и запустите check.bat
pause
