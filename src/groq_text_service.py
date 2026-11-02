"""Groq chat completions - the default AI for writing and refining the message text."""

from __future__ import annotations

from . import config
from .claude_service import REFINE_TEMPLATE, SYSTEM_PROMPT, WRITE_TEMPLATE


class GroqTextSetupError(Exception):
    """Missing key or SDK."""


class GroqTextError(Exception):
    """The API call failed."""


def groq_text_available() -> bool:
    return bool(config.groq_api_key())


def _complete(user_text: str) -> str:
    api_key = config.groq_api_key()
    if not api_key:
        raise GroqTextSetupError("GROQ_API_KEY is missing. Add it to the keys file, .env or Streamlit secrets.")
    try:
        import groq
    except ImportError as exc:
        raise GroqTextSetupError("The groq package is not installed. Run: pip install -r requirements.txt") from exc

    client = groq.Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=config.groq_text_model(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            temperature=0.4,
            max_completion_tokens=1024,
        )
    except groq.AuthenticationError as exc:
        raise GroqTextError("Groq rejected the API key (401). Check GROQ_API_KEY in your keys file.") from exc
    except groq.RateLimitError as exc:
        raise GroqTextError("Groq rate limit reached. Wait a moment and try again.") from exc
    except groq.APIStatusError as exc:
        raise GroqTextError(f"Groq API error (HTTP {exc.status_code}): {getattr(exc, 'message', exc)}") from exc
    except groq.APIConnectionError as exc:
        raise GroqTextError(f"Could not reach the Groq API: {exc}") from exc

    text = (response.choices[0].message.content or "").strip() if response.choices else ""
    if not text:
        raise GroqTextError("Groq returned no text.")
    return text


def write_message(brief: str) -> str:
    brief = (brief or "").strip()
    if not brief:
        raise GroqTextError("Describe what the message should say.")
    return _complete(WRITE_TEMPLATE.format(brief=brief))


def refine_to_egyptian(text: str) -> str:
    text = (text or "").strip()
    if not text:
        raise GroqTextError("Nothing to refine.")
    return _complete(REFINE_TEMPLATE.format(text=text))
