@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-ogma-dev.ps1"
if errorlevel 1 (
  echo.
  echo DEV server failed. Review the message above.
  pause
)
