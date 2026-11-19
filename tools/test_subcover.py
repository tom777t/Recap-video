# -*- coding: utf-8 -*-
"""test_subcover.py - burned-in subtitles are found and hidden (owner,
19 Nov: the next downloads carry subtitles in the picture).

Synthetic films, real ffmpeg: a 1280x720 frame with a 2.35:1 picture
(rows 88-632) of moving test pattern - bright, hard-edged colour bars and a
noisy checkerboard, the things a naive text detector mistakes for letters -
and white outlined subtitle lines that come and go.

  FIND-IN-PICTURE   subtitles inside the picture (row ~560) are found as a
                    band around them
  FIND-IN-BAR       subtitles in the black bar under the picture (row ~660)
                    are found there
  NO-SUBTITLES      the same moving pattern with no subtitles: nothing found
                    (a false find would crop every frame of a clean film)
  NOT-A-SIGN        text that stays HIGH in the frame (a sign, a title) is
                    not a subtitle band
  CROP-HIDES        a REAL clip built from the subtitled film: at a moment
                    with a subtitle on screen, the bottom of the output
                    carries no text; the crop keeps the picture centred
  BAR-COSTS-NOTHING subtitles in the bar: the crop is exactly the picture,
                    no picture row lost
  BLACK-MODE        SUBTITLE_COVER "black" paints the band, frame size kept
  HAND-EDIT-WINS    subtitle_band.json as edited ({"found": false}, or moved
                    rows) is taken as written, no new detection
  CACHE-AND-CENSOR  the clip cache key changes with the cover; a censor box
                    drawn on a source frame moves with the crop

Run:  python tools/test_subcover.py      (exit 0 = all pass)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline import subcover as SC  # noqa: E402

LINES = ["Where are you going tonight?", "I told you to stay home.",
         "We don't have much time.", "He knows. He always knew.",
         "Get in the car, now!", "Nobody leaves this room."]


def _film(path: Path, sub_y: int | None, dur: int = 60,
          sign: bool = False) -> None:
    """60 s: subtitles on for 3 s of every 5, a different line each time."""
    vf = "pad=1280:720:0:88:black"
    if sub_y is not None:
        for i in range(dur // 5):
            t0, t1 = i * 5 + 1, i * 5 + 4
            txt = LINES[i % len(LINES)].replace("'", "")
            vf += (f",drawtext=text='{txt}':fontcolor=white:fontsize=36:"
                   f"borderw=2:bordercolor=black:x=(w-text_w)/2:y={sub_y}:"
                   f"enable='between(t,{t0},{t1})'")
    if sign:
        vf += (",drawtext=text='MOTEL - VACANCY':fontcolor=white:"
               "fontsize=40:borderw=2:bordercolor=black:x=200:y=150")
    subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"testsrc2=s=1280x544:d={dur}:r=25", "-f", "lavfi",
                    "-i", "anullsrc=r=44100:cl=stereo", "-t", str(dur),
                    "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-preset", "veryfast", "-c:a", "aac", str(path)],
                   check=True)


_FILMS: dict = {}


def _get(kind: str) -> Path:
    if kind not in _FILMS:
        d = Path(tempfile.mkdtemp(prefix="sc_"))
        p = d / "source.mp4"
        _film(p, {"picture": 560, "bar": 660, "none": None,
                  "sign": None}[kind], sign=(kind == "sign"))
        _FILMS[kind] = p
    return _FILMS[kind]


def t_find_in_picture():
    b = SC.detect(_get("picture"), probes=60)
    ok = b["found"] and b["y0"] <= 565 and b["y1"] >= 590 and b["y0"] > 500
    return ok, (f"band {b.get('y0')}-{b.get('y1')} around the 560-600 "
                f"subtitles ({b['why']})" if ok else f"{b}")


def t_find_in_bar():
    b = SC.detect(_get("bar"), probes=60)
    ok = b["found"] and 620 <= b["y0"] <= 665 and b["y1"] >= 690
    return ok, (f"band {b.get('y0')}-{b.get('y1')}, picture "
                f"{b['content']}" if ok else f"{b}")


def t_no_subtitles():
    b = SC.detect(_get("none"), probes=60)
    return (not b["found"]), f"clean film: nothing found ({b['why']})"


def t_not_a_sign():
    b = SC.detect(_get("sign"), probes=60)
    return (not b["found"]), f"a sign at row 150: nothing found ({b['why']})"


def _pdir(kind: str, band: dict | None = None) -> Path:
    src = _get(kind)
    pd = src.parent
    if band is not None:
        (pd / "subtitle_band.json").write_text(json.dumps(band),
                                               encoding="utf-8")
    return pd


def _frame(path: Path, t: float, w: int = 1920, h: int = 1080):
    import numpy as np
    r = subprocess.run([config.ffmpeg(), "-v", "error", "-ss", f"{t:.2f}",
                        "-i", str(path), "-frames:v", "1", "-vf",
                        "format=gray", "-f", "rawvideo", "-"],
                       capture_output=True)
    return np.frombuffer(r.stdout[:w * h], np.uint8).reshape(h, w)


def t_crop_hides():
    from pipeline import render as R
    pd = _pdir("picture")
    (pd / "subtitle_band.json").unlink(missing_ok=True)
    band = SC.begin(pd, pd / "source.mp4")
    out = pd / "clip.mp4"
    aud = pd / "n.wav"
    subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-f", "lavfi",
                    "-i", "sine=f=440:d=3", str(aud)], check=True)
    saved = config.MOTION_ENABLE
    config.MOTION_ENABLE = False
    try:
        R._build_clip(config.ffmpeg(), pd / "source.mp4", 5.5, 9.5, aud, 3.0,
                      out, 1, 0.0, 0.0, "none", None, 0.0, film_audio=False,
                      src_wh=(1280, 720))
    finally:
        config.MOTION_ENABLE = saved
        SC.end()
    import numpy as np
    g = _frame(out, 1.0)                        # source t=6.5: subtitle on
    rows = SC.text_rows(g)
    lit = np.where(g.mean(axis=1) > 8)[0]
    top, bot = int(lit[0]), int(lit[-1])
    centred = abs(top - (1079 - bot)) <= 4
    text_low = float(rows[int(1080 * 0.6):].max())
    ok = band.get("found") and text_low < 0.025 and centred
    return ok, (f"crop {SC.prefix(pd).rstrip(',')}: no text in the lower "
                f"40% of the output (max row share {text_low:.3f}), picture "
                f"rows {top}-{bot}, centred" if ok else
                f"band {band}, text {text_low:.3f}, rows {top}-{bot}")


def t_bar_costs_nothing():
    pd = _pdir("bar")
    (pd / "subtitle_band.json").unlink(missing_ok=True)
    b = SC.begin(pd, pd / "source.mp4")
    try:
        r = SC.rect()
    finally:
        SC.end()
    ok = b.get("found") and r is not None and r[1] <= 90 and \
        r[1] + r[3] >= 630
    return ok, (f"kept rows {r[1]}-{r[1] + r[3]}: the whole picture "
                f"(88-632), only the bar with the subtitles goes" if ok
                else f"{b} {r}")


def t_black_mode():
    pd = _pdir("picture", {"found": True, "y0": 550, "y1": 605,
                           "src_w": 1280, "src_h": 720,
                           "content": [88, 632], "why": "test"})
    saved = config.SUBTITLE_COVER
    config.SUBTITLE_COVER = "black"
    try:
        p = SC.prefix(pd)
    finally:
        config.SUBTITLE_COVER = saved
        (pd / "subtitle_band.json").unlink(missing_ok=True)
    ok = p.startswith("drawbox=x=0:y=550:w=iw:h=55:color=black")
    return ok, (f"black: {p.rstrip(',')}" if ok else p)


def t_hand_edit_wins():
    pd = _pdir("picture", {"found": False, "why": "owner: no subtitles"})
    try:
        b1 = SC.begin(pd)
        p1 = SC.prefix()
        SC.end()
        (pd / "subtitle_band.json").write_text(json.dumps(
            {"found": True, "y0": 400, "y1": 450, "src_w": 1280,
             "src_h": 720, "content": [88, 632], "why": "by hand"}))
        SC.begin(pd)
        p2 = SC.prefix()
    finally:
        SC.end()
        (pd / "subtitle_band.json").unlink(missing_ok=True)
    ok = not b1["found"] and p1 == "" and p2 == "crop=1280:312:0:88,"
    return ok, ("found:false -> nothing covered; moved rows -> "
                f"{p2.rstrip(',')}" if ok else f"{b1} {p1!r} {p2!r}")


def t_cache_and_censor():
    from pipeline import render as R
    pd = _pdir("picture", {"found": True, "y0": 550, "y1": 605,
                           "src_w": 1280, "src_h": 720,
                           "content": [88, 632], "why": "test"})
    a = pd / "n.wav"
    a.write_bytes(b"x" * 64)
    args = (pd / "source.mp4", 5.0, 9.0, 0.0, 1, 0.0, 3.0, a)
    try:
        k_off = R._clip_signature(*args)
        SC.begin(pd)
        k_on = R._clip_signature(*args)

        class Box:
            x, y, width, height = 100, 300, 200, 100     # source pixels
        x, y, w, h = R.region_to_output(Box, 1280, 720)
    finally:
        SC.end()
        (pd / "subtitle_band.json").unlink(missing_ok=True)
    # kept frame: rows 88-550 (462 tall) -> scale 1080/462 is capped by the
    # width: f = min(1920/1280, 1080/462) = 1.5; y = (300-88)*1.5 + pad
    f = min(1920 / 1280, 1080 / 462)
    want_y = round((300 - 88) * f + (1080 - 462 * f) / 2)
    ok = k_off != k_on and abs(y - want_y) <= 1 and abs(h - 150) <= 1
    return ok, (f"cache key changes; censor box at output y={y} "
                f"(expected {want_y})" if ok else
                f"keys equal={k_off == k_on}, box {x},{y},{w},{h} vs "
                f"y {want_y}")


TESTS = [("FIND-IN-PICTURE", t_find_in_picture),
         ("FIND-IN-BAR", t_find_in_bar), ("NO-SUBTITLES", t_no_subtitles),
         ("NOT-A-SIGN", t_not_a_sign), ("CROP-HIDES", t_crop_hides),
         ("BAR-COSTS-NOTHING", t_bar_costs_nothing),
         ("BLACK-MODE", t_black_mode), ("HAND-EDIT-WINS", t_hand_edit_wins),
         ("CACHE-AND-CENSOR", t_cache_and_censor)]

if __name__ == "__main__":
    fails = 0
    try:
        for name, fn in TESTS:
            try:
                ok, msg = fn()
            except Exception as e:
                import traceback
                traceback.print_exc()
                ok, msg = False, f"{type(e).__name__}: {e}"
            fails += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {name:18s} {msg}")
    finally:
        for p in _FILMS.values():
            shutil.rmtree(p.parent, ignore_errors=True)
    print("-" * 60)
    print("test_subcover: all pass" if not fails
          else f"test_subcover: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
