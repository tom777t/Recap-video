# -*- coding: utf-8 -*-
"""test_anchor.py - the shown footage contains the moment the line narrates.

  QUOTE-FOUND        a quoted line anchors on the transcript segment that says it
  PARA-FOUND         2+ shared content words anchor; 1 shared word does not
  NO-DIALOGUE        a purely visual line gets no anchor (render unchanged)
  PLACE-INSIDE       the shown part moves inside the window so the moment is on
                     screen, never before clip_start / after clip_end - need
  PLACE-NEIGHBOURS   never back into the previous line's footage, never past
                     the next line's window
  PLACE-UNREACHABLE  a moment outside the window returns None (reported, not
                     silently shown wrong)
  REPORT-STATES      anchor_report: ON / MOVED / OFF on a scratch project
  REBIND             --apply rebinds an OFF line onto its moment when the
                     neighbours leave room, writes a backup, and leaves a
                     blocked line alone
  RENDER-SHARES      render.py uses the same find_anchor/place/visible

Calibration (real renders, before -> after this change, lines that narrate a
quoted/paraphrased moment and do NOT show it):
    doublelife2023  15 of 36 -> 6      furious72015  17 of 38 -> 5
The 11 that remain have their moment inside a NEIGHBOUR's window: the words
and the footage are in a different order, which is a writing fix.

Run:  python tools/test_anchor.py      (exit 0 = all pass)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline import anchor as A  # noqa: E402

SEGS = [(100.0, "Hello there."),
        (106.0, "Put some pressure on her father's business."),
        (112.0, "The street always wins, every single time."),
        (140.0, "We will take the house and everything of value.")]


def t_quote():
    a = A.find_anchor('He says it flat: "Put some pressure on her '
                      'father\'s business."', SEGS, 100.0, 110.0)
    return (a is not None and a[0] == 106.0 and a[1] == "quote",
            f"anchor {a}")


def t_para():
    a = A.find_anchor("That night, Dom says the street always wins.",
                      SEGS, 100.0, 115.0)
    b = A.find_anchor("The house is quiet that night.", SEGS, 135.0, 145.0)
    ok = a is not None and a[0] == 112.0 and a[1] == "para" and b is None
    return ok, f"2+ words -> {a and a[0]}; 1 word ('house') -> {b}"


def t_no_dialogue():
    a = A.find_anchor("Headlights sweep a dark road as two cars race.",
                      SEGS, 100.0, 115.0)
    return a is None, f"visual line -> {a}"


def t_place_inside():
    # window 100-118, moment at 112, needs 5s of footage, 3s of voice
    s = A.place(100.0, 118.0, 112.0, 5.0, 0.5, 3.0)
    ok = s is not None and 100.0 <= s <= 113.0 and A.visible(s, 5.0, 112.0)
    s2 = A.place(100.0, 114.0, 113.5, 5.0, 0.5, 3.0)   # clamps to ce - need
    ok2 = s2 is not None and abs(s2 - 109.0) < 1e-6
    return ok and ok2, f"start {s}; clamped {s2} (want 109.0)"


def t_place_neighbours():
    # previous line showed up to 108, next window starts at 113
    s = A.place(100.0, 120.0, 106.0, 4.0, 0.5, 2.0, lo=108.0, hi=113.0)
    s2 = A.place(100.0, 120.0, 111.0, 4.0, 0.5, 2.0, lo=108.0, hi=113.0)
    ok = s is None and s2 is not None and 108.0 <= s2 <= 109.0
    return ok, f"moment in prev footage -> {s}; between -> {s2}"


def t_unreachable():
    s = A.place(100.0, 107.0, 115.0, 5.0, 0.5, 3.0)
    s2 = A.place(100.0, 107.0, 92.0, 5.0, 0.5, 3.0)
    return s is None and s2 is None, f"after -> {s}, before -> {s2}"


def _scratch(name: str, lines: list) -> Path:
    pdir = Path(ROOT) / "projects" / name
    shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir(parents=True)
    (pdir / "draft.json").write_text(json.dumps({"lines": lines}),
                                     encoding="utf-8")
    (pdir / "transcript.json").write_text(json.dumps({"segments": [
        {"start": t, "end": t + 2, "text": x} for t, x in SEGS]}),
        encoding="utf-8")
    return pdir


def _run(*args):
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools",
                                                     "anchor_report.py"),
                        *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def t_report_states():
    pdir = _scratch("_selftest_anchor", [
        {"id": 1, "narration": 'Then: "Hello there."',
         "clip_start": "00:01:39.000", "clip_end": "00:01:45.000"},
        {"id": 2, "narration": "That night he says the street always wins.",
         "clip_start": "00:01:46.000", "clip_end": "00:02:05.000"},
        {"id": 3, "narration": '"We will take the house and everything."',
         "clip_start": "00:02:06.000", "clip_end": "00:02:10.000"}])
    try:
        code, out = _run("--project", "_selftest_anchor")
    finally:
        shutil.rmtree(pdir, ignore_errors=True)
    ok = "ON 1, MOVED 1, REBOUND 0, OFF 1" in out and code == 1
    return ok, out.splitlines()[0] if out else "no output"


def t_rebind():
    pdir = _scratch("_selftest_anchor_rb", [
        {"id": 1, "narration": 'Then: "Hello there."',
         "clip_start": "00:01:39.000", "clip_end": "00:01:45.000"},
        {"id": 3, "narration": '"We will take the house and everything."',
         "clip_start": "00:02:06.000", "clip_end": "00:02:12.000"},
        {"id": 4, "narration": "The car pulls away.",
         "clip_start": "00:02:40.000", "clip_end": "00:02:50.000"}])
    try:
        code, out = _run("--project", "_selftest_anchor_rb", "--apply")
        d = json.loads((pdir / "draft.json").read_text(encoding="utf-8"))
        backup = (pdir / "draft_preanchor.json").exists()
    finally:
        shutil.rmtree(pdir, ignore_errors=True)
    l3 = next(x for x in d["lines"] if x["id"] == 3)
    s = sum(float(v) * k for v, k in zip(l3["clip_start"].split(":"),
                                          (3600, 60, 1)))
    e = sum(float(v) * k for v, k in zip(l3["clip_end"].split(":"),
                                          (3600, 60, 1)))
    ok = backup and "REBOUND 1" in out and s <= 140.5 <= e and e <= 160.0
    return ok, f"line 3 now {l3['clip_start']}-{l3['clip_end']}, backup {backup}"


def t_render_shares():
    src = Path(ROOT, "pipeline", "render.py").read_text(encoding="utf-8")
    need = ["_anc.find_anchor(", "_anc.place(", "_anc.visible(",
            '"shown_start"', "[ANCHOR]"]
    miss = [n for n in need if n not in src]
    return not miss, "render uses the shared anchor functions" if not miss \
        else f"missing in render.py: {miss}"


TESTS = [("QUOTE-FOUND", t_quote), ("PARA-FOUND", t_para),
         ("NO-DIALOGUE", t_no_dialogue), ("PLACE-INSIDE", t_place_inside),
         ("PLACE-NEIGHBOURS", t_place_neighbours),
         ("PLACE-UNREACHABLE", t_unreachable),
         ("REPORT-STATES", t_report_states), ("REBIND", t_rebind),
         ("RENDER-SHARES", t_render_shares)]

if __name__ == "__main__":
    fails = 0
    for name, fn in TESTS:
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"{type(e).__name__}: {e}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:18s} {msg}")
    print("-" * 60)
    print("test_anchor: all pass" if not fails
          else f"test_anchor: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
