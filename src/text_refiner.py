"""Text writing/refinement: Claude is primary, local Ollama is the optional fallback."""

from __future__ import annotations

import requests

from . import claude_service, config

OLLAMA_PROMPT = (
    "أعد صياغة النص التالي باللهجة المصرية العامية الطبيعية كما يُقال في رسالة صوتية قصيرة. "
    "حافظ على المعنى، لا تضف معلومات جديدة، ولا تكتب أي شرح. أخرج النص المعدل فقط.\n\n"
    "النص:\n{text}"
)

ENGINE_CLAUDE = "Claude"
ENGINE_OLLAMA = "Ollama (local fallback)"


class RefineError(Exception):
    pass


def ollama_available() -> bool:
    try:
        resp = requests.get(f"{config.ollama_base_url()}/api/tags", timeout=3)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def active_engine() -> str | None:
    """Which text engine will be used, or None when neither is configured."""
    if claude_service.claude_available():
        return ENGINE_CLAUDE
    if ollama_available():
        return ENGINE_OLLAMA
    return None


def _ollama_refine(text: str) -> str:
    try:
        resp = requests.post(
            f"{config.ollama_base_url()}/api/generate",
            json={"model": config.ollama_model(), "prompt": OLLAMA_PROMPT.format(text=text), "stream": False},
            timeout=120,
        )
    except requests.RequestException as exc:
        raise RefineError(f"Could not reach Ollama at {config.ollama_base_url()}: {exc}") from exc
    if resp.status_code != 200:
        raise RefineError(f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}")
    refined = (resp.json().get("response") or "").strip()
    if not refined:
        raise RefineError("Ollama returned an empty response.")
    return refined


def refine_to_egyptian(text: str) -> tuple[str, str]:
    """Return (refined_text, engine_name). Claude first, Ollama when Claude is not configured."""
    text = (text or "").strip()
    if not text:
        raise RefineError("Nothing to refine.")
    if claude_service.claude_available():
        try:
            return claude_service.refine_to_egyptian(text), ENGINE_CLAUDE
        except (claude_service.ClaudeSetupError, claude_service.ClaudeError) as exc:
            raise RefineError(str(exc)) from exc
    if ollama_available():
        return _ollama_refine(text), ENGINE_OLLAMA
    raise RefineError("No text engine configured. Add ANTHROPIC_API_KEY to .env (or run Ollama locally).")


def write_message(brief: str) -> tuple[str, str]:
    """Draft a message from a brief. Claude only; Ollama fallback is refinement-only."""
    try:
        return claude_service.write_message(brief), ENGINE_CLAUDE
    except (claude_service.ClaudeSetupError, claude_service.ClaudeError) as exc:
        raise RefineError(str(exc)) from exc
