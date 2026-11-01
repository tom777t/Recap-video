# -*- coding: utf-8 -*-
"""test_window_span.py - wider windows, never at the cost of a rule.

  RULES-HOLD     after tools/widen_windows.py on the real draft: clip_start never
                 moves, no window shrinks, none reaches the next bound line,
                 none crosses a reveal landing it started before, none enters
                 a censor-flagged shot
  RATIO-REACHED  the median window/narration ratio moves from the rewrite's
                 ~1.37x to at least the warning floor
  GATE-FIRES     [WINDOW-SPAN] warns on the narrow (rewrite) draft and is quiet
                 on the draft the viewer approved (pre-rewrite)

Run:  python tools/test_window_span.py      (exit 0 = all pass)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline.draft import parse_ts  # noqa: E402

REAL = "tokyodrift2006"
SCRATCH = "_selftest_window_span"
TITLE = "Exiled Teen Bets His Last Chance on One Deadly Downhill Race Against a Yakuza Heir"


def _scratch(draft_file="draft.json") -> Path:
    src, dst = Path(config.project_dir(REAL)), Path(config.project_dir(SCRATCH))
    shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True)
    for p in src.iterdir():
        if p.is_file() and p.suffix in (".json", ".md", ".txt"):
            shutil.copy2(p, dst / p.name)
        elif p.is_dir() and p.name.endswith(".d"):
            shutil.copytree(p, dst / p.name)
    d = json.loads((src / draft_file).read_text(encoding="utf-8-sig"))
    d["title"] = TITLE
    (dst / "draft.json").write_text(json.dumps(d, indent=2), encoding="utf-8")
    return dst


def _ratio_median(draft: dict) -> float:
    wpm = float(getattr(config, "TARGET_WPM", 210))
    rs = sorted((parse_ts(l["clip_end"]) - parse_ts(l["clip_start"]))
                / (len(l["narration"].split()) / wpm * 60)
                for l in draft["lines"]
                if l.get("clip_start") and l.get("clip_end")
                and str(l.get("narration") or "").strip())
    return rs[len(rs) // 2]


def test_rules_hold_and_ratio():
    import widen_windows as ww
    pdir = _scratch()
    before = json.loads((pdir / "draft.json").read_text(encoding="utf-8"))
    after, changes, _basis = ww.plan(SCRATCH)
    b_by = {l["id"]: l for l in before["lines"]}
    lands = [parse_ts(str(r.get("land") or r.get("land_ref")))
             for r in json.loads((pdir / "reveals.json").read_text(
                 encoding="utf-8-sig"))["reveals"]
             if (r.get("land") or r.get("land_ref"))]
    from pipeline import censor
    flagged = [(float(f["a"]), float(f["b"])) for f in censor.flagged_shots(pdir)]
    bound = sorted([l for l in after["lines"] if l.get("clip_start")
                    and l.get("clip_end")], key=lambda l: parse_ts(l["clip_start"]))
    for i, l in enumerate(bound):
        o = b_by[l["id"]]
        a, b = parse_ts(l["clip_start"]), parse_ts(l["clip_end"])
        if l["clip_start"] != o["clip_start"]:
            return False, f"line {l['id']}: clip_start moved"
        if b < parse_ts(o["clip_end"]) - 1e-3:
            return False, f"line {l['id']}: window shrank"
        if i + 1 < len(bound) and b > parse_ts(bound[i + 1]["clip_start"]) + 1e-3:
            return False, f"line {l['id']}: runs into line {bound[i+1]['id']}"
        if b > parse_ts(o["clip_end"]) + 1e-3:
            for L in lands:
                if a < L < b:
                    return False, f"line {l['id']}: widened across a reveal at {L:.0f}s"
            for fa, _fb in flagged:
                if parse_ts(o["clip_end"]) <= fa < b:
                    return False, f"line {l['id']}: widened into a flagged shot"
    m0, m1 = _ratio_median(before), _ratio_median(after)
    floor = float(config.WINDOW_SPAN_MIN_MEDIAN)
    if m1 < floor:
        return False, f"median ratio {m0:.2f}x -> {m1:.2f}x, still under {floor}"
    return True, (f"{len(changes)} window(s) widened, all five rules hold; "
                  f"median {m0:.2f}x -> {m1:.2f}x")


def _draft_out() -> str:
    r = subprocess.run([sys.executable, "recap.py", "draft", "--project", SCRATCH],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return (r.stdout or "") + (r.stderr or "")


def test_gate_fires():
    _scratch("draft.json")
    narrow = _draft_out()
    _scratch("draft_prerewrite.json")
    approved = _draft_out()
    if "[WINDOW-SPAN]" not in narrow or "median window is" not in narrow:
        return False, "no [WINDOW-SPAN] warning on the narrow rewrite draft"
    if "median window is" in approved:
        return False, "[WINDOW-SPAN] warns on the draft the viewer approved"
    return True, "warns on the rewrite (1.37x), quiet on the approved draft (1.71x)"


TESTS = {
    "RULES-HOLD+RATIO-REACHED": test_rules_hold_and_ratio,
    "GATE-FIRES": test_gate_fires,
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
                ok, msg = False, f"raised {type(e).__name__}: {e}"
            print(f"{'PASS' if ok else 'FAIL'}  {name:<26} {msg}")
            bad += 0 if ok else 1
    finally:
        shutil.rmtree(config.project_dir(SCRATCH), ignore_errors=True)
    print("-" * 60)
    print(f"test_window_span: {bad} FAILURE(S)" if bad else "test_window_span: all pass")
    sys.exit(1 if bad else 0)
