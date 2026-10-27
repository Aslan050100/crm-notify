@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === crm-notify setup ===
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
%PY% --version
if errorlevel 1 goto nopython
echo.
echo [1/3] Creating .venv ...
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
if not exist .venv\Scripts\python.exe goto novenv
echo [2/3] Installing libraries, 1-3 min, do not close this window ...
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
echo [3/3] Checking ...
.venv\Scripts\python -m crm_notify.install_check
pause
exit /b 0
:nopython
echo Python not found. Install Python 3.11+ from python.org and tick "Add python.exe to PATH".
pause
exit /b 1
:novenv
echo ERROR: could not create .venv - send a screenshot of this window.
pause
exit /b 1
