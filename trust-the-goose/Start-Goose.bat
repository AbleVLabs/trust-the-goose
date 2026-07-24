@echo off
title Trust the Goose
cd /d "%~dp0"
echo.
echo   TRUST THE GOOSE - golf caddie
echo.
echo   Starting... a browser will open at http://127.0.0.1:5000
echo   Keep this window open while you use it. Close it to stop.
echo.
rem install deps from the pinned list; show errors instead of hiding them
pip install -r requirements.txt
rem open the browser AFTER the server has had a few seconds to boot --
rem opening it first just shows "connection refused"
start "" cmd /c "timeout /t 3 >nul & start "" http://127.0.0.1:5000"
python app.py
pause
