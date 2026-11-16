# -*- coding: utf-8 -*-
"""test_censor_flags.py - tools/censor_flags.py lists and clears blur flags.

  LIST       an unregioned flag is listed as "render refuses this", a
             regioned one with its box
  CLEAR      --clear sets it to none with the note recorded, and the policy
             check is clean after; --clear without --note is refused; an
             unknown clip_start changes nothing

Run:  python tools/test_censor_flags.py      (exit 0 = all pass)
"""
from __future__ import annotations

import io
import json
import shutil
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402

PROJ = "_selftest_censorflags"


def main() -> int:
    import censor_flags as CF
    from pipeline import censor
    d = Path(config.project_dir(PROJ))
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    shots = {"shots": [
        {"clip_start": "00:01:00.000", "clip_end": "00:01:05.000",
         "censor": "blur_light", "action": "party guests in dresses"},
        {"clip_start": "00:02:00.000", "clip_end": "00:02:05.000",
         "censor": "blur", "action": "blood on the asphalt",
         "censor_region": {"x": 10, "y": 10, "width": 50, "height": 50}},
        {"clip_start": "00:03:00.000", "clip_end": "00:03:05.000",
         "censor": "none"}]}
    (d / "shots.json").write_text(json.dumps(shots), encoding="utf-8")
    b = io.StringIO()
    with redirect_stdout(b):
        CF.main(["--project", PROJ, "--no-frames"])
    out = b.getvalue()
    listed = ("00:01:00.000..00:01:05.000  blur_light  NO REGION" in out
              and "00:02:00.000..00:02:05.000  blur  region" in out
              and "00:03:00.000" not in out)
    before = (d / "shots.json").read_bytes()
    with redirect_stdout(io.StringIO()):
        rc_unknown = CF.main(["--project", PROJ, "--clear", "00:09:00.000",
                              "--note", "x"])
    same = (d / "shots.json").read_bytes() == before
    try:
        with redirect_stderr(io.StringIO()):
            CF.main(["--project", PROJ, "--clear", "00:01:00.000"])
        no_note = False
    except SystemExit:
        no_note = (d / "shots.json").read_bytes() == before
    with redirect_stdout(io.StringIO()):
        rc = CF.main(["--project", PROJ, "--clear", "00:01:00.000",
                      "--note", "party dresses, no gore"])
    s = json.loads((d / "shots.json").read_text(encoding="utf-8"))["shots"]
    cleared = (rc == 0 and s[0]["censor"] == "none"
               and "party dresses" in s[0].get("censor_cleared", "")
               and s[1]["censor"] == "blur" and not censor.criteria_problems(d))
    shutil.rmtree(d, ignore_errors=True)
    cases = [("LIST", listed, "unregioned flag marked, regioned one shows its "
              "box, unflagged shot not listed"),
             ("CLEAR", cleared and rc_unknown == 1 and same and no_note,
              "cleared with the note, policy clean; no note / unknown time "
              "change nothing")]
    bad = 0
    for n, ok, m in cases:
        print(f"{'PASS' if ok else 'FAIL'}  {n:<6} {m}")
        bad += not ok
    print("-" * 60)
    print(f"test_censor_flags: {bad} FAILURE(S)" if bad
          else "test_censor_flags: all pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
