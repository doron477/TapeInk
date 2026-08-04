@echo off
rem Debug launcher — keeps the console open so errors are visible.
rem For everyday use prefer TapeInk.lnk (no console window).
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python app.py
pause
