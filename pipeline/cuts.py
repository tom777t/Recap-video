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

Scanning a 2h film takes ~10 minutes, so the result is cached in
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


def _probe(src: Path):
    import subprocess
    r = subprocess.run([config.ffprobe(), "-v", "error", "-select_streams",
                        "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate,nb_frames:"
                        "format=duration", "-of", "json", str(src)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    d = json.loads(r.stdout or "{}")
    s = (d.get("streams") or [{}])[0]
    num, den = str(s.get("r_frame_rate") or "24/1").split("/")
    fps = float(num) / float(den or 1)
    dur = float((d.get("format") or {}).get("duration") or 0)
    return int(s["width"]), int(s["height"]), fps, dur


def ffmpeg_cuts(src: Path, threshold: float = DEFAULT_THRESHOLD,
                min_scene_len: int = DEFAULT_MIN_SCENE, progress: bool = True):
    """Cut times from PySceneDetect's own ContentDetector, fed frames that
    ffmpeg decodes (multi-threaded) and scales down while decoding.

    Lost in the Stars, 20 Nov: the OpenCV-decoded scan ran at 15 frames/s on
    the owner's PC - 3 h 10 min for a 2 h film, against ~11 min (260 fps)
    for the same code on Linux. The detector is not the slow part, the
    decode is. The frames are scaled by PySceneDetect's own auto-downscale
    rule (width // 256), so the detector sees what it saw before: on the
    film's first 10 minutes this finds 130 of PySceneDetect's 134 cuts to
    the frame and the rest within 0.5 s (the snap tolerance is 3 s).
    """
    import subprocess
    import time
    import inspect
    import numpy as np
    from scenedetect.detectors import ContentDetector
    try:
        from scenedetect import FrameTimecode
    except ImportError:                                   # older releases
        from scenedetect.frame_timecode import FrameTimecode
    W, H, fps, dur = _probe(src)
    k = max(1, W // 256)
    w, h = max(2, W // k), max(2, H // k)
    det = ContentDetector(threshold=threshold, min_scene_len=min_scene_len)
    takes_tc = "timecode" in inspect.signature(det.process_frame).parameters
    from pipeline.ffcmd import fit
    p = subprocess.Popen(fit([config.ffmpeg(), "-v", "error", "-threads",
                              "0", "-i", str(src), "-map", "0:v:0", "-an",
                              "-sn", "-vf", f"scale={w}:{h}:flags=bilinear",
                              "-pix_fmt", "bgr24", "-f", "rawvideo", "-"]),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         bufsize=10 ** 7)
    n = w * h * 3
    i, marks, t0, shown = 0, [0.0], time.time(), -1
    total = max(1, int(dur * fps))
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        frame = np.frombuffer(b, np.uint8).reshape(h, w, 3)
        out = det.process_frame(FrameTimecode(i, fps) if takes_tc else i,
                                frame)
        for c in out or []:
            sec = getattr(c, "seconds", None)
            if sec is None:
                sec = (c.get_seconds() if hasattr(c, "get_seconds")
                       else float(c) / fps)
            marks.append(round(float(sec), 3))
        i += 1
        pct = i * 20 // total
        if progress and pct != shown:
            shown = pct
            el = time.time() - t0
            rate = i / el if el > 0 else 0
            left = (total - i) / rate if rate > 0 else 0
            print(f"  cuts: {min(100, pct * 5):3d}%  {len(marks) - 1} cut(s)"
                  f"  {rate:.0f} frames/s  ~{left / 60:.0f} min left",
                  flush=True)
    err = p.stderr.read().decode("utf-8", "replace") if p.stderr else ""
    p.wait()
    if p.returncode != 0 or i == 0:
        raise RuntimeError(f"ffmpeg decode failed (rc {p.returncode}): "
                           f"{err[-300:]}")
    marks.append(round(i / fps, 3))
    el = time.time() - t0
    if progress:
        print(f"  cuts: {len(marks) - 2} cut(s) in {i} frames, "
              f"{el / 60:.1f} min ({i / max(el, 1e-6):.0f} frames/s)")
    return sorted(set(marks))


def detect_cuts(project: str, threshold: float = DEFAULT_THRESHOLD,
                min_scene_len: int = DEFAULT_MIN_SCENE, progress: bool = True):
    """Scan source.mp4 and cache the cut list. Returns the cuts, or None.

    Raises nothing - a missing source or a missing scenedetect install is a
    normal answer here, reported by the caller rather than crashing a run.
    ffmpeg decodes (ffmpeg_cuts); PySceneDetect's own OpenCV reader is the
    fallback when that fails.
    """
    src = config.project_dir(project) / "source.mp4"
    if not src.exists():
        return None
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector
    except ImportError:
        return None

    try:
        cuts = ffmpeg_cuts(src, threshold, min_scene_len, progress)
        json.dump({"threshold": threshold, "min_scene_len": min_scene_len,
                   "decoder": "ffmpeg", "cuts": cuts},
                  io.open(cache_path(project), "w", encoding="utf-8"))
        return cuts
    except Exception as e:
        print(f"  cuts: the ffmpeg reader failed ({type(e).__name__}: "
              f"{str(e)[:200]}) - falling back to PySceneDetect's own "
              f"reader, which can be much slower")

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
