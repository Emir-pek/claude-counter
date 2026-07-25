@echo off
setlocal
cd /d "%~dp0"

REM --- Find a working Python. Existence is not enough: on Windows the
REM --- "python" command is often the Microsoft Store stub, which opens the
REM --- Store instead of running anything. Executing a no-op filters it out.
set "PY="
py -3 -c "pass" >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if defined PY goto have_python

python -c "pass" >nul 2>&1
if not errorlevel 1 set "PY=python"
if defined PY goto have_python

echo.
echo Python was not found on this computer.
echo.
echo Install Python 3.10 or newer from:
echo     https://www.python.org/downloads/
echo During setup, tick "Add python.exe to PATH".
echo Then run this file again.
echo.
pause
exit /b 1

:have_python
REM --- The completion marker is pythonw.exe, not the .venv folder: a setup
REM --- interrupted halfway leaves the folder behind and would otherwise
REM --- wedge every future launch.
if exist ".venv\Scripts\pythonw.exe" goto run

echo.
echo First run: setting up a local Python environment.
echo This takes a few seconds and happens only once.
echo.
%PY% -m venv .venv
if errorlevel 1 goto setup_failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto setup_failed
if not exist ".venv\Scripts\pythonw.exe" goto setup_failed
echo.
echo Setup complete. Starting Claude Counter...

:run
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

:setup_failed
echo.
echo Setup failed.
echo Check your internet connection, delete the .venv folder,
echo and run this file again.
echo.
pause
exit /b 1
