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


def _beats_project(pd: Path) -> None:
    (pd / "names.json").write_text(json.dumps({"names": [
        {"character": "He Fei", "actor": "Zhu Yilong"},
        {"character": "Chen Mai", "actor": "Ni Ni"},
        {"character": "Shen Man", "actor": "Ni Ni"},
        {"character": "Li Muzi", "actor": "Kay Huang"}]}))
    (pd / "beats_proposal.md").write_text(
        "B01 | 00:00:48 | He Fei reports Muzi missing | He Fei | dialogue\n"
        "B20 | 00:19:15 | He Fei meets the lawyer | He Fei, Chen Mai | "
        "dialogue\n"
        "B102 | 01:30:48 | He Fei names the lighthouse | He Fei, Chen Mai | "
        "dialogue\n"
        "B115 | 01:38:44 | the troupe faces him | Shen Man | reveal\n"
        "B116 | 01:38:52 | flashback | Shen Man, Li Muzi | emotion\n",
        encoding="utf-8")


def test_hidden_identity() -> tuple[bool, str]:
    """Two names, one actor (Chen Mai / Shen Man): the later one is a secret
    until the beat map first shows it. A point naming it earlier moves after
    that beat; a point naming the first identity, or Muzi - talked about
    long before she is seen - stays."""
    pd = Path(config.project_dir(PROJ))
    shutil.rmtree(pd, ignore_errors=True)
    pd.mkdir(parents=True)
    try:
        _beats_project(pd)
        hid = WS._hidden_names(PROJ)
        bad = []
        if hid != [(5924.0, ["Shen Man"])]:
            bad.append(f"hidden {hid}")
        mk = lambda sid, beat, ts, mw: {   # noqa: E731
            "slot": sid, "beat": beat, "role": "action", "clip_start": ts,
            "clip_end": ts, "max_words": mw}
        plan = {"slots": [mk("S1", "B01", "00:00:48.000", 20),
                          mk("S2", "B102", "01:30:48.000", 15),
                          mk("S3", "B115", "01:38:44.000", 4),
                          mk("S4", "B116", "01:38:52.800", 16)],
                "spine": [{"step": "He Fei reports Muzi missing",
                           "beats": ["B01"]},
                          {"step": "He Fei names the lighthouse",
                           "beats": ["B102"]}],
                "holders": [{"what": "Muzi's location", "changes": [
                    {"beat": "B102", "to": "Shen Man and the troupe"}]}]}
        (pd / "plan.json").write_text(json.dumps(plan))
        got = WS.remark_points(PROJ, pd)
        sl = {x["slot"]: x for x in json.loads(
            (pd / "plan.json").read_text())["slots"]}
        if "Muzi" not in str(sl["S1"].get("must_say")):
            bad.append("the B01 point naming Muzi moved")
        if "Shen Man" in str(sl["S2"].get("must_say")) or \
                "lighthouse" not in str(sl["S2"].get("must_say")):
            bad.append(f"S2: {sl['S2'].get('must_say')}")
        if "Shen Man" not in str(sl["S4"].get("must_say")):
            bad.append(f"S4 (first roomy slot after B115): "
                       f"{sl['S4'].get('must_say')}")
        if WS.remark_points(PROJ, pd):
            bad.append("a second re-place changed something again")
        if sorted(got) != ["S1", "S2", "S4"]:
            bad.append(f"changed {got}")
        return (not bad), ("Shen Man hidden until B115; the holder point "
                           "naming her moves to B116; Muzi / lighthouse "
                           "points stay; idempotent"
                           if not bad else "; ".join(bad))
    finally:
        shutil.rmtree(pd, ignore_errors=True)


