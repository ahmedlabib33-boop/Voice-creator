"""Post-processing that makes synthetic speech sit more naturally in the ear.

Synthetic voices sound "too clean": no room, no breath, flat dynamics. This
ffmpeg chain adds a touch of warmth, gentle compression, a very small room and
a whisper of air. It never alters the words. Strength 0 = untouched, 1 = maximum.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class HumanizeError(Exception):
    pass


def filter_graph(strength: float) -> str:
    s = max(0.0, min(1.0, strength))
    presence_cut = -1.0 - 2.0 * s      # soften the sharp 3-4 kHz "digital" band
    warmth = 0.5 + 1.5 * s             # a little low-mid body
    air = 0.0015 + 0.0035 * s          # breath/room noise level (very low)
    room_decay = 0.08 + 0.12 * s       # tiny room, not an echo
    return (
        "[0:a]highpass=f=70,lowpass=f=11500,"
        f"equalizer=f=220:t=q:w=1.2:g={warmth:.2f},"
        f"equalizer=f=3500:t=q:w=1.4:g={presence_cut:.2f},"
        "acompressor=threshold=-20dB:ratio=2.2:attack=12:release=160:makeup=2,"
        f"aecho=0.9:{room_decay:.2f}:11:0.06,"
        "aresample=44100[v];"
        f"anoisesrc=c=pink:r=44100:a={air:.4f}[n];"
        "[v][n]amix=inputs=2:duration=first:normalize=0,"
        "alimiter=limit=0.95"
    )


def humanize(src: Path, dst: Path, strength: float = 0.5) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise HumanizeError("ffmpeg was not found on PATH.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
        "-filter_complex", filter_graph(strength), "-ac", "1", "-b:a", "128k", "-f", "mp3", str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not dst.exists():
        raise HumanizeError(f"ffmpeg failed: {result.stderr.strip()[:300]}")
    return dst
