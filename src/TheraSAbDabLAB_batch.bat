@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Thera-SAbDab WHO INN Curator

echo ============================================================
echo  Thera-SAbDab WHO INN Curator - Windows launcher v1.0.4
echo ============================================================
echo.
echo This release uses the Python ALREADY INSTALLED on this PC.
echo It creates an isolated environment under:
echo   %%LOCALAPPDATA%%\TSCurator\venv104
echo It does not modify your system Python packages.
echo.

set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS%" set "PS=powershell.exe"

"%PS%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_system_python_setup.ps1"
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" exit /b 0

echo.
echo ============================================================
echo  STARTUP FAILED - error code %RC%
echo ============================================================
echo The window is being kept open so the error can be read.
echo Run DIAGNOSE_WINDOWS.bat and send the report if needed.
echo Launcher log:
echo   %%LOCALAPPDATA%%\TSCurator\logs\windows_launcher_v104.log
echo.
echo You can also run REPAIR_AND_RUN.bat to rebuild only the private
echo environment. Your application database is not deleted.
echo.
pause
exit /b %RC%
