"""Free Egyptian Arabic neural voices through Microsoft Edge's read-aloud service.

No key, no account. Voices are the same neural models Azure sells
(``ar-EG-SalmaNeural`` female, ``ar-EG-ShakirNeural`` male). Output is MP3.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

VOICES = {
    "ar-EG-SalmaNeural": "Salma · Egyptian female (soft, default)",
    "ar-EG-ShakirNeural": "Shakir · Egyptian male",
}
DEFAULT_VOICE = "ar-EG-SalmaNeural"

# Softer delivery: slightly slower and a touch lower.
SOFT_PRESET = {"rate": "-6%", "pitch": "-2Hz", "volume": "+0%"}


class EdgeSetupError(Exception):
    pass


class EdgeError(Exception):
    pass


def available() -> bool:
    try:
        import edge_tts  # noqa: F401

        return True
    except Exception:
        return False


def _pct(value: float) -> str:
    """Map a slider value (-50..50) to the '+N%' / '-N%' form edge-tts expects."""
    value = int(round(value))
    return f"{'+' if value >= 0 else ''}{value}%"


def _hz(value: float) -> str:
    value = int(round(value))
    return f"{'+' if value >= 0 else ''}{value}Hz"


def synthesize(text: str, voice: str, output: Path, rate_pct: float | None = None, pitch_hz: float | None = None) -> Path:
    if not available():
        raise EdgeSetupError("The edge-tts package is not installed. Run: pip install -r requirements.txt")
    import edge_tts

    voice = voice or DEFAULT_VOICE
    rate = _pct(rate_pct) if rate_pct is not None else SOFT_PRESET["rate"]
    pitch = _hz(pitch_hz) if pitch_hz is not None else SOFT_PRESET["pitch"]
    output.parent.mkdir(parents=True, exist_ok=True)

    async def _run():
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(str(output))

    try:
        asyncio.run(_run())
    except RuntimeError:
        # Already inside an event loop (rare under Streamlit); use a private loop.
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_run())
        finally:
            loop.close()
    except Exception as exc:  # network / service errors
        raise EdgeError(f"Edge TTS failed: {exc.__class__.__name__}: {exc}") from exc

    if not output.exists() or output.stat().st_size == 0:
        raise EdgeError("Edge TTS produced no audio. Check the internet connection and try again.")
    return output
