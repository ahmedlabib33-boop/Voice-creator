"""Text-to-speech providers.

Provider order (first available is the default):
1. Groq Orpheus Arabic TTS   - ``canopylabs/orpheus-arabic-saudi`` (WAV only, 200 chars/request)
2. OpenAI TTS                - ``gpt-4o-mini-tts`` by default
3. Azure Speech              - Egyptian Arabic neural voice ``ar-EG-SalmaNeural`` by default
4. Windows TTS fallback      - offline ``pyttsx3`` (SAPI5), lower quality, Windows only

Every provider returns an MP3 path inside ``generated_audio/`` so preview,
download and WhatsApp upload share one format. Long text is split into
provider-sized chunks and merged with ffmpeg.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

from . import config, elevenlabs_service

PROVIDER_ELEVENLABS = "ElevenLabs natural voice (clone-capable)"
PROVIDER_GROQ = "Groq Orpheus Arabic TTS"
PROVIDER_OPENAI = "OpenAI TTS"
PROVIDER_AZURE = "Azure Arabic Egypt Neural TTS"
PROVIDER_WINDOWS = "Windows TTS fallback"
PROVIDER_ORDER = [PROVIDER_ELEVENLABS, PROVIDER_AZURE, PROVIDER_GROQ, PROVIDER_OPENAI, PROVIDER_WINDOWS]

GROQ_MAX_CHARS = 200
OPENAI_MAX_CHARS = 4000
AZURE_MAX_CHARS = 3000
GROQ_ARABIC_VOICES = ["noura", "lulwa", "aisha", "abdullah", "fahad", "sultan"]

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[\.\!\?؟،,;:\n])\s+")


class TTSSetupError(Exception):
    """Raised when a provider cannot run because of missing keys or tools."""


class TTSGenerationError(Exception):
    """Raised when the provider call itself fails."""


@dataclass
class ProviderStatus:
    name: str
    ready: bool
    message: str
    warning: str = ""


# --- readiness ------------------------------------------------------------------

def provider_statuses() -> list[ProviderStatus]:
    """Readiness per provider. Messages never contain secret values."""
    statuses = []

    statuses.append(
        ProviderStatus(
            PROVIDER_ELEVENLABS,
            elevenlabs_service.available(),
            "Ready: natural voices, Egyptian female voice, cloning." if elevenlabs_service.available() else "Missing ELEVENLABS_API_KEY.",
        )
    )
    statuses.append(
        ProviderStatus(
            PROVIDER_GROQ,
            bool(config.groq_api_key()),
            "Ready." if config.groq_api_key() else "Missing GROQ_API_KEY in .env or Streamlit secrets.",
        )
    )
    statuses.append(
        ProviderStatus(
            PROVIDER_OPENAI,
            bool(config.openai_api_key()),
            "Ready." if config.openai_api_key() else "Missing OPENAI_API_KEY in .env or Streamlit secrets.",
        )
    )
    azure_missing = [n for n in ("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION") if not config.has_setting(n)]
    statuses.append(
        ProviderStatus(
            PROVIDER_AZURE,
            not azure_missing,
            "Ready: Egyptian Arabic neural voice (ar-EG-SalmaNeural)." if not azure_missing else "Missing " + " and ".join(azure_missing) + ".",
        )
    )
    win_ready = sys.platform == "win32" and _pyttsx3_available()
    statuses.append(
        ProviderStatus(
            PROVIDER_WINDOWS,
            win_ready,
            "Ready (offline)." if win_ready else "Only available on Windows with pyttsx3 installed.",
            warning="Fallback only: robotic Windows voice, not a natural Egyptian accent.",
        )
    )
    order = {name: i for i, name in enumerate(PROVIDER_ORDER)}
    statuses.sort(key=lambda st: order.get(st.name, 99))
    return statuses


def default_provider() -> str:
    for status in provider_statuses():
        if status.ready:
            return status.name
    return PROVIDER_ELEVENLABS


def _pyttsx3_available() -> bool:
    try:
        import pyttsx3  # noqa: F401

        return True
    except Exception:
        return False


# --- text helpers --------------------------------------------------------------

def split_text(text: str, max_chars: int) -> list[str]:
    """Split text into chunks no longer than ``max_chars``, preferring sentence
    boundaries, then word boundaries, then hard cuts."""
    text = re.sub(r"[ \t]+", " ", (text or "").strip())
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_words(sentence, max_chars))
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def _split_words(sentence: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for word in sentence.split(" "):
        while len(word) > max_chars:  # a single oversized token: hard cut
            if current:
                chunks.append(current)
                current = ""
            chunks.append(word[:max_chars])
            word = word[max_chars:]
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks


# --- ffmpeg helpers ----------------------------------------------------------

def ffmpeg_path() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise TTSSetupError(
            "ffmpeg was not found on PATH. Install it (winget install Gyan.FFmpeg on Windows) "
            "so audio can be merged and converted to MP3."
        )
    return path


def merge_to_mp3(parts: list[Path], output: Path) -> Path:
    """Concatenate audio parts (any ffmpeg-readable format) into one MP3."""
    if not parts:
        raise TTSGenerationError("No audio parts to merge.")
    ffmpeg = ffmpeg_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        list_file = Path(tmp) / "parts.txt"
        list_file.write_text(
            "".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8"
        )
        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-vn", "-ar", "24000", "-ac", "1", "-b:a", "96k", "-f", "mp3", str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise TTSGenerationError(f"ffmpeg failed: {result.stderr.strip()[:500]}")
    return output


def new_output_path(output_dir: Path | None = None) -> Path:
    output_dir = output_dir or config.GENERATED_AUDIO_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_dir / f"voice_{stamp}.mp3"


# --- providers -------------------------------------------------------------------

def generate_speech(text: str, provider: str, voice: str | None = None, output_dir: Path | None = None, options: dict | None = None) -> Path:
    """Generate an MP3 for ``text`` using ``provider``. Returns the MP3 path."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Enter some text to convert to speech.")
    output = new_output_path(output_dir)
    generators = {
        PROVIDER_ELEVENLABS: _generate_elevenlabs,
        PROVIDER_GROQ: _generate_groq,
        PROVIDER_OPENAI: _generate_openai,
        PROVIDER_AZURE: _generate_azure,
        PROVIDER_WINDOWS: _generate_windows,
    }
    if provider not in generators:
        raise ValueError(f"Unknown provider: {provider}")
    if provider == PROVIDER_ELEVENLABS:
        return _generate_elevenlabs(text, voice or "", output, options or {})
    return generators[provider](text, voice or "", output)


