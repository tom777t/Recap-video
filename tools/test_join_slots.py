# -*- coding: utf-8 -*-
"""test_join_slots.py - one sentence across 2-3 adjacent slots (writer side).

Owner, 17 Nov: the slots cut every line to one short shot, so our sentences
averaged 12 words against 16 for a binge-watched channel, and a chain of
actions came out as two-word facts. A writer may now reply ONE line over 2-3
slots in a row, with a '|' where each next slot's footage begins.

  JOIN-BUILDS        a valid join becomes one line: narration without '|',
                     the window from the first slot's start to the last's
                     end, `parts` with each piece, its slot, window and caps
  JOIN-REFUSED       not adjacent / across a hold / wrong '|' count / an
                     outro / more than 3 / starting at another slot -> a
                     plain line on its own slot ('|' removed) + the reason
  MERGE-CONSERVES    the act file has no line for a carried slot, and
                     [DRAFT-CONSERVATION] and the plan-count check count it
                     as said (both beats it runs over)
  CHECK-PER-PIECE    the word caps hold per piece: a piece over its slot's
                     cap deviates, naming that slot; the joined sentence is
                     never measured against the first slot's cap alone
  CHECK-SLOTS        check_slots: a carried slot is answered; saying it again
                     on its own is 'said twice'; a refused join is reported
  REVISION-KEEPS     merge_revision: a rewrite with the same join is taken
                     (parts updated); one that changes the join is not; the
                     carried slot is never reported missing
  STALE-PARTS        a later rewrite without '|' leaves the parts stale:
                     parts_intact False, the caps are then checked on the sum
  SCHEMAS            the saved-line schema accepts parts and refuses a
                     one-piece `parts`; the reply schema offers `join`

Run:  python tools/test_join_slots.py      (exit 0 = all pass)
"""
from __future__ import annotations

import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import test_story_mode as TSM  # noqa: E402
import write_slots as WS  # noqa: E402

config.STYLE_QUOTA_FLOORS = False
K = 2


def _act():
    plan, ab, slots = TSM._layout()
    act = WS.slots_for_act(slots, K)
    return plan, slots, act


def _pair(act, n=2):
    """n adjacent narrated slots with continuous footage, no skip inside."""
    for i in range(len(act) - n + 1):
        ss = act[i:i + n]
        if all(x["role"] not in WS.NO_JOIN for x in ss) and not any(
                x.get("after_skip") or x.get("transition") for x in ss[1:]) \
                and all(abs(WS._pt(b["clip_start"]) - WS._pt(a["clip_end"]))
                        <= WS.JOIN_GAP for a, b in zip(ss, ss[1:])) \
                and not any(x.get("quote") or x.get("must_keys") for x in ss):
            return ss
    raise AssertionError("no joinable run in the fixture")


def _piece(s, w=None):
    n = w or max(3, min(int(s["max_words"]), 7))
    return " ".join((["Sean"] + ["races"] * 40)[:n])


def _fill_act(act, joined=None, extra=None):
    """A reply for the whole act; `joined` = the slots one line runs over."""
    out = []
    jset = [x["slot"] for x in joined] if joined else []
    for i, s in enumerate(act):
        if s["role"] in ("hold", "film_speaks"):
            continue
        if jset and s["slot"] == jset[0]:
            out.append({"slot": s["slot"], "join": jset, "payload": "stake",
                        "delivery": "normal", "narration": " | ".join(
                            _piece(x) + "." for x in joined)})
            continue
        if s["slot"] in jset[1:]:
            continue
        out.append(TSM._fill(s, i))
    return out + (extra or [])


def t_join_builds():
    _p, _sl, act = _act()
    ss = _pair(act)
    ln = {"slot": ss[0]["slot"], "join": [x["slot"] for x in ss],
          "narration": "Sean takes the car. | He floors it out of the lot.",
          "payload": "stake", "delivery": "normal"}
    out, probs = WS.apply_join(ln, act)
    ok = (not probs and "|" not in out["narration"]
          and out["clip_start"] == ss[0]["clip_start"]
          and out["clip_end"] == ss[1]["clip_end"]
          and [p["slot"] for p in out["parts"]] == [x["slot"] for x in ss]
          and out["parts"][1]["text"] == "He floors it out of the lot."
          and out["parts"][0]["max_words"] == ss[0]["max_words"])
    return ok, (f"{ss[0]['slot']}+{ss[1]['slot']} -> one line "
                f"{out['clip_start']}-{out['clip_end']}, 2 parts" if ok
                else f"{probs} {out}")


