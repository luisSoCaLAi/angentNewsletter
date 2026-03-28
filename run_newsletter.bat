@echo off
:: SoCal AI Solutions — Newsletter Agent Runner
:: Called by Windows Task Scheduler every Tuesday at 9:00 AM

cd /d "%~dp0"

:: Activate virtual environment if one exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: Ensure log directory exists
if not exist "data\logs" mkdir "data\logs"

:: Run the agent — stdout + stderr go to the weekly log file
:: Python prints the timestamp, so the log is self-describing
python main.py >> "data\logs\newsletter.log" 2>&1

exit /b %errorlevel%