def _generate_elevenlabs(text: str, voice: str, output: Path, options: dict) -> Path:
    if not elevenlabs_service.available():
        raise TTSSetupError("ELEVENLABS_API_KEY is missing. Add it to the keys file, .env or Streamlit secrets.")
    voice_id = voice or config.elevenlabs_voice_id()
    chunks = split_text(text, elevenlabs_service.MAX_CHARS)
    try:
        settings = options.get("settings")
        model_id = options.get("model_id")
        if len(chunks) == 1:
            return elevenlabs_service.synthesize(chunks[0], voice_id, output, settings, model_id)
        with tempfile.TemporaryDirectory() as tmp:
            parts = [
                elevenlabs_service.synthesize(c, voice_id, Path(tmp) / f"part_{i:03d}.mp3", settings, model_id)
                for i, c in enumerate(chunks)
            ]
            return merge_to_mp3(parts, output)
    except elevenlabs_service.ElevenLabsSetupError as exc:
        raise TTSSetupError(str(exc)) from exc
    except elevenlabs_service.ElevenLabsError as exc:
        raise TTSGenerationError(str(exc)) from exc


def _generate_groq(text: str, voice: str, output: Path) -> Path:
    api_key = config.groq_api_key()
    if not api_key:
        raise TTSSetupError("GROQ_API_KEY is missing. Add it to .env or Streamlit secrets.")
    try:
        from groq import Groq
    except ImportError as exc:
        raise TTSSetupError("The groq package is not installed. Run: pip install -r requirements.txt") from exc

    client = Groq(api_key=api_key)
    model = config.groq_tts_model()
    voice = voice or config.groq_tts_voice()
    chunks = split_text(text, GROQ_MAX_CHARS)
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for index, chunk in enumerate(chunks):
            part = Path(tmp) / f"part_{index:03d}.wav"
            try:
                response = client.audio.speech.create(
                    model=model, voice=voice, input=chunk, response_format="wav"
                )
                response.write_to_file(part)
            except Exception as exc:  # SDK raises typed errors; surface a clean message
                raise TTSGenerationError(f"Groq TTS failed: {_describe(exc)}") from exc
            parts.append(part)
        return merge_to_mp3(parts, output)


