#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -c "import streamlit, anthropic, groq, openai, dotenv, requests" 2>/dev/null || python3 -m pip install -r requirements.txt
command -v ffmpeg >/dev/null || echo "WARNING: ffmpeg not found on PATH."
[ -f .env ] || cp .env.example .env
[ -f keys.txt ] || [ -f "../API keys.txt" ] || [ -f "../API keys" ] || { cp keys.example.txt keys.txt; echo "Created keys.txt - paste your Claude and Groq keys into it."; }
echo "Starting on http://127.0.0.1:6543"
python3 -m streamlit run app.py --server.port 6543 --server.address 127.0.0.1 --server.headless true
