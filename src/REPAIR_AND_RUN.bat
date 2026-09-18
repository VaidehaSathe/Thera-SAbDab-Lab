@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Repair Thera-SAbDab WHO INN Curator
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS%" set "PS=powershell.exe"
echo Rebuilding the private v1.0.4 environment. Your database is preserved.
echo.
"%PS%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_system_python_setup.ps1" -ForceRepair
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%
