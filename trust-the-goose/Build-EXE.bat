@echo off
title Paranoid Penguin - Build standalone EXE
cd /d "%~dp0"
echo.
echo   This packages Paranoid Penguin into ONE .exe file so it can be
echo   shared with people who don't have Python installed.
echo.
echo   It installs PyInstaller (once), then builds. Takes a few minutes.
echo.
pause

pip install pyinstaller

pyinstaller --onefile --name ParanoidPenguin ^
  --collect-submodules pandas ^
  --hidden-import real_feeds --hidden-import scan_pc --hidden-import audit_python ^
  --hidden-import harden_audit --hidden-import scan_startup --hidden-import scan_logins ^
  --hidden-import scan_network --hidden-import scan_connections --hidden-import scan_wifi ^
  --hidden-import build_my_dashboard --hidden-import grade ^
  control_panel.py

echo.
if exist "dist\ParanoidPenguin.exe" (
  echo   SUCCESS. Your app is at:  dist\ParanoidPenguin.exe
  echo   Double-click it to run — no Python needed.
  echo.
  echo   NOTE: the "Audit my apps" check still needs Python on the machine,
  echo   because it inspects a Python install. Every other check works standalone.
) else (
  echo   Build did not finish. Scroll up for the error, or paste it to Claude.
)
echo.
pause
