@echo off
rem Start the translate bot supervisor (hidden, single instance).
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0service_runner.py"
echo Translate bot supervisor started.
