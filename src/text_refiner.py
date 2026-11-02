"""Text writing/refinement engines.

Order in the UI: Groq (default), Claude, then local Ollama (refinement only,
shown when reachable). The user picks the engine in the sidebar.
"""

from __future__ import annotations

import requests

from . import claude_service, config, groq_text_service

OLLAMA_PROMPT = (
    "أعد صياغة النص التالي باللهجة المصرية العامية الطبيعية كما يُقال في رسالة صوتية قصيرة. "
    "حافظ على المعنى، لا تضف معلومات جديدة، ولا تكتب أي شرح. أخرج النص المعدل فقط.\n\n"
    "النص:\n{text}"
)

ENGINE_GROQ = "Groq"
ENGINE_CLAUDE = "Claude"
ENGINE_OLLAMA = "Ollama (local)"
ENGINE_ORDER = [ENGINE_GROQ, ENGINE_CLAUDE, ENGINE_OLLAMA]
_ENGINE_KEYS = {"groq": ENGINE_GROQ, "claude": ENGINE_CLAUDE, "anthropic": ENGINE_CLAUDE, "ollama": ENGINE_OLLAMA}


class RefineError(Exception):
    pass


def ollama_available() -> bool:
    try:
        resp = requests.get(f"{config.ollama_base_url()}/api/tags", timeout=3)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def engine_ready(engine: str) -> tuple[bool, str]:
    """(ready, message). Messages never contain secret values."""
    if engine == ENGINE_GROQ:
        ok = groq_text_service.groq_text_available()
        return ok, f"Ready (model {config.groq_text_model()})." if ok else "Missing GROQ_API_KEY."
    if engine == ENGINE_CLAUDE:
        ok = claude_service.claude_available()
        return ok, f"Ready (model {config.claude_model()})." if ok else "Missing ANTHROPIC_API_KEY."
    if engine == ENGINE_OLLAMA:
        ok = ollama_available()
        return ok, "Ready (refine only)." if ok else f"Not reachable at {config.ollama_base_url()}."
    return False, "Unknown engine."


def default_engine() -> str:
    """Configured TEXT_ENGINE, Groq by default."""
    return _ENGINE_KEYS.get(config.text_engine().lower(), ENGINE_GROQ)


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


def refine_to_egyptian(text: str, engine: str | None = None) -> tuple[str, str]:
    """Return (refined_text, engine_name) using the chosen engine."""
    engine = engine or default_engine()
    text = (text or "").strip()
    if not text:
        raise RefineError("Nothing to refine.")
    try:
        if engine == ENGINE_GROQ:
            return groq_text_service.refine_to_egyptian(text), ENGINE_GROQ
        if engine == ENGINE_CLAUDE:
            return claude_service.refine_to_egyptian(text), ENGINE_CLAUDE
        if engine == ENGINE_OLLAMA:
            return _ollama_refine(text), ENGINE_OLLAMA
    except (
        groq_text_service.GroqTextSetupError, groq_text_service.GroqTextError,
        claude_service.ClaudeSetupError, claude_service.ClaudeError,
    ) as exc:
        raise RefineError(str(exc)) from exc
    raise RefineError(f"Unknown engine: {engine}")


def write_message(brief: str, engine: str | None = None) -> tuple[str, str]:
    """Draft a message from a brief with Groq or Claude (Ollama is refine-only)."""
    engine = engine or default_engine()
    try:
        if engine == ENGINE_GROQ:
            return groq_text_service.write_message(brief), ENGINE_GROQ
        if engine == ENGINE_CLAUDE:
            return claude_service.write_message(brief), ENGINE_CLAUDE
    except (
        groq_text_service.GroqTextSetupError, groq_text_service.GroqTextError,
        claude_service.ClaudeSetupError, claude_service.ClaudeError,
    ) as exc:
        raise RefineError(str(exc)) from exc
    raise RefineError(f"{engine} cannot draft a message. Choose Groq or Claude.")
