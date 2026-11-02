"""ElevenLabs: natural multilingual voices and instant voice cloning.

Used for the "real" soft Egyptian female voice and for cloning an uploaded
sample. Cloning is gated behind an explicit consent attestation recorded in the
local database, and every generated file keeps the AI disclosure label.
"""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path

import requests

from . import config

API_BASE = "https://api.elevenlabs.io/v1"
API_BASE_V2 = "https://api.elevenlabs.io/v2"
OUTPUT_FORMAT = "mp3_44100_128"
MAX_CHARS = 2500  # well under every model's per-request limit; chunks are merged by the TTS layer

# Model ids from https://elevenlabs.io/docs/models (all support Arabic).
MODELS = {
    "eleven_multilingual_v2": "Multilingual v2 · reliable default, 29 languages",
    "eleven_v4": "v4 · highest quality, high-fidelity cloning",
    "eleven_v3": "v3 · expressive, 70+ languages",
    "eleven_flash_v2_5": "Flash v2.5 · fastest, lower cost",
}

CONSENT_TEXT = (
    "I confirm that this is my own voice, or that the speaker has given me explicit permission "
    "to clone it. I will not use it to impersonate anyone or to deceive recipients. "
    "Generated audio will stay labelled as AI-generated."
)

# Soft, calm delivery for a "high-class" conversational register.
SOFT_SETTINGS = {"stability": 0.65, "similarity_boost": 0.85, "style": 0.15, "use_speaker_boost": True, "speed": 0.95}


class ElevenLabsSetupError(Exception):
    pass


class ElevenLabsError(Exception):
    pass


@dataclass
class Voice:
    voice_id: str
    name: str
    category: str  # premade | cloned | generated | professional
    labels: dict

    @property
    def label(self) -> str:
        bits = [v for k, v in self.labels.items() if k in ("gender", "accent", "language", "age") and v]
        tag = "clone" if self.category == "cloned" else self.category
        return f"{self.name} · {', '.join(bits) if bits else tag}"


def available() -> bool:
    return bool(config.elevenlabs_api_key())


def _headers() -> dict:
    key = config.elevenlabs_api_key()
    if not key:
        raise ElevenLabsSetupError("ELEVENLABS_API_KEY is missing. Add it to the keys file, .env or Streamlit secrets.")
    return {"xi-api-key": key}


def _raise(resp: requests.Response, action: str) -> None:
    if resp.status_code < 400:
        return
    detail = ""
    try:
        payload = resp.json()
        detail = payload.get("detail", payload)
        if isinstance(detail, dict):
            detail = detail.get("message") or detail.get("status") or str(detail)
    except ValueError:
        detail = resp.text[:300]
    if resp.status_code == 401:
        detail = "API key rejected. Check ELEVENLABS_API_KEY."
    raise ElevenLabsError(f"{action} failed (HTTP {resp.status_code}): {detail}")


def list_voices() -> list[Voice]:
    """All voices in the account (premade library picks + clones), paginated via /v2/voices."""
    voices: list[Voice] = []
    token = None
    for _ in range(5):  # at most 500 voices
        params = {"page_size": 100}
        if token:
            params["next_page_token"] = token
        resp = requests.get(f"{API_BASE_V2}/voices", headers=_headers(), params=params, timeout=30)
        _raise(resp, "Listing voices")
        payload = resp.json()
        for item in payload.get("voices", []):
            voices.append(Voice(item.get("voice_id", ""), item.get("name", "?"), item.get("category", ""), item.get("labels") or {}))
        token = payload.get("next_page_token")
        if not payload.get("has_more") or not token:
            break
    # cloned voices first, then female voices, then the rest
    def rank(v: Voice):
        return (v.category != "cloned", (v.labels.get("gender") or "").lower() != "female", v.name.lower())
    return sorted(voices, key=rank)


def synthesize(text: str, voice_id: str, output: Path, settings: dict | None = None, model_id: str | None = None) -> Path:
    if not voice_id:
        raise ElevenLabsSetupError("Choose an ElevenLabs voice (or set ELEVENLABS_VOICE_ID).")
    body = {
        "text": text,
        "model_id": model_id or config.elevenlabs_model(),
        "voice_settings": settings or SOFT_SETTINGS,
    }
    try:
        resp = requests.post(
            f"{API_BASE}/text-to-speech/{voice_id}",
            params={"output_format": OUTPUT_FORMAT},
            headers={**_headers(), "Content-Type": "application/json", "Accept": "audio/mpeg"},
            json=body,
            timeout=120,
        )
    except requests.RequestException as exc:
        raise ElevenLabsError(f"Could not reach ElevenLabs: {exc}") from exc
    _raise(resp, "Speech generation")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(resp.content)
    return output


@dataclass
class CloneResult:
    voice: Voice
    requires_verification: bool


def clone_voice(name: str, sample_paths: list[Path], description: str = "", remove_noise: bool = True, labels: dict | None = None) -> CloneResult:
    """Instant voice clone from 1+ audio samples. Caller must have recorded consent first."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Give the cloned voice a name.")
    if not sample_paths:
        raise ValueError("Upload at least one audio sample.")
    files = []
    handles = []
    try:
        for path in sample_paths:
            fh = open(path, "rb")
            handles.append(fh)
            files.append(("files", (Path(path).name, fh, mimetypes.guess_type(Path(path).name)[0] or "audio/mpeg")))
        data = {
            "name": name,
            "description": description or "Cloned with consent in Egyptian Voice Sender. Output is labelled AI-generated.",
            "remove_background_noise": "true" if remove_noise else "false",
        }
        if labels:
            import json

            data["labels"] = json.dumps(labels)
        try:
            resp = requests.post(f"{API_BASE}/voices/add", headers=_headers(), data=data, files=files, timeout=300)
        except requests.RequestException as exc:
            raise ElevenLabsError(f"Could not reach ElevenLabs: {exc}") from exc
    finally:
        for fh in handles:
            fh.close()
    _raise(resp, "Voice cloning")
    payload = resp.json()
    voice_id = payload.get("voice_id")
    if not voice_id:
        raise ElevenLabsError("ElevenLabs returned no voice_id.")
    return CloneResult(Voice(voice_id, name, "cloned", labels or {}), bool(payload.get("requires_verification")))


def delete_voice(voice_id: str) -> None:
    resp = requests.delete(f"{API_BASE}/voices/{voice_id}", headers=_headers(), timeout=30)
    _raise(resp, "Deleting voice")
