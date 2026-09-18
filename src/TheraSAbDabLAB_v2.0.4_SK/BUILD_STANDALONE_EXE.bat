@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Build Thera-SAbDab WHO INN Curator Standalone EXE

echo ============================================================
echo  Build standalone Windows application v1.0.4
echo ============================================================
echo This uses your installed Python only to create a private build
echo environment. Your system Python packages are not modified.
echo.

set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS%" set "PS=powershell.exe"
"%PS%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo BUILD FAILED - error code %RC%
  echo Run DIAGNOSE_WINDOWS.bat for details.
  pause
)
exit /b %RC%
