# -*- coding: utf-8 -*-
"""test_resolve_routing.py - the audit's blocking items reach the reviser.

Lost in the Stars: after the gates were clean, `recap.py draft` still ended
"Audit failed hard: 10 [VOICE-VISUAL] ...; 2 REVEAL-TIMING ...;
[RUNTIME-BAND] 22.1 min over the 19 min ceiling", and resolve stopped on
"draft-wide gate error(s) name no line" - nothing was ever sent. And the
draft was long because story slots held 7,691 words against a 3,550 plan.

    python tools/test_resolve_routing.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import write_api as W  # noqa: E402
import write_slots as WS  # noqa: E402

AUDIT = """Binding audit ([VOICE-VISUAL]):
  x line 76 [SPEAKER_ABSENT] claim=speech(subject chen mai)
      ""Have you noticed the manager of the hotel hall?" She says the manager"
      footage: clip 00:40:10.917  depicts=['action', 'montage', 'reveal']  chars=['he fei']
      try: clip:00:00:48, clip:00:01:07
[REVEAL-TIMING] 2 possible early reveal(s) - a protected term appears BEFORE its landing beat:
    R3: "Chen Mai is Shen Man" in line 207 (~96.8 min) lands before 01:38:44
      key: R3 ? 6c489eb3
    R2: "the hospital was a set" in line 209 (~97.2 min) lands before 01:37:31
"""
PROJ = "_selftest_resolve_routing"


def test_audit_rows() -> tuple[bool, str]:
    got = W.audit_line_findings(AUDIT)
    ids = [sorted(W.finding_ids(f)) for f in got]
    bad = []
    if ids != [[76], [207], [209]]:
        bad.append(f"ids {ids}")
    if got and "['he fei']" not in got[0]:
        bad.append("the footage's people are not in the finding")
    if len(got) > 1 and "Chen Mai is Shen Man" not in got[1]:
        bad.append("the giveaway term is not in the finding")
    return (not bad), ("VOICE-VISUAL line 76 and REVEAL-TIMING 207 / 209 "
                       "routed to their lines" if not bad else "; ".join(bad))


def test_runtime() -> tuple[bool, str]:
    pd = Path(config.project_dir(PROJ))
    shutil.rmtree(pd, ignore_errors=True)
    (pd / "draft.json.d").mkdir(parents=True)
    try:
        (pd / "transcript.json").write_text(json.dumps({"duration": 7200}))
        (pd / "plan.json").write_text(json.dumps({"acts": [
            {"act": 1, "word_budget": 30}, {"act": 2, "word_budget": 400}]}))
        w = lambda n: " ".join(["word"] * n)          # noqa: E731
        acts = {1: [w(25), w(25)], 2: [w(20), w(20)]}
        draft, i = [], 1
        for k, texts in acts.items():
            own = []
            for j, t in enumerate(texts):
                ln = {"id": k * 1000 + j + 1, "note": f"B{i:02d}",
                      "narration": t, "clip_start": f"00:0{i}:00.000",
                      "clip_end": f"00:0{i}:20.000"}
                own.append(ln)
                draft.append(dict(ln, id=i))
                i += 1
            (pd / "draft.json.d" / f"act{k}.json").write_text(
                json.dumps({"act": k, "lines": own}))
        (pd / "draft.json").write_text(json.dumps({"lines": draft}))
        errs = ["Audit failed hard: [RUNTIME-BAND] est. 21.1 min of narration "
                "-> 22.1 min finished (x1.046, measured): 22.1 min over the "
                "19 min ceiling. (exit 1)"]
        got = W.runtime_findings(PROJ, errs)
        bad = []
        if len(got) != 1 or got[0]["ids"] != ["1", "2"]:
            bad.append(f"expected one finding on act 1's lines 1, 2: "
                       f"{[(f['ids'], f['text'][:60]) for f in got]}")
        elif "cut about 20 words" not in got[0]["text"]:
            bad.append(f"cut size: {got[0]['text'][:160]}")
        if W.runtime_findings(PROJ, ["[HOOK] something else"]):
            bad.append("a finding without a runtime error")
        return (not bad), ("over-budget act 1 gets a cut-20-words finding on "
                           "its lines; act 2 under budget is left alone"
                           if not bad else "; ".join(bad))
    finally:
        shutil.rmtree(pd, ignore_errors=True)


def test_act_scale() -> tuple[bool, str]:
    """Story slots share the act's plan budget (built right, not graded)."""
    from pipeline.preflight import budget_words
    narr = [{"act": 1, "role": "action", "a": 0.0 + 30 * i, "z": 25.0 + 30 * i}
            for i in range(10)]
    narr.append({"act": 1, "role": "intro", "a": 400.0, "z": 410.0})
    plan = {"acts": [{"act": 1, "word_budget": 200}]}
    sc = WS._act_scale(narr, plan)
    full = sum(min(WS.BANDS["free"][1], budget_words(25.0)) for _ in range(10))
    want = (200 - WS.INTRO_WORDS[1]) / full
    bad = []
    if abs(sc.get(1, 0) - want) > 1e-6:
        bad.append(f"scale {sc} != {want:.3f}")
    if WS._act_scale(narr, {"acts": [{"act": 1, "word_budget": 99999}]}) \
            != {1: 1.0}:
        bad.append("a budget above the footage raised capacity")
    if WS._act_scale(narr, {"acts": []}):
        bad.append("no budget, yet a scale")
    return (not bad), (f"10 slots of {full} words share 200 - 40 intro "
                       f"(x{want:.2f}); never above 1; none without a budget"
                       if not bad else "; ".join(bad))


TESTS = {"AUDIT-ROWS": test_audit_rows, "RUNTIME-PER-ACT": test_runtime,
         "ACT-BUDGET-SCALE": test_act_scale}

if __name__ == "__main__":
    bad = 0
    for name, fn in TESTS.items():
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        print(f'{"PASS" if ok else "FAIL"}  {name:<18} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_resolve_routing: all pass" if not bad else
          f"test_resolve_routing: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
