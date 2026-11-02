"""Credential and settings loading.

Values are read, in order, from:
1. A local ``.env`` file next to ``app.py`` (wins over the process environment,
   so a stale empty variable in the shell cannot hide a key saved in the file).
2. A plain-text keys file: ``keys.txt`` or ``API keys.txt`` in the app folder or
   its parent folder (or the path in ``KEYS_FILE``). Lines may be ``NAME=value``,
   ``name: value`` or a bare key; non-blank values override ``.env``.
3. The process environment.
4. Streamlit secrets (``.streamlit/secrets.toml``) when running under Streamlit.

Secret values are never logged or displayed; only presence is reported.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = APP_DIR / ".env"
KEYS_PATH = APP_DIR / "keys.txt"
GENERATED_AUDIO_DIR = APP_DIR / "generated_audio"
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "voice_app.db"

AI_DISCLOSURE = "Generated AI voice audio."

DEFAULTS = {
    "TEXT_ENGINE": "groq",
    "GROQ_TEXT_MODEL": "llama-3.3-70b-versatile",
    "CLAUDE_MODEL": "claude-opus-5-5",
    "CLAUDE_EFFORT": "medium",
    "ELEVENLABS_MODEL": "eleven_multilingual_v2",
    "ELEVENLABS_VOICE_ID": "",
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


KEY_ALIASES = {
    "elevenlabs": "ELEVENLABS_API_KEY", "eleven_labs": "ELEVENLABS_API_KEY", "elevenlabs_api_key": "ELEVENLABS_API_KEY",
    "eleven": "ELEVENLABS_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY", "anthropic_api_key": "ANTHROPIC_API_KEY",
    "claude": "ANTHROPIC_API_KEY", "claude_api": "ANTHROPIC_API_KEY", "claude_api_key": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY", "groq_api": "GROQ_API_KEY", "groq_api_key": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY", "openai_api": "OPENAI_API_KEY", "openai_api_key": "OPENAI_API_KEY",
    "azure": "AZURE_SPEECH_KEY", "azure_key": "AZURE_SPEECH_KEY", "azure_speech_key": "AZURE_SPEECH_KEY",
    "azure_region": "AZURE_SPEECH_REGION", "azure_speech_region": "AZURE_SPEECH_REGION",
    "whatsapp": "WHATSAPP_ACCESS_TOKEN", "whatsapp_token": "WHATSAPP_ACCESS_TOKEN",
    "whatsapp_access_token": "WHATSAPP_ACCESS_TOKEN",
}
KEY_PREFIXES = (("sk-ant-", "ANTHROPIC_API_KEY"), ("gsk_", "GROQ_API_KEY"), ("sk-", "OPENAI_API_KEY"))
KEYS_FILE_NAMES = ("keys.txt", "api keys.txt", "api keys", "api_keys.txt", "apikeys.txt")


def _normalize_key_name(name: str) -> str:
    cleaned = name.strip().strip("#*-").strip().lower()
    cleaned = "_".join(cleaned.replace("-", " ").split())
    if cleaned in KEY_ALIASES:
        return KEY_ALIASES[cleaned]
    return cleaned.upper()


def parse_keys_text(text: str) -> dict[str, str]:
    """Parse a loose keys file: ``NAME=value``, ``name: value`` or bare keys."""
    found: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line or line.startswith("#"):
            continue
        name, value = "", ""
        if "=" in line:
            name, value = line.split("=", 1)
        elif ":" in line and not line.lower().startswith("http"):
            name, value = line.split(":", 1)
        else:
            value = line
        value = _clean(value)
        if not value:
            continue
        key = _normalize_key_name(name) if name.strip() else ""
        if not key or key not in KEY_ALIASES.values() and not key.endswith(("_KEY", "_TOKEN", "_REGION", "_MODEL", "_VOICE", "_URL", "_VERSION", "_NUMBER", "_EFFORT")):
            key = next((target for prefix, target in KEY_PREFIXES if value.startswith(prefix)), key)
        if key:
            found[key] = value
    return found


def find_keys_file() -> Path | None:
    """First keys file found: KEYS_FILE env, app folder, then the parent folder."""
    explicit = _clean(os.environ.get("KEYS_FILE"))
    if explicit and Path(explicit).is_file():
        return Path(explicit)
    for folder in (APP_DIR, APP_DIR.parent):
        try:
            entries = {entry.name.lower(): entry for entry in folder.iterdir() if entry.is_file()}
        except OSError:
            continue
        for name in KEYS_FILE_NAMES:
            if name in entries:
                return entries[name]
    return None


LOADED_KEYS_FILE: Path | None = None


def load_keys_file(path: Path | None = None) -> int:
    """Load a keys file into the environment. Returns the number of keys applied.

    Only non-blank values are applied, so an empty line never wipes a key that
    ``.env`` already set. The file is plain text so it can be edited in Notepad.
    """
    global LOADED_KEYS_FILE
    path = path or find_keys_file()
    if path is None or not path.exists():
        return 0
    values = parse_keys_text(path.read_text(encoding="utf-8-sig", errors="replace"))
    for key, value in values.items():
        os.environ[key] = value
    if values:
        LOADED_KEYS_FILE = path
    return len(values)


def _clean(value) -> str:
    if value is None:
        return ""
    text = str(value).strip().strip('"').strip("'").strip()
    return text


load_env_file()
load_keys_file()


def _streamlit_secret(name: str):
    try:
        import streamlit as st  # noqa: WPS433 - optional at import time

        return st.secrets.get(name)  # type: ignore[union-attr]
    except Exception:  # no secrets file, or not running under Streamlit
        return None


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


# --- Text engine selection (Groq default, Claude optional) --------------------

def text_engine() -> str:
    return get_setting("TEXT_ENGINE")


def groq_text_model() -> str:
    return get_setting("GROQ_TEXT_MODEL")


# --- Claude (optional AI for writing and refining the message text) -----------

def anthropic_api_key() -> str:
    return get_setting("ANTHROPIC_API_KEY")


def claude_model() -> str:
    return get_setting("CLAUDE_MODEL")


def claude_effort() -> str:
    effort = get_setting("CLAUDE_EFFORT").lower()
    return effort if effort in ("low", "medium", "high", "xhigh", "max") else "medium"


# --- ElevenLabs (natural voices + voice cloning) ----------------------------

def elevenlabs_api_key() -> str:
    return get_setting("ELEVENLABS_API_KEY")


def elevenlabs_model() -> str:
    return get_setting("ELEVENLABS_MODEL")


def elevenlabs_voice_id() -> str:
    return get_setting("ELEVENLABS_VOICE_ID")


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
            "ELEVENLABS_API_KEY",
            "ANTHROPIC_API_KEY",
            "GROQ_API_KEY",
            "OPENAI_API_KEY",
            "AZURE_SPEECH_KEY",
            "AZURE_SPEECH_REGION",
            "WHATSAPP_ACCESS_TOKEN",
        )
    }