def _generate_openai(text: str, voice: str, output: Path) -> Path:
    api_key = config.openai_api_key()
    if not api_key:
        raise TTSSetupError("OPENAI_API_KEY is missing. Add it to .env or Streamlit secrets.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise TTSSetupError("The openai package is not installed. Run: pip install -r requirements.txt") from exc

    client = OpenAI(api_key=api_key)
    model = config.openai_tts_model()
    voice = voice or config.openai_tts_voice()
    chunks = split_text(text, OPENAI_MAX_CHARS)
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for index, chunk in enumerate(chunks):
            part = Path(tmp) / f"part_{index:03d}.mp3"
            try:
                with client.audio.speech.with_streaming_response.create(
                    model=model, voice=voice, input=chunk, response_format="mp3"
                ) as response:
                    response.stream_to_file(part)
            except Exception as exc:
                raise TTSGenerationError(f"OpenAI TTS failed: {_describe(exc)}") from exc
            parts.append(part)
        if len(parts) == 1:
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(parts[0], output)
            return output
        return merge_to_mp3(parts, output)


def _generate_azure(text: str, voice: str, output: Path) -> Path:
    key = config.azure_speech_key()
    region = config.azure_speech_region()
    if not key or not region:
        raise TTSSetupError("AZURE_SPEECH_KEY and AZURE_SPEECH_REGION are required for Azure TTS.")
    voice = voice or config.azure_speech_voice()
    lang = "-".join(voice.split("-")[:2]) if voice.count("-") >= 2 else "ar-EG"
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3",
        "User-Agent": "egyptian-voice-sender",
    }
    chunks = split_text(text, AZURE_MAX_CHARS)
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for index, chunk in enumerate(chunks):
            ssml = (
                f"<speak version='1.0' xml:lang='{lang}'>"
                f"<voice name='{voice}'>{_xml_escape(chunk)}</voice></speak>"
            )
            try:
                resp = requests.post(url, headers=headers, data=ssml.encode("utf-8"), timeout=60)
            except requests.RequestException as exc:
                raise TTSGenerationError(f"Azure TTS request failed: {exc}") from exc
            if resp.status_code != 200:
                raise TTSGenerationError(f"Azure TTS failed: HTTP {resp.status_code} {resp.text[:300]}")
            part = Path(tmp) / f"part_{index:03d}.mp3"
            part.write_bytes(resp.content)
            parts.append(part)
        if len(parts) == 1:
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(parts[0], output)
            return output
        return merge_to_mp3(parts, output)


def _generate_windows(text: str, voice: str, output: Path) -> Path:
    if sys.platform != "win32":
        raise TTSSetupError("Windows TTS fallback only works on Windows.")
    try:
        import pyttsx3
    except ImportError as exc:
        raise TTSSetupError("pyttsx3 is not installed. Run: pip install pyttsx3") from exc

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "fallback.wav"
        engine = pyttsx3.init()
        if voice:
            for v in engine.getProperty("voices"):
                if voice.lower() in (v.name or "").lower() or voice == v.id:
                    engine.setProperty("voice", v.id)
                    break
        else:  # prefer an Arabic SAPI voice when one is installed
            for v in engine.getProperty("voices"):
                if "arab" in (v.name or "").lower() or "ar-" in (v.id or "").lower():
                    engine.setProperty("voice", v.id)
                    break
        engine.save_to_file(text, str(wav))
        engine.runAndWait()
        if not wav.exists() or wav.stat().st_size == 0:
            raise TTSGenerationError("Windows TTS produced no audio.")
        return merge_to_mp3([wav], output)


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;").replace("'", "&apos;")
    )


def _describe(exc: Exception) -> str:
    """Short error text for the UI; strips anything that could echo a key."""
    message = str(exc) or exc.__class__.__name__
    status = getattr(exc, "status_code", None)
    if status:
        message = f"HTTP {status}: {message}"
    if "401" in message or "invalid_api_key" in message.lower():
        message += " (The API key was rejected. Check the value saved in .env.)"
    return message[:400]
