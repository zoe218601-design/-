@echo off
cd /d "%~dp0"
where python >nul 2>nul
if not errorlevel 1 (
    python cat.py
) else (
    py cat.py
)
if errorlevel 1 (
    echo.
    echo Could not start. Please run install.bat first.
    pause
)
