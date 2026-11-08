# -*- coding: utf-8 -*-
"""test_write_slots.py - the plan as slots: structure by construction.

  SLOT-LAYOUT        one slot per planned line, per beat; anchors open on
                     action and end on ONE reaction; quote slots carry a real
                     transcript line; a loop opens at least every
                     BAR_LOOP_GAP lines; long AND short bands present
  WINDOWS-BY-CODE    every window inside its beat, none overlapping, none
                     straddling a reveal's landing, none narrower than
                     write_slots.MIN_WINDOW; holds carry their seconds
  GATES-BY-CONSTRUCTION
                     a draft that just FILLS the slots (placeholder words to
                     each band, payloads per role) is silent on the gates the
                     layout is meant to satisfy: [WINDOW-OVERLAP] (checked
                     here), [PACING-CONTOUR], [LOOP-CADENCE], [RHYTHM] SD /
                     punch, [PERSONA] windows, [PEAK-ORDER]
  BRIEF-FROM-CONSTANTS
                     the writer brief changes when a gate constant changes -
                     it is generated from them, never a copy
  DRAFT-SLOTS        cmd_draft: plan.json grows `slots`; each act request
                     carries its slots + the brief, and a reply schema with
                     `slot` and no timestamps; the act file gets code's ids,
                     beats, windows and holds; an act that misses its slots
                     gets the deviations back ONCE inside the stage
  COUNTS-FOLLOWED    after the acts, each beat's narrated line count equals
                     the plan's (the follow-through check of item 4)

Run:  python tools/test_write_slots.py
"""
from __future__ import annotations

import io
import json
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import tag_batch as TB  # noqa: E402
import write_api as W  # noqa: E402
import write_slots as WS  # noqa: E402
import test_write_plan as TWP  # noqa: E402

PROJ, PDIR = TWP.PROJ, TWP.PDIR
_C = {}


def _layout():
    if not _C:
        TWP._setup()
        plan = TWP._plan("good")
        # a realistic plan: holds after the anchors only
        from pipeline import angle_spec
        an = {b for a in angle_spec.load(PDIR)["anchors"] for b in a["beats"]}
        for b in plan["beats"]:
            b["hold_after"] = b["beat"] in an
        _C["plan"], _C["ab"] = plan, TWP._ab()
        _C["anchors"] = an
        _C["r"] = WS.derive_slots(plan, PROJ, PDIR, _C["ab"])
    return _C["plan"], _C["ab"], _C["r"]["slots"]


def _narrated(slots):
    return [s for s in slots if s["role"] not in ("hold", "film_speaks")]


def test_slot_layout():
    from pipeline import craft_gates as CG
    plan, ab, slots = _layout()
    bad = []
    for b in plan["beats"]:
        n = sum(1 for s in _narrated(slots) if s["beat"] == b["beat"])
        if n != b["lines"]:
            bad.append(f"{b['beat']}: {n} slot(s), plan {b['lines']}")
    from pipeline import angle_spec
    for an in angle_spec.load(PDIR)["anchors"]:
        bid = "/".join(an["beats"])
        grp = [s for s in _narrated(slots) if s["beat"] in an["beats"]]
        if len(grp) >= 2 and (grp[0]["role"] != "action"
                              or grp[-1]["role"] != "reaction"
                              or sum(x["role"] == "reaction" for x in grp)
                              > config.PERSONA_PEAK_REACTION_MAX):
            bad.append(f"anchor {bid}: {[x['role'] for x in grp]}")
    segs = {t for _a, _b, t in WS.speech(PDIR)}
    q = [s for s in slots if s["role"] == "quote"]
    if not q or any(s.get("quote") not in segs for s in q):
        bad.append("quote slots without a real transcript line")
    gap, run = 0, 0
    for s in _narrated(slots):
        run = 0 if s.get("opens_loop") else run + 1
        gap = max(gap, run)
    if gap > CG.BAR_LOOP_GAP:
        bad.append(f"{gap} lines without a loop")
    bands = {s["band"] for s in _narrated(slots)}
    if not {"short", "long"} <= bands:
        bad.append(f"bands {bands}")
    if any(s["role"] not in WS.ROLES for s in slots):
        bad.append("unknown role")
    return (not bad), (f"{len(slots)} slots, counts = plan per beat, anchors "
                       f"action..reaction, {len(q)} quotes, loop gap <= {gap}"
                       if not bad else "; ".join(bad[:5]))


