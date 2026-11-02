"""Claude (Anthropic API) - the app's primary AI.

Claude writes and refines the Egyptian Arabic message text. Voice synthesis is a
separate step handled by the TTS providers, because the Claude API does not
produce audio.
"""

from __future__ import annotations

from . import config

SYSTEM_PROMPT = (
    "You write short voice-note scripts in natural Egyptian Arabic (العامية المصرية), "
    "the way a Cairo speaker would actually say them out loud. Use Arabic script only. "
    "Keep the meaning the user gives you, add nothing that was not asked for, and never "
    "include explanations, options, headings, quotes, or transliteration. "
    "Output only the final text that will be read aloud."
)

WRITE_TEMPLATE = (
    "اكتب رسالة صوتية قصيرة باللهجة المصرية بناءً على هذا الطلب:\n\n{brief}"
)
REFINE_TEMPLATE = (
    "أعد صياغة النص التالي باللهجة المصرية العامية الطبيعية كما يُقال في رسالة صوتية. "
    "حافظ على المعنى ولا تضف معلومات جديدة.\n\nالنص:\n{text}"
)


class ClaudeSetupError(Exception):
    """Missing key or SDK."""


class ClaudeError(Exception):
    """The API call failed or was refused."""


def claude_available() -> bool:
    return bool(config.anthropic_api_key())


def _client():
    api_key = config.anthropic_api_key()
    if not api_key:
        raise ClaudeSetupError("ANTHROPIC_API_KEY is missing. Add it to .env or Streamlit secrets.")
    try:
        import anthropic
    except ImportError as exc:
        raise ClaudeSetupError("The anthropic package is not installed. Run: pip install -r requirements.txt") from exc
    return anthropic, anthropic.Anthropic(api_key=api_key)


def _complete(user_text: str) -> str:
    anthropic, client = _client()
    try:
        response = client.beta.messages.create(
            model=config.claude_model(),
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            output_config={"effort": config.claude_effort()},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": user_text}],
        )
    except anthropic.AuthenticationError as exc:
        raise ClaudeError("Claude rejected the API key (401). Check ANTHROPIC_API_KEY in .env.") from exc
    except anthropic.RateLimitError as exc:
        raise ClaudeError("Claude rate limit reached. Wait a moment and try again.") from exc
    except anthropic.APIStatusError as exc:
        raise ClaudeError(f"Claude API error (HTTP {exc.status_code}): {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise ClaudeError(f"Could not reach the Claude API: {exc}") from exc

    if response.stop_reason == "refusal":
        reason = getattr(getattr(response, "stop_details", None), "explanation", None) or "no details"
        raise ClaudeError(f"Claude declined this request: {reason}")

    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise ClaudeError("Claude returned no text.")
    return text


def write_message(brief: str) -> str:
    """Turn a short brief (any language) into an Egyptian Arabic voice-note script."""
    brief = (brief or "").strip()
    if not brief:
        raise ClaudeError("Describe what the message should say.")
    return _complete(WRITE_TEMPLATE.format(brief=brief))


def refine_to_egyptian(text: str) -> str:
    """Rewrite existing text into natural Egyptian dialect without changing meaning."""
    text = (text or "").strip()
    if not text:
        raise ClaudeError("Nothing to refine.")
    return _complete(REFINE_TEMPLATE.format(text=text))
