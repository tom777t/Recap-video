# -*- coding: utf-8 -*-
"""test_cuts_fast.py - the cut scan decodes with ffmpeg and finds the same
cuts PySceneDetect does.

Lost in the Stars, 20 Nov: the OpenCV-decoded scan ran at 15 frames/s on
the owner's PC (3 h 10 min for a 2 h film). cuts.ffmpeg_cuts feeds
PySceneDetect's own ContentDetector frames that ffmpeg decodes and scales.

  FINDS-THE-CUTS     a film of 5 shots (4 known cuts) - every cut found to
                     the frame, nothing extra
  SAME-AS-PYSCENE    the same cuts as PySceneDetect's own reader
  CACHE-WRITTEN      detect_cuts writes _cuts.json with decoder: ffmpeg
  FALLBACK           when the ffmpeg reader fails, the old reader still
                     gives the cuts

    python tools/test_cuts_fast.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline import cuts as C  # noqa: E402

PROJ = "_selftest_cuts"
CUTS = [3.0, 5.5, 9.0, 11.0]          # seconds, at 24 fps: frames 72,132,...


def _film(path: Path) -> None:
    srcs = ["testsrc2=size=640x272:rate=24", "mandelbrot=size=640x272:rate=24",
            "smptebars=size=640x272:rate=24", "rgbtestsrc=size=640x272:rate=24",
            "cellauto=size=640x272:rate=24"]
    edges = [0.0] + CUTS + [13.0]
    ins = []
    for i, s in enumerate(srcs):
        ins += ["-f", "lavfi", "-t", f"{edges[i + 1] - edges[i]}", "-i", s]
    g = "".join(f"[{i}:v]format=yuv420p,setsar=1[s{i}];"
                for i in range(len(srcs))) + \
        "".join(f"[s{i}]" for i in range(len(srcs))) + \
        f"concat=n={len(srcs)}:v=1:a=0[v]"
    subprocess.run([config.ffmpeg(), "-v", "error", "-y", *ins,
                    "-filter_complex", g, "-map", "[v]", "-c:v", "libx264",
                    "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    str(path)], check=True)


def _pyscene(path: Path) -> list:
    from scenedetect import open_video, SceneManager
    from scenedetect.detectors import ContentDetector
    v = open_video(str(path))
    sm = SceneManager()
    sm.add_detector(ContentDetector(threshold=C.DEFAULT_THRESHOLD,
                                    min_scene_len=C.DEFAULT_MIN_SCENE))
    sm.detect_scenes(v, show_progress=False)
    m = set()
    for a, b in sm.get_scene_list():
        m.add(round(a.seconds, 3))
        m.add(round(b.seconds, 3))
    return sorted(m)


def main() -> int:
    try:
        import scenedetect  # noqa: F401
    except ImportError:
        print("SKIP  scenedetect not installed (pip install scenedetect)")
        return 0
    pd = config.project_dir(PROJ)
    shutil.rmtree(pd, ignore_errors=True)
    pd.mkdir(parents=True)
    res = []
    try:
        src = pd / "source.mp4"
        _film(src)
        got = C.ffmpeg_cuts(src, progress=False)
        inner = [c for c in got if 0.01 < c < 12.99]
        ok = len(inner) == len(CUTS) and all(
            abs(a - b) <= 1 / 24 + 1e-6 for a, b in zip(inner, CUTS))
        res.append(("FINDS-THE-CUTS", ok, f"found {inner} (want {CUTS})"))
        ref = _pyscene(src)
        same = len(ref) == len(got) and all(abs(a - b) <= 1 / 24 + 1e-6
                                            for a, b in zip(ref, got))
        res.append(("SAME-AS-PYSCENE", same, f"ffmpeg {got} | pyscene {ref}"))
        cj = C.detect_cuts(PROJ, progress=False)
        meta = json.loads((pd / "_cuts.json").read_text(encoding="utf-8"))
        res.append(("CACHE-WRITTEN", meta.get("decoder") == "ffmpeg"
                    and meta.get("cuts") == cj, f"decoder "
                    f"{meta.get('decoder')}, {len(cj or [])} marks"))
        saved = C.ffmpeg_cuts

        def boom(*a, **k):
            raise RuntimeError("simulated decode failure")
        C.ffmpeg_cuts = boom
        try:
            fb = C.detect_cuts(PROJ, progress=False)
        finally:
            C.ffmpeg_cuts = saved
        res.append(("FALLBACK", bool(fb) and len(fb) == len(ref),
                    f"old reader gave {len(fb or [])} marks"))
    finally:
        shutil.rmtree(pd, ignore_errors=True)
    bad = 0
    for name, ok, msg in res:
        print(f'{"PASS" if ok else "FAIL"}  {name:<16} {msg}')
        bad += not ok
    print("-" * 60)
    print("test_cuts_fast: all pass" if not bad else
          f"test_cuts_fast: {bad} FAILURE(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
