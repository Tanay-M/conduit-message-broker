@echo off
setlocal
title Conduit - Stop Local Services
pushd "%~dp0"
if errorlevel 1 exit /b 1

if not exist ".venv\Scripts\python.exe" (
    echo No configured Conduit environment was found in this folder.
    popd
    exit /b 0
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1"
set "CONDUIT_EXIT=%ERRORLEVEL%"
if not "%CONDUIT_EXIT%"=="0" (
    echo.
    echo Some services could not stop. Check .local logs.
    pause
) else (
    echo Conduit services stopped. Your database and reports are saved.
)
popd
exit /b %CONDUIT_EXIT%