def test_windows_by_code():
    from pipeline.draft import parse_ts, parse_reveal_map
    plan, ab, slots = _layout()
    rng = WS._beat_ranges(PROJ, [])
    lands = [r["land_sec"] for r in parse_reveal_map(PROJ)
             if r.get("land_sec") not in (None, float("inf"))]
    w = sorted((parse_ts(s["clip_start"]), parse_ts(s["clip_end"]), s)
               for s in slots)
    bad = []
    for (a1, b1, s1), (a2, _b2, s2) in zip(w, w[1:]):
        if a2 < b1 - 1e-6:
            bad.append(f"{s1['slot']}/{s2['slot']} overlap")
    for a, b, s in w:
        lo, hi = rng[s["beat"]]
        if a < lo - 1e-6 or a >= hi:
            bad.append(f"{s['slot']} starts outside {s['beat']}")
        if any(a < t < b - 1e-6 for t in lands):
            bad.append(f"{s['slot']} straddles a reveal landing")
        if b - a < WS.MIN_WINDOW - 1e-6:
            bad.append(f"{s['slot']} {b - a:.1f}s")
        if s["role"] == "hold" and not s.get("hold"):
            bad.append(f"{s['slot']} hold without seconds")
    return (not bad), (f"{len(w)} windows: inside their beats, disjoint, no "
                       f"reveal straddled" if not bad else "; ".join(bad[:5]))


_TEXT = {
    "reaction": "Honestly, you could see that one coming from the car park.",
    "quote": "{q} - and that is exactly what he says.",
}


def _fill(s, i):
    """Placeholder narration that fills a slot the way the brief asks."""
    if s["role"] == "quote":
        t = f"\"{s['quote']}\" is what he tells him."
    elif s["role"] == "reaction":
        t = (_TEXT["reaction"] if s["max_words"] >= 11
             else "Honestly, that went well.")
    elif s.get("shape") == "punch" and s["max_words"] >= 28:
        t = ("He takes the second car down the ramp at a speed that costs "
             "him the front bumper and the paint along one whole side. It "
             "goes badly.")
    elif s.get("shape") == "sweep" and s["max_words"] >= 35:
        t = ("He takes the second car down the ramp at a speed that costs "
             "him the front bumper and the paint along one whole side on the "
             "first night he has ever been in that garage at all.")
    else:
        n = s["target"]
        t = " ".join((["The", "deal", "costs", "him", "his", "only", "car",
                       "and", "the", "money", "he", "owes", "the", "uncle",
                       "is", "now", "due", "tonight"] * 3)[:n]) + "."
    pl = ("loop" if s.get("opens_loop") else "judgment"
          if s["role"] == "reaction" else ("stake", "reasoning")[i % 2])
    return {"slot": s["slot"], "narration": t, "payload": pl,
            "delivery": "normal"}


def _filled_draft():
    plan, ab, slots = _layout()
    lines = []
    for k in sorted(ab):
        mine = WS.slots_for_act(slots, k)
        rep = [_fill(s, i) for i, s in enumerate(mine)
               if s["role"] not in ("hold", "film_speaks")]
        lines += WS.merge(rep, slots, k)
    return {"title": plan["title"], "lines": lines,
            "_dir": str(PDIR)}


def test_gates_by_construction():
    from pipeline import craft_gates as CG
    from pipeline import pacing_gates as PG
    d = _filled_draft()
    msgs = []
    for rep in (CG.craft_report(d), PG.pacing_report(d, PDIR)):
        msgs += rep["errors"] + rep["warns"]
    want_silent = ("[PACING-CONTOUR]", "[LOOP-CADENCE]", "[PEAK-ORDER]")
    loud = [m for m in msgs if m.startswith(want_silent)]
    loud += [m for m in msgs if m.startswith("[RHYTHM]") and (
        "SD is" in m or "punch sentence" in m)]
    loud += [m for m in msgs if m.startswith("[PERSONA]") and "window(s) of"
             in m]
    errs = W.schema_problems(d["lines"])
    sd = next((m for m in msgs if "SD is" in m), None)
    return (not loud and not errs), (
        f"filled slots: {len(d['lines'])} lines, contour / loop / peak / "
        f"rhythm-SD+punch / persona-window silent, schema clean"
        if not loud and not errs else f"{(loud + errs)[:3]} {sd or ''}")


def test_brief_from_constants():
    from pipeline import craft_gates as CG
    plan, ab, slots = _layout()
    a = WS.writer_brief(PDIR, plan, 2)
    old = (CG.BAR_REST_SHARE, config.PERSONA_JUDGMENT_SHARE_MAX)
    CG.BAR_REST_SHARE, config.PERSONA_JUDGMENT_SHARE_MAX = 0.11, 0.77
    try:
        b = WS.writer_brief(PDIR, plan, 2)
    finally:
        CG.BAR_REST_SHARE, config.PERSONA_JUDGMENT_SHARE_MAX = old
    budget = next(x["word_budget"] for x in plan["acts"] if x["act"] == 2)
    ok = ("11%" in b and "77%" in b and "11%" not in a
          and f"{budget} words" in a and "PERSONA" in a)
    return ok, "brief follows the constants the gates read; budget stated"


def _run(client, *argv):
    TB.CLIENT_FACTORY = lambda: client
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = W.main(list(argv))
    return rc, buf.getvalue()


