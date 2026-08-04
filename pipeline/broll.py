"""
B-roll pool: a curated set of action/scenery shots a script can pull from by
label (e.g. "A4"), instead of being tied to the plot moment. This lets the
recap show mostly ACTION footage even while the narration covers dialogue —
exactly how review-phim channels keep the energy up.

Each pool entry: label -> {start, end, crop_top, quality, note}
A line in draft.json sets  "pool": "A4"  and the renderer resolves it to a
clip, applying a small in-point jitter (so repeated uses never look identical)
and an optional top crop (to hide burned-in credit text on B-roll).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from rich.console import Console

import config

console = Console()


def broll_path(project: str) -> Path:
    return config.project_dir(project) / "broll.json"


def load(project: str) -> dict:
    p = broll_path(project)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        return data.get("pool", data)
    except Exception as e:
        console.print(f"[red]broll.json is invalid:[/] {e}")
        return {}


def resolve(pool: dict, label: str, need_dur: float, seed: int) -> dict | None:
    """
    Resolve a pool label to a concrete clip window long enough for need_dur.
    Applies deterministic in-point jitter (seeded by line id) so repeated uses
    of the same shot pick different sub-windows.
    Returns {start, end, crop_top} or None if the label is unknown.
    """
    entry = pool.get(label)
    if not entry:
        return None
    a = float(entry["start"])
    b = float(entry["end"])
    span = max(0.1, b - a)
    crop_top = float(entry.get("crop_top", 0.0))

    # how much room to jitter the in-point while still covering need_dur
    slack = max(0.0, span - need_dur)
    rng = random.Random(f"{label}:{seed}")
    offset = rng.uniform(0.0, slack) if slack > 0.4 else 0.0
    start = a + offset

    end = min(b, start + max(need_dur, 0.5))
    if end - start < 0.5:
        start = max(a, b - 0.5)
        end = b
    return {"start": start, "end": end, "crop_top": crop_top}


STARTER = {
    "A1": {"start": 55.0, "end": 63.0, "crop_top": 0.14, "quality": "good",
           "note": "shark B-roll (credits) - top-crop hides names"},
    "A2": {"start": 301.0, "end": 304.5, "crop_top": 0.0, "quality": "strong",
           "note": "gore - severed limb in hands"},
    "A3": {"start": 295.0, "end": 301.0, "crop_top": 0.0, "quality": "strong",
           "note": "girl screaming, bloody"},
    "A4": {"start": 305.0, "end": 308.5, "crop_top": 0.0, "quality": "best",
           "note": "shark surfacing, jaws open"},
    "A5": {"start": 308.0, "end": 325.0, "crop_top": 0.0, "quality": "good",
           "note": "thrashing / drowning splashes"},
    "A6": {"start": 330.0, "end": 355.0, "crop_top": 0.0, "quality": "good",
           "note": "dorsal fin + floating remains"},
    "A7": {"start": 1745.0, "end": 1749.0, "crop_top": 0.0, "quality": "clean",
           "note": "clean dorsal fin at sunset (29:05)"},
    "A8": {"start": 3010.0, "end": 3020.0, "crop_top": 0.0, "quality": "good",
           "note": "diver descending silhouette (50:10)"},
    "A9": {"start": 3090.0, "end": 3160.0, "crop_top": 0.0, "quality": "good",
           "note": "diver + shark underwater (51:30)"},
    "A10": {"start": 3285.0, "end": 3297.0, "crop_top": 0.0, "quality": "good",
            "note": "diver passing shark (54:45)"},
    "A11": {"start": 3245.0, "end": 3265.0, "crop_top": 0.0, "quality": "good",
            "note": "shark hits boat / prop in mouth (54:05)"},
    "A12": {"start": 3685.0, "end": 3718.0, "crop_top": 0.0, "quality": "best",
            "note": "explosion + sharks airborne (1:01:25)"},
    "A13": {"start": 3030.0, "end": 3040.0, "crop_top": 0.0, "quality": "ok",
            "note": "scenic lake establisher (50:30)"},
}


def scaffold(project: str) -> Path:
    p = broll_path(project)
    if p.exists():
        console.print(f"[yellow]broll.json already exists[/], not overwriting: {p}")
        return p
    p.write_text(json.dumps({"pool": STARTER}, indent=2), encoding="utf-8")
    console.print(f"[green]Wrote starter broll.json:[/] {p}")
    console.print("  Edit the start/end timestamps to match your film's action shots.")
    return p


def summary(project: str):
    pool = load(project)
    if not pool:
        console.print("[yellow]No broll.json (or empty).[/] Run: recap.py broll --project NAME")
        return None
    console.print(f"[bold]B-roll pool[/] ({len(pool)} shots):")
    for label, e in pool.items():
        dur = float(e["end"]) - float(e["start"])
        console.print(f"  {label:<4} {dur:5.1f}s  {e.get('quality', '?'):<6} "
                      f"{e.get('note', '')}")
