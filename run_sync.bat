@echo off
:: SoCal AI Solutions — Daily Subscriber Sync
:: Called by Windows Task Scheduler every day at 8:00 AM

cd /d "%~dp0"

:: Activate virtual environment if one exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: Ensure log directory exists
if not exist "data\logs" mkdir "data\logs"

:: Run subscriber sync — stdout + stderr go to the sync log file
python main.py --sync >> "data\logs\sync.log" 2>&1

exit /b %errorlevel%
