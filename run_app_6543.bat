@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul || (
    echo Python was not found on PATH. Install Python 3.10+ and try again.
    pause & exit /b 1
)

python -c "import streamlit, groq, openai, dotenv, requests" >nul 2>nul || (
    echo Installing dependencies...
    python -m pip install -r requirements.txt || (pause & exit /b 1)
)

where ffmpeg >nul 2>nul || echo WARNING: ffmpeg not found on PATH. Install it: winget install Gyan.FFmpeg

if not exist ".env" (
    echo No .env found. Copying .env.example to .env - paste your real keys into it.
    copy /y ".env.example" ".env" >nul
)

echo Starting on http://127.0.0.1:6543
python -m streamlit run app.py --server.port 6543 --server.address 127.0.0.1 --server.headless true
endlocal