def test_story_point_finding() -> tuple[bool, str]:
    """A slot's point its line does not say becomes a [STORY-POINT] finding
    on that line; a line that names who does not."""
    pd = Path(config.project_dir(PROJ))
    shutil.rmtree(pd, ignore_errors=True)
    (pd / "draft.json.d").mkdir(parents=True)
    try:
        slots = [{"slot": "S1", "act": 1, "beat": "B116", "role": "action",
                  "clip_start": "01:38:52.800", "clip_end": "01:39:01.400",
                  "min_words": 3, "max_words": 30, "band": "free",
                  "anchor": False, "peak": False,
                  "must_say": "Chen Mai is Shen Man",
                  "must_keys": [["Shen Man"]]},
                 {"slot": "S2", "act": 1, "beat": "B117", "role": "action",
                  "clip_start": "01:39:10.000", "clip_end": "01:39:20.000",
                  "min_words": 3, "max_words": 30, "band": "free",
                  "anchor": False, "peak": False,
                  "must_say": "Muzi saves her", "must_keys": [["Muzi"]]}]
        (pd / "plan.json").write_text(json.dumps(
            {"slots": slots, "slots_version": WS.SLOTS_VERSION}))
        act = [{"id": 1001, "slot": "S1", "note": "B116",
                "narration": "In a flashback, a schoolgirl is bullied.",
                "clip_start": "01:38:52.800", "clip_end": "01:39:01.400"},
               {"id": 1002, "slot": "S2", "note": "B117",
                "narration": "Muzi tends her wounds on the rooftop.",
                "clip_start": "01:39:10.000", "clip_end": "01:39:20.000"}]
        (pd / "draft.json.d" / "act1.json").write_text(
            json.dumps({"act": 1, "lines": act}))
        (pd / "draft.json").write_text(json.dumps({"lines": [
            dict(act[0], id=221), dict(act[1], id=222)]}))
        got = W.story_point_findings(PROJ)
        ok = [f["ids"] for f in got] == [["221"]] and \
            "[STORY-POINT]" in got[0]["text"]
        return ok, ("line 221 (point unsaid) flagged; 222 (names Muzi) not"
                    if ok else f"got {[(f['ids'], f['text'][:80]) for f in got]}")
    finally:
        shutil.rmtree(pd, ignore_errors=True)


def test_identity_timing() -> tuple[bool, str]:
    """Narration that names the secret identity before the unmasking is an
    early reveal (Lost in the Stars line 189, 01:30:57: "Now Shen Man and
    her troupe know where Muzi vanished"); the first identity, and the name
    after the unmasking, are not. The audit row reaches resolve."""
    from types import SimpleNamespace as NS
    from pipeline import draft as D
    pd = Path(config.project_dir(PROJ))
    shutil.rmtree(pd, ignore_errors=True)
    pd.mkdir(parents=True)
    try:
        _beats_project(pd)
        L = lambda i, ts, t: NS(id=i, narration=t, clip_start=ts,  # noqa
                                note="B102")
        d = NS(lines=[L(189, "01:30:57.600",
                        "Now Shen Man and her troupe know where Muzi is."),
                      L(190, "01:31:10.000", "Chen Mai leans in."),
                      L(222, "01:39:01.458", "Chen Mai is Shen Man.")])
        hits = D.reveal_timing_check(PROJ, d)
        got = [(h["reveal_id"], h["line_id"], h["term"]) for h in hits]
        bad = []
        if got != [("IDENTITY", 189, "Shen Man")]:
            bad.append(f"hits {got}")
        row = ('    IDENTITY: "Shen Man" in line 189 (~91.0 min) lands '
               'before 01:38:44')
        f = W.audit_line_findings(row)
        if len(f) != 1 or W.finding_ids(f[0]) != {189} or \
                "secret identity" not in f[0]:
            bad.append(f"finding {f}")
        return (not bad), ("line 189 naming Shen Man before B115 is an early "
                           "reveal, routed to its line; Chen Mai / after the "
                           "unmasking are clean" if not bad else
                           "; ".join(bad))
    finally:
        shutil.rmtree(pd, ignore_errors=True)


def test_covers_conserved() -> tuple[bool, str]:
    """A film-speaks unit that replaces lines carries their slots: the draft
    still conserves every planned line; without the covers it does not."""
    from pipeline import draft as D
    pd = Path(config.project_dir(PROJ))
    shutil.rmtree(pd, ignore_errors=True)
    pd.mkdir(parents=True)
    try:
        (pd / "plan.json").write_text(json.dumps({"slots": [
            {"slot": "S1", "role": "action", "beat": "B01"},
            {"slot": "S2", "role": "action", "beat": "B02"},
            {"slot": "S3", "role": "action", "beat": "B03"}]}))
        d = {"lines": [{"id": 1, "slot": "S1", "narration": "a"},
                       {"id": 9, "narration": "", "film_speaks_seconds": 5.0,
                        "film_speaks_covers": ["S2"]},
                       {"id": 3, "slot": "S3", "narration": "c"}]}
        ok1 = D.conservation_problems(PROJ, d) == []
        d["lines"][1].pop("film_speaks_covers")
        ok2 = bool(D.conservation_problems(PROJ, d))
        return ok1 and ok2, ("covered slot conserved; uncovered cut reported"
                             if ok1 and ok2 else f"covered {ok1}, bare {ok2}")
    finally:
        shutil.rmtree(pd, ignore_errors=True)


TESTS = {"AUDIT-ROWS": test_audit_rows, "RUNTIME-PER-ACT": test_runtime,
         "ACT-BUDGET-SCALE": test_act_scale,
         "HIDDEN-IDENTITY": test_hidden_identity,
         "STORY-POINT-FINDING": test_story_point_finding,
         "IDENTITY-TIMING": test_identity_timing,
         "COVERS-CONSERVED": test_covers_conserved}

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
