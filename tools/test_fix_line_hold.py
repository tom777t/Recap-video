# -*- coding: utf-8 -*-
"""test_fix_line_hold.py - fix_line --hold sets a hold's length, safely.

  HOLD-SET        a hold given a length that fits: narration_silence_seconds
                  and clip_end change in draft.json AND its act file; the
                  window starts where it did
  HOLD-CLASH      a length that would run into the next line's footage is
                  refused, says how much fits, and changes nothing
  NOT-A-HOLD      a narrated line is refused

Run:  python tools/test_fix_line_hold.py      (exit 0 = all pass)
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


def main() -> int:
    import shutil
    import fix_line as FL
    import test_write_slots as TWS
    import write_api as W
    import write_slots as WS
    TWS.test_draft_slots()
    pdir, proj = TWS.PDIR, TWS.PROJ
    d = json.loads((pdir / "draft.json").read_text(encoding="utf-8"))
    lines = d["lines"]
    starts = sorted(WS._pt(l["clip_start"]) for l in lines
                    if l.get("clip_start"))
    hold = None
    for l in lines:
        if str(l.get("narration") or "").strip() or not l.get("clip_start"):
            continue
        a0 = WS._pt(l["clip_start"])
        nxt = min((x for x in starts if x > a0 + 1e-3), default=a0 + 30)
        if 3.0 <= nxt - a0 <= 27.0:
            hold, room = l, nxt - a0
            break
    if hold is None:
        print("FAIL  no hold with room in the fixture")
        return 1
    lid = str(hold["id"])
    want = round(min(room - 0.5, 29.0), 1)
    files = [pdir / "draft.json"] + sorted((pdir / "draft.json.d").glob(
        "act*.json"))
    before = {f: f.read_bytes() for f in files}
    b2 = io.StringIO()
    with redirect_stdout(b2):
        rc_c = FL.main(["--project", proj, "--line", lid, "--hold",
                        f"{room + 2.0:.1f}"])
    clash = (rc_c == 2 and "at most" in b2.getvalue()
             and all(f.read_bytes() == b for f, b in before.items()))
    narrated = next(l for l in lines if str(l.get("narration") or "").strip())
    with redirect_stdout(io.StringIO()):
        rc_n = FL.main(["--project", proj, "--line", str(narrated["id"]),
                        "--hold", "5"])
    b1 = io.StringIO()
    with redirect_stdout(b1):
        rc = FL.main(["--project", proj, "--line", lid, "--hold", str(want)])
    d2 = json.loads((pdir / "draft.json").read_text(encoding="utf-8"))
    h2 = next(l for l in d2["lines"] if str(l["id"]) == lid)
    owner = W.act_of_lines(pdir)
    k, own = owner.get(int(lid), (None, None))
    act = [l for f in (pdir / "draft.json.d").glob(f"act{k}.json")
           for l in json.loads(f.read_text(encoding="utf-8"))["lines"]
           if l.get("id") == own]
    ok_set = (rc in (0, 2) and "saved" in b1.getvalue()
              and h2.get("narration_silence_seconds") == want
              and h2["clip_start"] == hold["clip_start"]
              and abs(WS._pt(h2["clip_end"]) - WS._pt(hold["clip_start"])
                      - want) < 0.01
              and act and act[0].get("clip_end") == h2["clip_end"])
    cases = [("HOLD-SET", ok_set, f"line {lid} held {want} s (room "
              f"{room:.1f} s); draft and act file agree"),
             ("HOLD-CLASH", clash, "too long -> refused, says what fits, "
              "files unchanged"),
             ("NOT-A-HOLD", rc_n == 1, "a narrated line is refused")]
    shutil.rmtree(config.project_dir("_selftest_writeplan"), ignore_errors=True)
    bad = 0
    for n, ok, m in cases:
        print(f"{'PASS' if ok else 'FAIL'}  {n:<11} {m}")
        bad += not ok
    if bad:
        print(b1.getvalue()[-800:])
    print("-" * 60)
    print(f"test_fix_line_hold: {bad} FAILURE(S)" if bad
          else "test_fix_line_hold: all pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
