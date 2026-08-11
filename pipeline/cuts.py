"""Scene cuts as a snap grid for catalogue boundaries.

A shot window that starts several seconds off a real visual cut spends those
seconds showing the *previous* scene. Measured on Shutter Island, the worst case
was clip:01:52:40.0 - 6.0s early at the start, on a reveal line - so the first
six seconds of that clip play the wrong scene under a line about Chuck giving
his real name. Mild, unnoticed, and entirely machine-preventable.

What this module does NOT do: replace the catalogue. PySceneDetect returns
CUTS; a catalogue entry is a MOMENT, which usually spans several cuts (median
detected segment on Shutter Island was 3.9s, while a narration line needs
9-25s). Grouping cuts into moments is a judgement about the story. So the cuts
are a grid to snap to, not a catalogue to adopt.

Measured basis for the default tolerance (Shutter Island, 62 hand boundaries vs
1906 detected cuts):

    < 1s   39%
    1-3s   48%     -> 87% already within 3s
    3-10s  13%
    > 10s   0%     -> the detector missed no scene at all

87% already land within 3s, so snapping does not distort an existing catalogue -
it only pulls in the 13% that drifted.

Scanning a 2h film takes ~11 minutes, so the result is cached in
projects/<p>/_cuts.json and reused. Cache format matches the one written by the
diagnostic scripts, so an existing cache is picked up as-is.
"""
from __future__ import annotations

import io
import json
from bisect import bisect_left
from pathlib import Path

import config

DEFAULT_THRESHOLD = 27.0     # ContentDetector sensitivity
DEFAULT_MIN_SCENE = 15       # frames
DEFAULT_TOLERANCE = 3.0      # seconds; see the distribution above


def cache_path(project: str) -> Path:
    return config.project_dir(project) / "_cuts.json"


def load_cuts(project: str):
    """Sorted cut times in seconds, or None when no scan has been done."""
    p = cache_path(project)
    if not p.exists():
        return None
    try:
        data = json.load(io.open(p, encoding="utf-8"))
        cuts = data.get("cuts") or []
        return sorted(float(c) for c in cuts) or None
    except Exception:
        return None


def detect_cuts(project: str, threshold: float = DEFAULT_THRESHOLD,
                min_scene_len: int = DEFAULT_MIN_SCENE, progress: bool = True):
    """Scan source.mp4 and cache the cut list. Returns the cuts, or None.

    Raises nothing - a missing source or a missing scenedetect install is a
    normal answer here, reported by the caller rather than crashing a run.
    """
    src = config.project_dir(project) / "source.mp4"
    if not src.exists():
        return None
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector
    except ImportError:
        return None

    video = open_video(str(src))
    sm = SceneManager()
    sm.add_detector(ContentDetector(threshold=threshold, min_scene_len=min_scene_len))
    sm.detect_scenes(video, show_progress=progress)

    marks = set()
    for a, b in sm.get_scene_list():
        marks.add(round(a.seconds, 3))
        marks.add(round(b.seconds, 3))
    cuts = sorted(marks)

    json.dump({"threshold": threshold, "min_scene_len": min_scene_len,
               "cuts": cuts},
              io.open(cache_path(project), "w", encoding="utf-8"))
    return cuts


def nearest_distance(cuts, t: float) -> float:
    """Seconds from t to the closest cut."""
    i = bisect_left(cuts, t)
    best = float("inf")
    for j in (i - 1, i, i + 1):
        if 0 <= j < len(cuts):
            best = min(best, abs(cuts[j] - t))
    return best


def snap_report(project: str, shot_index, tolerance: float = DEFAULT_TOLERANCE) -> dict:
    """How far the catalogue boundaries sit from real cuts.

    shot_index: [(start_sec, end_sec, depicts, family, shot_id)] - the tuple
    draft._load_shot_index already produces.

    Returns {"measured": bool, "reason", "total", "off", "worst", "offenders"}.
    `offenders` is [(shot_id, "start"|"end", seconds, distance)] worst first.

    No-ops loudly rather than silently when there is no cut cache: a boundary
    check with no grid to check against is an unknown, not a pass.
    """
    out = {"measured": False, "reason": "", "total": 0, "off": 0,
           "worst": 0.0, "offenders": [], "tolerance": tolerance}
    if not shot_index:
        out["reason"] = "no shots.json"
        return out
    cuts = load_cuts(project)
    if not cuts:
        out["reason"] = "no _cuts.json - run `recap.py cuts --project <p>` once (~11 min)"
        return out

    rows = []
    for a, b, _dep, _fam, sid in shot_index:
        for kind, t in (("start", a), ("end", b)):
            d = nearest_distance(cuts, t)
            rows.append((d, sid, kind, t))
    rows.sort(reverse=True)

    out["measured"] = True
    out["total"] = len(rows)
    out["off"] = sum(1 for d, _s, _k, _t in rows if d > tolerance)
    out["worst"] = rows[0][0] if rows else 0.0
    out["offenders"] = [(sid, kind, t, d) for d, sid, kind, t in rows if d > tolerance]
    out["cuts"] = len(cuts)
    return out
