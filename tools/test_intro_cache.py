# -*- coding: utf-8 -*-
"""test_intro_cache.py - the intro block is reused only when nothing it uses changed.

  REUSED-WHEN-UNCHANGED  a second render of the same fixture reuses the cached
                         block: same intro length, same recorded footage (the
                         censor audit and freeze trace read it)
  STORY-TEXT-KEEPS-CACHE editing a story line's TEXT keeps the same key
  REBUILT-ON-CHANGE      editing an intro line, a clip window or the shots file
                         changes the key, so the block is rebuilt

Run:  python tools/test_intro_cache.py      (exit 0 = all pass)
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import test_render_smoke as smoke  # noqa: E402


def _render(pdir, draft):
    from pipeline.render import render
    from pipeline import intro as _intro
    nar = smoke._narration_for(pdir, draft["lines"])
    buf = io.StringIO()
    with redirect_stdout(buf):
        render(smoke.PROJ, draft, nar, music=None, captions=False,
               keep_temp=False, force_clips=False)
    tl = json.loads((pdir / "timeline.json").read_text(encoding="utf-8"))
    return (buf.getvalue(), float(tl.get("intro_offset") or 0),
            [dict(u) for u in _intro.used_footage()])


def main() -> int:
    from pipeline import intro as _intro
    orig = smoke._stub_intro_tts()
    restore = smoke._no_stems()
    bad = 0
    try:
        pdir, draft = smoke._setup()
        out1, off1, fp1 = _render(pdir, draft)
        out2, off2, fp2 = _render(pdir, draft)
        ok = ("reused from cache" in out2 and "reused from cache" not in out1
              and abs(off1 - off2) < 1e-3 and fp1 == fp2 and off1 > 0)
        print(f"{'PASS' if ok else 'FAIL'}  REUSED-WHEN-UNCHANGED   intro "
              f"{off1:.2f}s then {off2:.2f}s, footage records "
              f"{len(fp1)} == {len(fp2)}: {fp1 == fp2}, second run reused: "
              f"{'reused from cache' in out2}")
        bad += 0 if ok else 1

        k0 = _intro._intro_cache_key(smoke.PROJ)
        story = next(l for l in draft["lines"] if l.get("clip_start")
                     and str(l.get("narration") or "").strip())
        story["narration"] = story["narration"] + " Still."
        smoke._write(pdir, draft, json.loads((pdir / "shots.json").read_text()))
        k1 = _intro._intro_cache_key(smoke.PROJ)
        ok = k0 == k1
        print(f"{'PASS' if ok else 'FAIL'}  STORY-TEXT-KEEPS-CACHE  key "
              f"{'unchanged' if ok else 'changed'} after a story text edit")
        bad += 0 if ok else 1

        changed = []
        intro_ln = next(l for l in draft["lines"] if l.get("over_montage"))
        intro_ln["narration"] += " Twice."
        smoke._write(pdir, draft, json.loads((pdir / "shots.json").read_text()))
        changed.append(("intro line", _intro._intro_cache_key(smoke.PROJ) != k1))
        k2 = _intro._intro_cache_key(smoke.PROJ)
        story["clip_end"] = "00:00:18.5"
        smoke._write(pdir, draft, json.loads((pdir / "shots.json").read_text()))
        changed.append(("clip window", _intro._intro_cache_key(smoke.PROJ) != k2))
        k3 = _intro._intro_cache_key(smoke.PROJ)
        sh = json.loads((pdir / "shots.json").read_text())
        sh["shots"][0]["censor"] = "blur"
        sh["shots"][0]["censor_region"] = {"x": 1, "y": 1, "width": 10, "height": 10}
        smoke._write(pdir, draft, sh)
        changed.append(("shots.json", _intro._intro_cache_key(smoke.PROJ) != k3))
        ok = all(c for _n, c in changed)
        print(f"{'PASS' if ok else 'FAIL'}  REBUILT-ON-CHANGE       "
              + ", ".join(f"{n}: {'new key' if c else 'SAME KEY'}" for n, c in changed))
        bad += 0 if ok else 1
    finally:
        restore()
        _intro._tts_line = orig
        smoke._teardown()
    print("-" * 60)
    print(f"test_intro_cache: {bad} FAILURE(S)" if bad else "test_intro_cache: all pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