def test_draft_slots():
    plan, ab, _sl = _layout()
    shutil.rmtree(PDIR / "draft.json.d", ignore_errors=True)
    (PDIR / "draft.json").unlink(missing_ok=True)
    (PDIR / "plan.json").write_text(json.dumps(plan))
    seen = []

    def bat(cid, p):
        k = int(cid[3:])
        seen.append((cid, p))
        slots = json.loads((PDIR / "plan.json").read_text())["slots"]
        mine = [s for s in WS.slots_for_act(slots, k)
                if s["role"] not in ("hold", "film_speaks")]
        rep = [_fill(s, i) for i, s in enumerate(mine)]
        if k == 3 and len(p["messages"]) == 1:
            rep = rep[1:]                      # misses its first slot
            rep[0]["narration"] = "Far too short."
        return TWP.msg({"act": k, "lines": rep})
    c = TWP.Client(None, bat)
    real = W.run_gates
    W.run_gates = lambda project: (0, [])
    try:
        rc, out = _run(c, "draft", "--project", PROJ)
    finally:
        W.run_gates = real
    pj = json.loads((PDIR / "plan.json").read_text())
    slots = pj.get("slots") or []
    bad = []
    if not slots:
        bad.append("plan.json has no slots")
    first = [p for cid, p in seen[:len(ab)]]
    u = first[0]["messages"][0]["content"] if first else ""
    if "# YOUR SLOTS" not in u or "WRITER BRIEF" not in u:
        bad.append("act request lacks slots / brief")
    it = first[0]["output_config"]["format"]["schema"]["properties"][
        "lines"]["items"] if first else {}
    if "slot" not in it.get("required", []) or "clip_start" in it.get(
            "properties", {}):
        bad.append("reply schema still asks for timestamps / no slot")
    retry = [cid for cid, p in seen[len(ab):]]
    if retry != ["act3"]:
        bad.append(f"slot feedback went to {retry}, want act3 once")
    else:
        fb = seen[len(ab)][1]["messages"][-1]["content"]
        if "no line" not in fb or "does not follow its slots" not in fb:
            bad.append("the deviations were not fed back")
    a2 = json.loads((PDIR / "draft.json.d/act2.json").read_text())["lines"]
    s2 = {s["slot"]: s for s in WS.slots_for_act(slots, 2)}
    for ln in a2:
        s = s2.get(ln.get("slot"))
        if not s or (ln["clip_start"], ln["clip_end"], ln["note"]) != (
                s["clip_start"], s["clip_end"], s["beat"]):
            bad.append(f"act2 line {ln.get('id')} not on its slot")
            break
    holds = [ln for ln in a2 if ln.get("narration_silence_seconds")]
    if len(holds) != sum(1 for s in s2.values() if s["role"] == "hold"):
        bad.append("holds not written by code")
    _C["after"] = True
    return (not bad and rc in (0, 2)), (
        f"slots in plan.json ({len(slots)}); requests carry slots + brief, "
        f"schema slot-only; act files on code's windows; act3's deviations "
        f"fed back once (rc {rc})" if not bad else "; ".join(bad[:4]))


def test_counts_followed():
    import write_plan as WP
    plan, ab, _sl = _layout()
    if not _C.get("after"):
        return False, "DRAFT-SLOTS did not run first"
    bad = []
    for k in sorted(ab):
        lines = json.loads((PDIR / f"draft.json.d/act{k}.json").read_text())[
            "lines"]
        bad += WP.check_plan_counts(lines, plan, ab[k])
    # and a beat that comes back short IS reported (act 3 lost a slot until
    # the slot round put it back - drop one now and look)
    lines = json.loads((PDIR / "draft.json.d/act2.json").read_text())["lines"]
    nar = [l for l in lines if str(l.get("narration") or "").strip()]
    short = WP.check_plan_counts([l for l in lines if l is not nar[0]], plan,
                                 ab[2])
    ok = not bad and short
    return ok, (f"every beat's line count = plan; a dropped line reported: "
                f"{short[:1]}" if ok else f"{bad[:3]} / {short[:1]}")


TESTS = {
    "SLOT-LAYOUT":           test_slot_layout,
    "WINDOWS-BY-CODE":       test_windows_by_code,
    "GATES-BY-CONSTRUCTION": test_gates_by_construction,
    "BRIEF-FROM-CONSTANTS":  test_brief_from_constants,
    "DRAFT-SLOTS":           test_draft_slots,
    "COUNTS-FOLLOWED":       test_counts_followed,
}

if __name__ == "__main__":
    bad = 0
    saved = TB.CLIENT_FACTORY
    try:
        for name, fn in TESTS.items():
            try:
                ok, m = fn()
            except Exception as e:
                import traceback
                traceback.print_exc()
                ok, m = False, f"{type(e).__name__}: {e}"
            print(f'{"PASS" if ok else "FAIL"}  {name:<22} {m}')
            bad += (not ok)
    finally:
        TB.CLIENT_FACTORY = saved
        shutil.rmtree(PDIR, ignore_errors=True)
    print("-" * 60)
    print("test_write_slots: all pass" if not bad else
          f"test_write_slots: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
