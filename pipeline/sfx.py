"""
Sound design. We SYNTHESIZE the SFX with ffmpeg (no downloads, no copyright):
  - whoosh : filtered noise sweep for transitions
  - boom   : low sine thump for reveals / big action hits
  - riser  : rising tone for cliffhangers / tension builds
  - sting  : short bright hit for the title / channel intro

Each is rendered once into assets/sfx/ and reused. They are mixed UNDER the
music and well below the voice at render time.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console

import config

console = Console()

SFX_DIR = config.ROOT / "assets" / "sfx"


def _run(cmd: list[str]):
    subprocess.run(cmd, capture_output=True, text=True)


def _gen(ff: str, name: str, dur: float, afilter: str, src: str) -> Path:
    out = SFX_DIR / f"{name}.wav"
    cmd = [ff, "-y", "-f", "lavfi", "-i", src, "-t", f"{dur:.3f}",
           "-af", afilter, "-ar", "48000", "-ac", "2", str(out)]
    _run(cmd)
    return out


def ensure_sfx() -> dict:
    """Generate the SFX set if missing. Returns {name: path}."""
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    ff = config.ffmpeg()
    out = {}

    # whoosh: white noise, band-swept, quick in/out
    p = SFX_DIR / "whoosh.wav"
    if not p.exists():
        _gen(ff, "whoosh", 0.6,
             "highpass=f=300,lowpass=f=6000,"
             "afade=t=in:st=0:d=0.15,afade=t=out:st=0.3:d=0.3,volume=0.9",
             "anoisesrc=color=white:amplitude=0.4")
    out["whoosh"] = p

    # boom: low sine thump with fast decay
    p = SFX_DIR / "boom.wav"
    if not p.exists():
        _gen(ff, "boom", 1.2,
             "lowpass=f=180,afade=t=out:st=0.1:d=1.0,volume=1.4",
             "sine=frequency=55:beep_factor=0")
    out["boom"] = p

    # riser: tone sweeping up in pitch + volume
    p = SFX_DIR / "riser.wav"
    if not p.exists():
        # frequency ramps via sine with increasing freq using aevalsrc
        _gen(ff, "riser", 2.0,
             "afade=t=in:st=0:d=1.8,volume=0.6",
             "aevalsrc='0.3*sin(2*PI*(200+150*t)*t)':s=48000:d=2.0")
    out["riser"] = p

    # sting: bright short chord hit
    p = SFX_DIR / "sting.wav"
    if not p.exists():
        _gen(ff, "sting", 0.8,
             "afade=t=out:st=0.15:d=0.6,volume=0.7",
             "aevalsrc='0.25*sin(2*PI*523*t)+0.2*sin(2*PI*659*t)+0.2*sin(2*PI*784*t)':s=48000:d=0.8")
    out["sting"] = p

    return out


# Default placement rules (used by the renderer):
#   - whoosh at every transition (clip boundary)
#   - boom at the START of each "hold" action beat (the reveal)
#   - sting once, at the channel intro line (delivery == "intro")
#   - riser optionally on lines with delivery == "mystery" right before a hold
def plan_events(draft: dict, boundaries: list[float]) -> list[dict]:
    """
    Given the line list and the absolute start-time of each clip on the final
    timeline (boundaries[i] = start of clip i), return SFX events:
    [{"sfx": name, "at": seconds, "gain": db}, ...]
    Only triggered when config.SFX_ENABLE is True.
    """
    events: list[dict] = []
    if not getattr(config, "SFX_ENABLE", False):
        return events

    # 2026-10-20 REVEALS AND HOLDS ONLY.
    # This used to emit a transition whoosh before EVERY clip (so ~190 whooshes
    # on a 190-line draft), a sting on the intro and a riser on every mystery
    # beat. "Use these in moderation" is the one point every sound-design guide
    # agrees on, and a whoosh on every cut is the most recognisable mark of a
    # cheap recap.
    # The filtering lives HERE, at the point the events are decided, not as a
    # screen applied afterwards in render.py: the first version of this change
    # filtered downstream on `ev["line_id"]`, and since these dicts never
    # carried a line_id it silently dropped every single event while printing a
    # confident count. Every event now carries its line id.
    lines = draft["lines"]
    for i, ln in enumerate(lines):
        at = boundaries[i] if i < len(boundaries) else 0.0
        lid = ln.get("id")
        deliv = str(ln.get("delivery") or "normal")
        is_hold = (ln.get("narration_silence_seconds") is not None
                   or bool(ln.get("hold")))
        # A reveal gets a low boom ON the line.
        if deliv == "reveal" and config.SFX_BOOM:
            events.append({"sfx": "boom", "at": at,
                           "gain": config.SFX_BOOM_DB, "line_id": lid,
                           "why": "reveal"})
        # A hold gets one boom as the picture takes over.
        elif is_hold and config.SFX_BOOM:
            events.append({"sfx": "boom", "at": at,
                           "gain": config.SFX_BOOM_DB, "line_id": lid,
                           "why": "hold"})
    return events
