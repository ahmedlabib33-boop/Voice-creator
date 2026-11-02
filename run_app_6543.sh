#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -c "import streamlit, groq, openai, dotenv, requests" 2>/dev/null || python3 -m pip install -r requirements.txt
command -v ffmpeg >/dev/null || echo "WARNING: ffmpeg not found on PATH."
[ -f .env ] || { echo "No .env found. Copying .env.example to .env - paste your real keys into it."; cp .env.example .env; }
echo "Starting on http://127.0.0.1:6543"
python3 -m streamlit run app.py --server.port 6543 --server.address 127.0.0.1 --server.headless true
