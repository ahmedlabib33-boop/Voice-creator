"""Free, local voice cloning with Coqui XTTS v2 (runs on this PC, no account).

Install (one time, ~2 GB download on first use):
    pip install -r requirements-clone.txt

XTTS v2 speaks Arabic and clones a speaker from a short clean sample. It is
"close, not identical". CPU generation is slow (roughly 5-20x real time);
a CUDA GPU makes it near real time. Model license: Coqui Public Model License
(non-commercial). Cloning is consent-gated in the UI.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from . import config

MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
VOICES_DIR = config.DATA_DIR / "voices"
LICENSE_TEXT = (
    "I accept the Coqui Public Model License (non-commercial use) for the XTTS v2 model "
    "that will be downloaded to this computer."
)
MAX_SAMPLE_SECONDS = 60
MAX_CHARS = 220  # XTTS works best on short sentences; the TTS layer chunks and merges


class LocalCloneSetupError(Exception):
    pass


class LocalCloneError(Exception):
    pass


_model = None


def available() -> bool:
    """True when coqui-tts (and torch) are importable."""
    try:
        import TTS  # noqa: F401

        return True
    except Exception:
        return False


def install_hint() -> str:
    return "Local cloning needs the free XTTS model. Run once in PowerShell:  pip install -r requirements-clone.txt"


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    if not slug:
        raise ValueError("Give the cloned voice a name.")
    return slug


def list_clones() -> list[dict]:
    """Clones stored on disk: {voice_id, name, samples}."""
    if not VOICES_DIR.exists():
        return []
    out = []
    for folder in sorted(VOICES_DIR.iterdir()):
        samples = sorted(folder.glob("sample_*.wav"))
        if folder.is_dir() and samples:
            name_file = folder / "name.txt"
            out.append({
                "voice_id": folder.name,
                "name": name_file.read_text(encoding="utf-8").strip() if name_file.exists() else folder.name,
                "samples": [str(p) for p in samples],
            })
    return out


def prepare_clone(name: str, sample_paths: list[Path]) -> dict:
    """Normalize uploaded samples to 22.05 kHz mono WAV (first 60 s) and store them."""
    if not sample_paths:
        raise ValueError("Upload at least one audio sample.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise LocalCloneSetupError("ffmpeg was not found on PATH. Install it: winget install Gyan.FFmpeg")
    voice_id = slugify(name)
    folder = VOICES_DIR / voice_id
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    for index, src in enumerate(sample_paths):
        dest = folder / f"sample_{index:02d}.wav"
        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
            "-t", str(MAX_SAMPLE_SECONDS), "-ac", "1", "-ar", "22050", "-af", "loudnorm=I=-18:TP=-2", str(dest),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not dest.exists():
            shutil.rmtree(folder, ignore_errors=True)
            raise LocalCloneError(f"Could not read sample {Path(src).name}: {result.stderr.strip()[:200]}")
    (folder / "name.txt").write_text(name.strip(), encoding="utf-8")
    return {"voice_id": voice_id, "name": name.strip(), "samples": [str(p) for p in sorted(folder.glob('sample_*.wav'))]}


def delete_clone(voice_id: str) -> None:
    folder = VOICES_DIR / slugify(voice_id)
    if folder.exists():
        shutil.rmtree(folder)


def _load_model():
    global _model
    if _model is not None:
        return _model
    if not available():
        raise LocalCloneSetupError(install_hint())
    os.environ.setdefault("COQUI_TOS_AGREED", "1")  # the UI records license acceptance before this runs
    from TTS.api import TTS

    try:
        import torch

        gpu = bool(torch.cuda.is_available())
    except Exception:
        gpu = False
    try:
        _model = TTS(MODEL_NAME, progress_bar=False)
        if gpu:
            _model = _model.to("cuda")
    except Exception as exc:
        raise LocalCloneError(f"Could not load XTTS v2: {exc.__class__.__name__}: {exc}") from exc
    return _model


def synthesize_wav(text: str, voice_id: str, output_wav: Path) -> Path:
    """Speak ``text`` (Arabic) in the cloned voice. Returns a WAV path."""
    clones = {c["voice_id"]: c for c in list_clones()}
    if voice_id not in clones:
        raise LocalCloneSetupError("That cloned voice was not found. Create it in the Voice lab first.")
    model = _load_model()
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    try:
        model.tts_to_file(text=text, speaker_wav=clones[voice_id]["samples"], language="ar", file_path=str(output_wav))
    except Exception as exc:
        raise LocalCloneError(f"XTTS generation failed: {exc.__class__.__name__}: {exc}") from exc
    return output_wav