def t_join_refused():
    _p, _sl, act = _act()
    ss = _pair(act)
    i0 = act.index(ss[0])
    cases = {
        "not adjacent": [ss[0]["slot"]] + [x["slot"] for x in act[i0 + 2:i0 + 3]],
        "too many": [x["slot"] for x in act[i0:i0 + 4]],
        "not its own slot": [x["slot"] for x in ss[::-1]],
    }
    hold = next((i for i, x in enumerate(act) if x["role"] == "hold"
                 and i > 0 and act[i - 1]["role"] not in WS.NO_JOIN
                 and i + 1 < len(act)), None)
    if hold is not None:
        cases["across a hold"] = [act[hold - 1]["slot"], act[hold]["slot"]]
    outro = next((x for x in act if x["role"] == "outro"), None)
    bad = []
    for name, j in cases.items():
        ln = {"slot": j[0] if name != "not its own slot" else ss[0]["slot"],
              "join": j, "narration": " | ".join(["Sean drives fast."] * len(j)),
              "payload": "stake", "delivery": "normal"}
        out, probs = WS.apply_join(ln, act)
        if not probs or "|" in out["narration"] or out.get("parts"):
            bad.append(f"{name}: accepted")
    ln = {"slot": ss[0]["slot"], "join": [x["slot"] for x in ss],
          "narration": "Sean drives fast and the car spins.",
          "payload": "stake", "delivery": "normal"}
    if not WS.apply_join(ln, act)[1]:
        bad.append("no '|': accepted")
    return not bad, (f"refused: {', '.join(list(cases) + ['no |'])}"
                     + ("" if outro is None else "") if not bad
                     else "; ".join(bad))


def t_merge_conserves():
    import write_plan as WP
    from pipeline import draft as D
    plan, slots, act = _act()
    ss = _pair(act)
    lines = WS.merge(_fill_act(act, ss), slots, K)
    got = [l.get("slot") for l in lines]
    j = next(l for l in lines if l.get("parts"))
    bad = []
    if ss[1]["slot"] in got:
        bad.append("the carried slot has its own line")
    if j["clip_end"] != ss[1]["clip_end"]:
        bad.append("the joined line's window does not run to the last slot")
    # conservation: the draft says every planned slot (act 2 only here)
    tmp = config.project_dir(TSM.PROJ) / "plan.json"
    old = tmp.read_text(encoding="utf-8") if tmp.exists() else None
    try:
        tmp.write_text(json.dumps({"slots": act}), encoding="utf-8")
        cp = D.conservation_problems(TSM.PROJ, {"lines": lines})
    finally:
        if old is None:
            tmp.unlink()
        else:
            tmp.write_text(old, encoding="utf-8")
    if cp:
        bad.append(f"conservation: {cp[0][:90]}")
    # plan counts: both beats of the join counted
    cnt = WP.check_plan_counts(lines, plan, sorted({x["beat"] for x in act}))
    if any(b in " ".join(cnt) for b in {ss[0]["beat"], ss[1]["beat"]}):
        bad.append(f"plan counts: {cnt[:2]}")
    return not bad, ("carried slot has no line of its own; conserved; both "
                     "beats counted" if not bad else "; ".join(bad))


def t_check_per_piece():
    _p, _sl, act = _act()
    ss = _pair(act)
    long2 = " ".join(["races"] * (int(ss[1]["max_words"]) + 6))
    ln = {"slot": ss[0]["slot"], "join": [x["slot"] for x in ss],
          "narration": f"{_piece(ss[0])}. | Sean {long2}.",
          "payload": "stake", "delivery": "normal"}
    m, _ = WS.apply_join(ln, act)
    d_over = [d for d in WS.line_deviations(m, ss[0]) if "words" in d]
    full0 = _piece(ss[0], int(ss[0]["max_words"]))
    ok_ln = dict(ln, narration=f"{full0}. | {_piece(ss[1])}.")
    m2, _ = WS.apply_join(ok_ln, act)
    whole = WS._wc(m2["narration"])
    d_ok = [d for d in WS.line_deviations(m2, ss[0]) if "words" in d]
    ok = (len(d_over) == 1 and d_over[0].startswith(ss[1]["slot"])
          and not d_ok and whole > int(ss[0]["max_words"]))
    return ok, (f"piece 2 over its cap -> '{d_over[0][:40]}...'; a "
                f"{whole}-word joined line within its pieces passes" if ok
                else f"over {d_over}; ok {d_ok}")


