@echo off
REM Schedule this file in Windows Task Scheduler to run daily at midnight.
cd /d "%~dp0.."
call venv\Scripts\activate.bat
python manage.py expire_memberships
