@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-ogma.ps1"
if errorlevel 1 (
  echo.
  echo Production server failed. Review the message above.
  pause
)
