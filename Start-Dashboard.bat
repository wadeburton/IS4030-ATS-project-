@echo off
rem Double-click this file to install what is needed, sign in to Databricks, and open the ATS dashboard.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Dashboard.ps1" %*
if errorlevel 1 pause
