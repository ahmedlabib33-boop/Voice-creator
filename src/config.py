"""Credential and settings loading.

Values are read, in order, from:
1. A local ``.env`` file next to ``app.py`` (wins over the process environment,
   so a stale empty variable in the shell cannot hide a key saved in the file).
2. The process environment.
3. Streamlit secrets (``.streamlit/secrets.toml``) when running under Streamlit.

Secret values are never logged or displayed; only presence is reported.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = APP_DIR / ".env"
GENERATED_AUDIO_DIR = APP_DIR / "generated_audio"
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "voice_app.db"

AI_DISCLOSURE = "Generated AI voice audio."

DEFAULTS = {
    "GROQ_TTS_MODEL": "canopylabs/orpheus-arabic-saudi",
    "GROQ_TTS_VOICE": "noura",
    "OPENAI_TTS_MODEL": "gpt-4o-mini-tts",
    "OPENAI_TTS_VOICE": "alloy",
    "AZURE_SPEECH_VOICE": "ar-EG-SalmaNeural",
    "WHATSAPP_API_VERSION": "v22.0",
    "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
    "OLLAMA_MODEL": "llama3.1",
}


def load_env_file() -> bool:
    """Load ``.env`` into the process environment. Returns True when a file was read."""
    if not ENV_PATH.exists():
        return False
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependency missing
        return False
    # utf-8-sig strips a BOM that Windows editors/PowerShell often add.
    load_dotenv(ENV_PATH, override=True, encoding="utf-8-sig")
    return True


load_env_file()


def _streamlit_secret(name: str):
    try:
        import streamlit as st  # noqa: WPS433 - optional at import time

        return st.secrets.get(name)  # type: ignore[union-attr]
    except Exception:  # no secrets file, or not running under Streamlit
        return None


def _clean(value) -> str:
    if value is None:
        return ""
    text = str(value).strip().strip('"').strip("'").strip()
    return text


def get_setting(name: str, default: str = "") -> str:
    """Return a setting or ``default`` when it is blank everywhere."""
    value = _clean(os.environ.get(name))
    if not value:
        value = _clean(_streamlit_secret(name))
    if not value:
        value = DEFAULTS.get(name, default)
    return value


def has_setting(name: str) -> bool:
    return bool(_clean(os.environ.get(name)) or _clean(_streamlit_secret(name)))


# --- Voice providers -------------------------------------------------------

def groq_api_key() -> str:
    return get_setting("GROQ_API_KEY")


def groq_tts_model() -> str:
    return get_setting("GROQ_TTS_MODEL")


def groq_tts_voice() -> str:
    return get_setting("GROQ_TTS_VOICE")


def openai_api_key() -> str:
    return get_setting("OPENAI_API_KEY")


def openai_tts_model() -> str:
    return get_setting("OPENAI_TTS_MODEL")


def openai_tts_voice() -> str:
    return get_setting("OPENAI_TTS_VOICE")


def azure_speech_key() -> str:
    return get_setting("AZURE_SPEECH_KEY")


def azure_speech_region() -> str:
    return get_setting("AZURE_SPEECH_REGION")


def azure_speech_voice() -> str:
    return get_setting("AZURE_SPEECH_VOICE")


# --- WhatsApp ----------------------------------------------------------------

def whatsapp_access_token() -> str:
    return get_setting("WHATSAPP_ACCESS_TOKEN")


def whatsapp_api_version() -> str:
    version = get_setting("WHATSAPP_API_VERSION")
    return version if version.startswith("v") else f"v{version}"


def locked_recipient_number() -> str:
    return get_setting("LOCKED_RECIPIENT_NUMBER")


# --- Ollama -------------------------------------------------------------------

def ollama_base_url() -> str:
    return get_setting("OLLAMA_BASE_URL").rstrip("/")


def ollama_model() -> str:
    return get_setting("OLLAMA_MODEL")


# --- Readiness (no secret values are ever returned) ---------------------------

def credential_status() -> dict[str, bool]:
    """Presence map for the UI. Keys are variable names, values are True/False."""
    return {
        name: has_setting(name)
        for name in (
            "GROQ_API_KEY",
            "OPENAI_API_KEY",
            "AZURE_SPEECH_KEY",
            "AZURE_SPEECH_REGION",
            "WHATSAPP_ACCESS_TOKEN",
        )
    }
