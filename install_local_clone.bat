@echo off
setlocal
cd /d "%~dp0"
echo Installing the free local voice-cloning model (Coqui XTTS v2). This downloads about 2 GB on first use.
python -m pip install -r requirements-clone.txt || (echo Install failed. Python 3.10 - 3.14 is required. & pause & exit /b 1)
echo Done. Start the app with run_app_6543.bat and open the Voice lab tab.
pause
endlocal
