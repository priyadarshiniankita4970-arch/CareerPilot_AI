@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  py -m venv .venv
  if errorlevel 1 goto error
)
call ".venv\Scripts\activate.bat"
echo Installing project requirements...
python -m pip install -r requirements.txt
if errorlevel 1 goto error
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env from .env.example. Review JWT_SECRET and MongoDB settings.
)
echo.
echo Make sure MongoDB is running before continuing.
echo Seed demo jobs, recruiter, and admin accounts now? (Y/N)
set /p seedchoice=Choice:
if /I "%seedchoice%"=="Y" (
  python seed_demo_data.py
  if errorlevel 1 goto error
)
echo.
echo Starting CareerPilot AI at http://127.0.0.1:8000
python -m uvicorn app.main:app --reload
goto end
:error
echo.
echo Setup failed. Read the error above and check README.md.
pause
:end
endlocal
