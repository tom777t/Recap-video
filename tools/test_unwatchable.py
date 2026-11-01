# -*- coding: utf-8 -*-
"""test_unwatchable.py - [UNWATCHABLE-FOOTAGE]: no bound window on black/cards.

A synthetic source, built with ffmpeg, with every kind of footage the gate
must tell apart:

     0-10  moving test pattern                       watchable
    10-14  black                                     UNWATCHABLE
    14-20  a still white-on-black text card          UNWATCHABLE
    20-30  a DARK, MOVING scene with a few lights    watchable (night scene)
    30-40  moving test pattern                       watchable

  CATCHES-BLACK-AND-CARD  lines bound to black and to the card fail, named,
                          with their kind and source time
  NIGHT-IS-NOT-A-CARD     the dark moving scene passes; so do the ordinary ones
  SHORT-DIP-ALLOWED       a window that only grazes 0.5s of black passes
  CACHED                  a second validation measures nothing again; a new
                          source file version measures again
  NO-SOURCE-NOT-PASS      without source.mp4 the gate WARNS that it did not run
  WIRED-AND-REGISTERED    draft.py runs it; gates.json declares it an error
  TOKYODRIFT-LINE-114     the fixture draft binds line 114 to the catalogued
                          end disclaimer; on a box with the film's source.mp4
                          the gate must name it. Without the source it prints
                          NOT RUN (not PASS, not FAIL).

Run:  python tools/test_unwatchable.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline import footage as F  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="unwatch_"))
SRC = TMP / "source.mp4"


def _source() -> Path:
    if SRC.exists():
        return SRC
    s = "s=640x360:r=25"
    card = ("color=c=black:" + s + ":d=6,"
            + ",".join(f"drawbox=x={120 + (i % 2) * 40}:y={110 + i * 30}:"
                       f"w={360 - (i % 2) * 80}:h=8:color=white:t=fill"
                       for i in range(5)))
    # a night street: very dark, slow, with a white light that glows (blur)
    night = ("testsrc2=" + s + ":d=10,eq=brightness=-0.5:contrast=0.5,"
             "drawbox=x='100+t*12':y=180:w=24:h=24:color=white:t=fill,"
             "gblur=sigma=6")
    graph = (f"testsrc2={s}:d=10[a];color=c=black:{s}:d=4[b];{card}[c];"
             f"{night}[d];testsrc2={s}:d=10[e];"
             f"[a][b][c][d][e]concat=n=5:v=1:a=0,format=yuv420p[v]")
    r = subprocess.run([config.ffmpeg(), "-y", "-v", "error",
                        "-filter_complex", graph, "-map", "[v]",
                        "-c:v", "libx264", "-preset", "ultrafast", str(SRC)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-400:])
    return SRC


def _ts(x):
    return f"00:00:{x:06.3f}"


def _draft():
    lines = [(1, 2, 8), (2, 9.5, 14.5), (3, 14.5, 19.5), (4, 21, 29),
             (5, 31, 39), (6, 7, 10.5)]
    return {"lines": [{"id": i, "clip_start": _ts(a), "clip_end": _ts(b),
                       "narration": "words"} for i, a, b in lines]}


def _pdir():
    p = TMP / "proj"
    p.mkdir(exist_ok=True)
    return p


def _report(pdir, source=None):
    return F.unwatchable_report(_draft(), pdir, source or _source())


def test_catches_black_and_card():
    shutil.rmtree(_pdir() / "_cache", ignore_errors=True)
    r = _report(_pdir())
    bad = sorted(set(r["stats"]["bad"]))
    txt = " ".join(r["errors"])
    if bad != [2, 3]:
        return False, f"flagged lines {bad}, want [2, 3]: {txt[:300]}"
    if "black" not in txt or "text card" not in txt:
        return False, f"kinds not named: {txt[:300]}"
    return True, "black (line 2) and the still card (line 3) fail, named"


def test_night_not_card():
    r = _report(_pdir())
    ok = not any(x in (1, 4, 5) for x in r["stats"]["bad"])
    st = F.frame_stats(_source(), 22, 28)
    dark = max(s["dark"] for s in st)
    mean = max(s["mean"] for s in st)
    return ok, (f"dark slow night scene (dark share {dark:.2f}, mean luma "
                f"<= {mean:.0f}, a glowing light) and the pattern lines pass")


def test_short_dip_allowed():
    r = _report(_pdir())
    return 6 not in r["stats"]["bad"], ("line 6 grazes 0.5s of black at its "
                                         "end and passes")


def test_cached():
    pdir = _pdir()
    shutil.rmtree(pdir / "_cache", ignore_errors=True)
    r1 = _report(pdir)
    r2 = _report(pdir)
    src2 = TMP / "source2.mp4"
    shutil.copy(_source(), src2)
    r3 = F.unwatchable_report(_draft(), pdir, src2)
    ok = (r1["stats"]["measured"] == 6 and r2["stats"]["measured"] == 0
          and r2["stats"]["cached"] == 6 and r3["stats"]["measured"] == 6
          and r2["errors"] == r1["errors"])
    return ok, (f"measured {r1['stats']['measured']} -> "
                f"{r2['stats']['measured']} (cached), new file version -> "
                f"{r3['stats']['measured']}")


def test_no_source_not_pass():
    r = F.unwatchable_report(_draft(), _pdir(), TMP / "missing.mp4")
    ok = (not r["errors"] and r["warns"] and "did NOT run" in r["warns"][0]
          and not r["notes"])
    return ok, "no source -> a warning that it did not run, no pass note"


def test_wired_and_registered():
    src = (ROOT / "pipeline" / "draft.py").read_text(encoding="utf-8")
    reg = json.loads((ROOT / "config" / "gates.json").read_text(encoding="utf-8"))
    g = reg.get("UNWATCHABLE-FOOTAGE") or {}
    ok = ('"unwatchable_report"' in src and g.get("severity") == "error"
          and g.get("severity_source") == "declared")
    return ok, f"draft.py runs it; gates.json: {g.get('severity')}/{g.get('severity_source')}"


def test_tokyodrift_line_114():
    pdir = config.project_dir("tokyodrift2006")
    d = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    shots = json.loads((pdir / "shots.json").read_text(encoding="utf-8-sig"))
    ln = next(x for x in d["lines"] if x["id"] == 114)
    shot = next(s for s in shots["shots"]
                if s["clip_start"] == ln["clip_start"])
    if "disclaimer" not in shot["action"]:
        return False, "fixture drifted: line 114 is no longer on the disclaimer"
    if not (pdir / "source.mp4").exists():
        print("NOT RUN  TOKYODRIFT-LINE-114   the film's source.mp4 is not on "
              "this box; on the owner's laptop this case must name line 114")
        return None, ""
    r = F.unwatchable_report(d, pdir)
    return (114 in r["stats"]["bad"]), (f"line 114 ({ln['clip_start']}) "
                                        f"flagged: {114 in r['stats']['bad']}")


TESTS = {
    "CATCHES-BLACK-AND-CARD": test_catches_black_and_card,
    "NIGHT-IS-NOT-A-CARD":    test_night_not_card,
    "SHORT-DIP-ALLOWED":      test_short_dip_allowed,
    "CACHED":                 test_cached,
    "NO-SOURCE-NOT-PASS":     test_no_source_not_pass,
    "WIRED-AND-REGISTERED":   test_wired_and_registered,
    "TOKYODRIFT-LINE-114":    test_tokyodrift_line_114,
}

if __name__ == "__main__":
    bad = 0
    try:
        for name, fn in TESTS.items():
            try:
                ok, msg = fn()
            except Exception as e:
                import traceback
                traceback.print_exc()
                ok, msg = False, f"{type(e).__name__}: {e}"
            if ok is None:
                continue                     # printed NOT RUN itself
            print(f'{"PASS" if ok else "FAIL"}  {name:<24} {msg}')
            bad += (not ok)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print("-" * 60)
    print("test_unwatchable: all pass" if not bad else
          f"test_unwatchable: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
