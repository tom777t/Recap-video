# -*- coding: utf-8 -*-
"""test_compare_transcripts.py - the comparison says whether dialogue was
lost, not just how much of the film the segments span (20 Nov: the VAD pass
on Lost in the Stars read "usable 27% against 54%" while it held MORE words).

  WORDS-SHOWN    the table carries a words column for both transcripts
  TIGHT-NOT-LOST a tight transcript with the same words in every bin is not
                 flagged, though its coverage % is far lower
  DROP-FLAGGED   a bin where the new one lost most of the words is flagged

Run:  python tools/test_compare_transcripts.py      (exit 0 = all pass)
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import compare_transcripts as CT  # noqa: E402

PROJ = "_test_compare_transcripts"


def _run(new_drop_bin: int | None) -> str:
    pdir = Path(config.project_dir(PROJ))
    pdir.mkdir(parents=True, exist_ok=True)
    old, new = [], []
    for i in range(240):                      # 40 minutes, a line every 10 s
        t = i * 10.0
        txt = "he says the car is gone and she must run now"
        old.append({"start": t, "end": t + 9.5, "text": txt})     # loose
        if new_drop_bin is not None and new_drop_bin * 600 <= t < \
                (new_drop_bin + 1) * 600:
            continue
        new.append({"start": t + 1.0, "end": t + 3.0, "text": txt})  # tight
    (pdir / "old.json").write_text(json.dumps(
        {"duration": 2400, "segments": old}), encoding="utf-8")
    (pdir / "new.json").write_text(json.dumps(
        {"duration": 2400, "segments": new}), encoding="utf-8")
    buf = io.StringIO()
    argv = sys.argv
    sys.argv = ["x", PROJ, "--old", "old.json", "--new", "new.json"]
    try:
        with contextlib.redirect_stdout(buf):
            CT.main()
    finally:
        sys.argv = argv
    return buf.getvalue()


def t_words_shown():
    out = _run(None)
    return "words" in out.splitlines()[0], out.splitlines()[0]


def t_tight_not_lost():
    out = _run(None)
    ok = "-> 0 stretch(es)" in out and "LOST" not in out.replace(
        "lost dialogue", "")
    return ok, ("tight transcript, same words: nothing flagged" if ok
                else out)


def t_drop_flagged():
    out = _run(2)
    ok = "-> 1 stretch(es)" in out and "  20m  old" in out
    return ok, ("the 20-30 min bin the new pass dropped is flagged" if ok
                else out)


TESTS = [("WORDS-SHOWN", t_words_shown), ("TIGHT-NOT-LOST", t_tight_not_lost),
         ("DROP-FLAGGED", t_drop_flagged)]

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
            print(f"{'PASS' if ok else 'FAIL'}  {name:15s} {msg}")
    finally:
        shutil.rmtree(Path(config.project_dir(PROJ)), ignore_errors=True)
    print("-" * 60)
    print("test_compare_transcripts: all pass" if not fails
          else f"test_compare_transcripts: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
