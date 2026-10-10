@echo off
cd /d "%~dp0"
where python >nul 2>nul
if not errorlevel 1 (
    python -m pip install -r requirements.txt
) else (
    py -m pip install -r requirements.txt
)
pause
