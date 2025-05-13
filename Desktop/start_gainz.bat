@echo off
echo Starting Gainz Workout Tracker...

:: Navigate to project directory
cd C:\Users\Elmar\buffdaddy\gymapp

py -3.12 -m venv venv_new

:: Add PostgreSQL to PATH (temporary fix until reboot makes it permanent)
set PATH=%PATH%;C:\Program Files\PostgreSQL\17\bin

:: Start the development server
python manage.py runserver

:: Keep window open if there's an error
pause