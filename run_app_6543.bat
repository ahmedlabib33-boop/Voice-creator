@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul || (
    echo Python was not found on PATH. Install Python 3.10+ and try again.
    pause & exit /b 1
)

python -c "import streamlit, anthropic, groq, openai, dotenv, requests" >nul 2>nul || (
    echo Installing dependencies...
    python -m pip install -r requirements.txt || (pause & exit /b 1)
)

where ffmpeg >nul 2>nul || echo WARNING: ffmpeg not found on PATH. Install it: winget install Gyan.FFmpeg

if not exist ".env" copy /y ".env.example" ".env" >nul

set "HAVE_KEYS="
if exist "keys.txt" set "HAVE_KEYS=1"
if exist "..\API keys.txt" set "HAVE_KEYS=1"
if exist "..\API keys" set "HAVE_KEYS=1"
if not defined HAVE_KEYS (
    copy /y "keys.example.txt" "keys.txt" >nul
    echo Created keys.txt - paste your Claude and Groq keys into it, save, then close Notepad.
    notepad "keys.txt"
)

echo Starting on http://127.0.0.1:6543
python -m streamlit run app.py --server.port 6543 --server.address 127.0.0.1 --server.headless true
endlocal
