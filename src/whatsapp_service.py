"""Official WhatsApp Cloud API (Meta Graph API) sending.

Sending always goes through an authorized Meta ``phone_number_id``. A plain
phone number is never used as the sender: the SMS-registered local number only
proves OTP capability and cannot send WhatsApp messages by itself.
No WhatsApp Web / Desktop automation is used anywhere in this app.
"""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import requests

from . import config
from .validators import normalize_phone

GRAPH_BASE = "https://graph.facebook.com"


class WhatsAppSetupError(Exception):
    """Missing token or sender."""


class WhatsAppSendError(Exception):
    """The Graph API rejected the request."""


@dataclass
class SendResult:
    message_id: str
    media_id: str
    recipient_e164: str
    phone_number_id: str


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _require_token() -> str:
    token = config.whatsapp_access_token()
    if not token:
        raise WhatsAppSetupError("WHATSAPP_ACCESS_TOKEN is missing. Add it to .env or Streamlit secrets.")
    return token


def _base_url(phone_number_id: str) -> str:
    return f"{GRAPH_BASE}/{config.whatsapp_api_version()}/{phone_number_id}"


def _raise_for_graph_error(resp: requests.Response, action: str) -> dict:
    try:
        payload = resp.json()
    except ValueError:
        payload = {}
    if resp.status_code >= 400 or "error" in payload:
        err = payload.get("error", {})
        detail = err.get("message") or resp.text[:300]
        code = err.get("code")
        raise WhatsAppSendError(f"{action} failed (HTTP {resp.status_code}, code {code}): {detail}")
    return payload


def check_sender(phone_number_id: str) -> dict:
    """Read the sender's profile from Meta to validate the token and phone_number_id."""
    token = _require_token()
    resp = requests.get(
        _base_url(phone_number_id),
        headers=_headers(token),
        params={"fields": "display_phone_number,verified_name,quality_rating"},
        timeout=30,
    )
    return _raise_for_graph_error(resp, "Sender check")


def upload_media(phone_number_id: str, file_path: Path) -> str:
    token = _require_token()
    file_path = Path(file_path)
    if not file_path.exists():
        raise WhatsAppSendError(f"Audio file not found: {file_path}")
    mime = mimetypes.guess_type(file_path.name)[0] or "audio/mpeg"
    with file_path.open("rb") as fh:
        resp = requests.post(
            f"{_base_url(phone_number_id)}/media",
            headers=_headers(token),
            data={"messaging_product": "whatsapp", "type": mime},
            files={"file": (file_path.name, fh, mime)},
            timeout=120,
        )
    payload = _raise_for_graph_error(resp, "Media upload")
    media_id = payload.get("id")
    if not media_id:
        raise WhatsAppSendError("Media upload returned no media id.")
    return media_id


def _send_message(phone_number_id: str, body: dict, action: str) -> str:
    token = _require_token()
    resp = requests.post(
        f"{_base_url(phone_number_id)}/messages",
        headers={**_headers(token), "Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    payload = _raise_for_graph_error(resp, action)
    messages = payload.get("messages") or []
    return messages[0].get("id", "") if messages else ""


def send_audio(phone_number_id: str, recipient_input: str, audio_path: Path) -> SendResult:
    recipient = normalize_phone(recipient_input)
    media_id = upload_media(phone_number_id, audio_path)
    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient.digits,
        "type": "audio",
        "audio": {"id": media_id},
    }
    message_id = _send_message(phone_number_id, body, "Audio send")
    return SendResult(message_id, media_id, recipient.normalized_e164, phone_number_id)


def send_text(phone_number_id: str, recipient_input: str, text: str) -> str:
    recipient = normalize_phone(recipient_input)
    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient.digits,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    return _send_message(phone_number_id, body, "Text send")


def manual_chat_link(recipient_input: str, note: str = config.AI_DISCLOSURE) -> str:
    """wa.me link that opens the recipient chat so the user attaches the MP3 manually."""
    recipient = normalize_phone(recipient_input)
    return f"https://wa.me/{recipient.digits}?text={quote(note)}"
