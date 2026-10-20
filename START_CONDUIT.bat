@echo off
setlocal
title Conduit - Local Demo
pushd "%~dp0"
if errorlevel 1 exit /b 1

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-demo.ps1" %*
set "CONDUIT_EXIT=%ERRORLEVEL%"
if not "%CONDUIT_EXIT%"=="0" (
    echo.
    echo Conduit could not start. Read the message above.
    echo Logs are in the .local folder. No existing data was reset.
    pause
)
popd
exit /b %CONDUIT_EXIT%