def t_check_slots():
    _p, _sl, act = _act()
    ss = _pair(act)
    rep = _fill_act(act, ss)
    d0 = WS.check_slots(rep, act)
    twice = _fill_act(act, ss, extra=[TSM._fill(ss[1], 1)])
    d1 = WS.check_slots(twice, act)
    badj = copy.deepcopy(rep)
    for l in badj:
        if l.get("join"):
            l["narration"] = l["narration"].replace("|", "")
    d2 = WS.check_slots(badj, act)
    ok = (not any(ss[1]["slot"] in d and "no line" in d for d in d0)
          and any("said twice" in d for d in d1)
          and any("not allowed" in d for d in d2))
    return ok, ("carried slot answered; said again -> 'said twice'; a join "
                "without '|' reported" if ok
                else f"d0 {d0[:2]}; d1 {d1[:2]}; d2 {d2[:2]}")


def t_revision_keeps():
    _p, slots, act = _act()
    ss = _pair(act)
    prev = WS.merge(_fill_act(act, ss), slots, K)
    j = [x["slot"] for x in ss]
    same = {"slot": ss[0]["slot"], "join": j,
            "narration": "Sean grabs the keys. | He tears out of the lot.",
            "payload": "stake", "delivery": "normal"}
    out1, n1 = WS.merge_revision(prev, [same], act, K)
    jl = next(l for l in out1 if l.get("slot") == ss[0]["slot"])
    changed = {"slot": ss[0]["slot"], "narration": "Sean grabs the keys.",
               "payload": "stake", "delivery": "normal"}
    out2, n2 = WS.merge_revision(prev, [changed], act, K)
    kept = next(l for l in out2 if l.get("slot") == ss[0]["slot"])
    miss = [n for n in n1 + n2 if "still missing" in n and ss[1]["slot"] in n]
    ok = (jl["parts"][1]["text"] == "He tears out of the lot."
          and "|" not in jl["narration"]
          and kept.get("parts") and any("change the join" in n for n in n2)
          and not miss and ss[1]["slot"] not in [l.get("slot") for l in out1])
    return ok, ("same join: taken, parts updated; changed join: not taken; "
                "carried slot never 'missing'" if ok
                else f"n1 {n1}; n2 {n2}; miss {miss}")


def t_stale_parts():
    _p, _sl, act = _act()
    ss = _pair(act)
    ln = {"slot": ss[0]["slot"], "join": [x["slot"] for x in ss],
          "narration": f"{_piece(ss[0])}. | {_piece(ss[1])}.",
          "payload": "stake", "delivery": "normal"}
    m, _ = WS.apply_join(ln, act)
    m2 = dict(m, narration="Sean takes the keys and floors it out of town.")
    cap = sum(int(x["max_words"]) for x in ss)
    m3 = dict(m, narration=" ".join(["word"] * (cap + 8)))
    d3 = [d for d in WS.line_deviations(m3, ss[0]) if "words" in d]
    ok = (WS.parts_intact(m) and not WS.parts_intact(m2)
          and not [d for d in WS.line_deviations(m2, ss[0]) if "words" in d]
          and d3 and f"hold {cap}" in d3[0])
    return ok, (f"rewritten without '|': stale; checked against the {cap}-"
                f"word sum" if ok else f"{d3}")


def t_schemas():
    from pipeline import schemas as S
    import write_api as W
    _p, _sl, act = _act()
    ss = _pair(act)
    m, _ = WS.apply_join({"slot": ss[0]["slot"], "join": [x["slot"] for x in ss],
                          "narration": "Sean runs. | He hides.",
                          "payload": "stake", "delivery": "normal"}, act)
    good = dict(m, id=2001, note=ss[0]["beat"])
    one = dict(good, id=2002, parts=good["parts"][:1])
    p_ok = S.line_problems([good])
    p_bad = S.line_problems([one])
    sch = W.act_schema(W.SLOT_LINE_FIELDS, W.SLOT_LINE_REQUIRED)
    has_join = "join" in sch["properties"]["lines"]["items"]["properties"]
    ok = not p_ok and p_bad and has_join
    return ok, ("parts accepted, one-piece parts refused; reply schema has "
                "join" if ok else f"ok {p_ok}; bad {p_bad}; join {has_join}")


TESTS = [("JOIN-BUILDS", t_join_builds), ("JOIN-REFUSED", t_join_refused),
         ("MERGE-CONSERVES", t_merge_conserves),
         ("CHECK-PER-PIECE", t_check_per_piece),
         ("CHECK-SLOTS", t_check_slots), ("REVISION-KEEPS", t_revision_keeps),
         ("STALE-PARTS", t_stale_parts), ("SCHEMAS", t_schemas)]

if __name__ == "__main__":
    fails = 0
    for name, fn in TESTS:
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:16s} {msg}")
    print("-" * 60)
    print("test_join_slots: all pass" if not fails
          else f"test_join_slots: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
