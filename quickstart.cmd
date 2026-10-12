@echo off
rem EPMTS: double-click to start. Installs what is missing on first start, then opens the home window.
rem Advanced: quickstart.cmd editor [pack folder]  /  quickstart.cmd server [pack folder]
title EPMTS
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\setup\setup.ps1" %*
if errorlevel 1 pause
