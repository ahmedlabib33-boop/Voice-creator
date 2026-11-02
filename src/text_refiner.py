"""Optional Egyptian Arabic text refinement through a local Ollama server."""

from __future__ import annotations

import requests

from . import config

PROMPT = (
    "أعد صياغة النص التالي باللهجة المصرية العامية الطبيعية كما يُقال في رسالة صوتية قصيرة. "
    "حافظ على المعنى، لا تضف معلومات جديدة، ولا تكتب أي شرح. أخرج النص المعدل فقط.\n\n"
    "النص:\n{text}"
)


class RefineError(Exception):
    pass


def ollama_available() -> bool:
    try:
        resp = requests.get(f"{config.ollama_base_url()}/api/tags", timeout=3)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def refine_to_egyptian(text: str) -> str:
    text = (text or "").strip()
    if not text:
        raise RefineError("Nothing to refine.")
    try:
        resp = requests.post(
            f"{config.ollama_base_url()}/api/generate",
            json={"model": config.ollama_model(), "prompt": PROMPT.format(text=text), "stream": False},
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
