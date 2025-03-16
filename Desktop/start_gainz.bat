@echo off
echo Starting Gainz Workout Tracker...

:: Navigate to project directory
cd C:\gymapp

:: Activate virtual environment
call venv\Scripts\activate

:: Add PostgreSQL to PATH (temporary fix until reboot makes it permanent)
set PATH=%PATH%;C:\Program Files\PostgreSQL\17\bin

:: Start the development server
python manage.py runserver

:: Keep window open if there's an error
pause 