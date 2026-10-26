@echo off
REM Keep this window open — bootstrap handles pause on exit too.
call "%~dp0scripts\bootstrap.bat" app.py
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" exit /b %RC%
