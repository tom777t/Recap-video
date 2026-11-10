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
                     punch, [PERSONA] windows and share, [PEAK-ORDER],
                     [INTRO-OUTRO], [FILM-INTRO], [TRANSITION],
                     [VOICE-PRESENCE], no hold after the outro
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
    w = sorted(((parse_ts(s["clip_start"]), parse_ts(s["clip_end"]), s)
                for s in slots if s["role"] != "intro"), key=lambda x: x[:2])
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


def _tag(s):
    """Letters unique to the slot, so placeholder lines never repeat a
    3-word phrase ([TIC-REPETITION] reads the words)."""
    n = int(s["slot"][1:])
    return chr(97 + n % 26) + chr(97 + n // 26 % 26)


def _u(words, s):
    tg = _tag(s)

    def one(w):
        core = w.rstrip(".,!?")
        if core.islower() and core.isalpha() and len(core) > 3:
            return core + tg + w[len(core):]
        return w
    return " ".join(one(w) for w in words)


def _fill(s, i):
    """Placeholder narration that fills a slot the way the brief asks."""
    if s["role"] == "intro":
        f = WS._facts(PDIR)
        cast = [c for c in f.get("cast") or [] if c.get("lead")][:2]
        t = (f"This is {config.CHANNEL_NAME}, and today I am walking you "
             f"through {f.get('title')} from {f.get('year')}."
             if s.get("intro_part") == "greeting" else
             f"{f.get('director')} directs it, with "
             + " and ".join(f"{c['actor']} as {c['role']}" for c in cast)
             + ", and the whole thing was shot on real streets at night.")
        return {"slot": s["slot"], "narration": t, "payload": "rest",
                "delivery": "intro"}
    if s["role"] == "outro":
        t = ("In the end the only car that was ever really his is the one he "
             "gave back. Subscribe and tell me what to recap next.")
        return {"slot": s["slot"], "narration": t, "payload": "judgment",
                "delivery": "outro"}
    if s["role"] == "quote":
        t = f"\"{s['quote']}\" " + _u("he warns quietly.".split(), s)
    elif s["role"] == "reaction" and s.get("voice") == "eval":
        t = ("That's the " + _u("whole price paid tonight, settled once "
                                "and for good.".split(), s)
             if s["max_words"] >= 11 else "That's the " + _u(["price"], s) + ".")
    elif s["role"] == "reaction":
        t = ("You " + _u("could spot that coming from across the "
                         "parking lot.".split(), s)
             if s["max_words"] >= 11 else "You " + _u("knew that already."
                                                      .split(), s))
    elif s.get("shape") == "punch" and s["max_words"] >= 28:
        t = _u(("He takes the second car down the ramp at a speed that costs "
                "him the front bumper and the paint along one whole side. It "
                "goes badly.").split(), s)
    elif s.get("shape") == "sweep" and s["max_words"] >= 35:
        t = _u(("He takes the second car down the ramp at a speed that costs "
                "him the front bumper and the paint along one whole side on "
                "the first night he has ever been in that garage at all.")
               .split(), s)
    else:
        n = s["target"]
        t = _u((["The", "deal", "costs", "him", "his", "only", "car",
                 "and", "the", "money", "he", "owes", "the", "uncle",
                 "is", "now", "due", "tonight"] * 3)[:n], s) + "."
    if s.get("transition"):
        t = "Arizona, " + t[0].lower() + t[1:]
    elif s.get("after_skip"):
        t = s["jump"].split(",")[0] + ", " + t[0].lower() + t[1:]
    pl = ("loop" if s.get("opens_loop") else "judgment"
          if s["role"] == "reaction" else ("stake", "reasoning")[i % 2])
    return {"slot": s["slot"], "narration": t, "payload": pl,
            "delivery": "normal"}


def _filled_draft():
    plan, ab, slots = _layout()
    import write_plan as WP
    lines = [WP.hook_line(plan)]
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
    # + the gates the first real film (Furious 7) still failed after the
    # slots: no <intro>, judgment share under the floor, two reactions on a
    # peak, a hold after the outro, the story opener, the marker ceiling
    want_silent = ("[PACING-CONTOUR]", "[LOOP-CADENCE]", "[PEAK-ORDER]",
                   "[INTRO-OUTRO]", "[FILM-INTRO]", "[TRANSITION]",
                   "[VOICE-PRESENCE]", "[PERSONA-RUN]")
    loud_ = [m for m in msgs if m.startswith("[PERSONA]") and "judgment BY"
             in m]
    loud_ += [m for m in msgs if m.startswith("[SILENCE-UNIT]")
              and "follows a <outro>" in m]
    loud = [m for m in msgs if m.startswith(want_silent)]
    loud += [m for m in msgs if m.startswith("[RHYTHM]") and (
        "SD is" in m or "punch sentence" in m)]
    loud += [m for m in msgs if m.startswith("[PERSONA]") and "window(s) of"
             in m] + loud_
    errs = W.schema_problems(d["lines"])
    sd = next((m for m in msgs if "SD is" in m), None)
    return (not loud and not errs), (
        f"filled slots: {len(d['lines'])} lines, contour / loop / peak / "
        f"rhythm-SD+punch / persona window+share / intro-outro / film-intro / "
        f"transition / voice-presence silent, schema clean"
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


def test_revision_keeps_slots():
    """A revision reply that leaves slots out cannot drop their lines (the
    Furious 7 act 2 lost ~60 beats that way); a rewrite that breaks its slot
    is not taken; a good one is. Quotes are whole sentences only."""
    _plan, _ab, slots = _layout()
    k = sorted({s["act"] for s in slots})[1]
    mine = WS.slots_for_act(slots, k)
    prev = WS.merge([_fill(s, i) for i, s in enumerate(mine)
                     if s["role"] not in ("hold", "film_speaks")], slots, k)
    said = [l for l in prev if str(l.get("narration") or "").strip()]
    react = next(l for l in said if next(
        s for s in mine if s["slot"] == l["slot"])["role"] == "reaction")
    other = next(l for l in said if l is not react and next(
        s for s in mine if s["slot"] == l["slot"])["role"] == "bridge")
    reply = [{"slot": react["slot"], "narration": "He drives home."},
             {"slot": other["slot"], "narration":
              other["narration"].rstrip(".") + " again."}]
    out, notes = WS.merge_revision(prev, reply, mine, k)
    by = {l.get("slot"): l for l in out}
    checks = [
        (len(out) == len(prev), f"all {len(prev)} lines kept (got {len(out)})"),
        (by[react["slot"]]["narration"] == react["narration"],
         "a reaction rewritten as plain description is not taken"),
        (by[other["slot"]]["narration"].endswith("again."),
         "a rewrite that fits its slot is taken"),
        (any("not taken" in n for n in notes), "the refusal is reported"),
        (WS.whole_sentences("I'm also the last man on Earth whose computer")
         == [] and WS.whole_sentences("Fine. You know he's out there, right?")
         == ["Fine.", "You know he's out there, right?"],
         "a cut-off transcript segment yields no quote"),
        (all(s.get("quote") in " ".join(WS.whole_sentences(s["quote"]))
             for s in slots if s.get("quote")),
         "every planned quote is a whole sentence"),
        ("words" in WS.slot_tag(react_slot := next(
            s for s in mine if s["slot"] == react["slot"])),
         "the reviser sees the word band: " + WS.slot_tag(react_slot)),
    ]
    bad = [w for ok, w in checks if not ok]
    return not bad, ("; ".join(w for _, w in checks) if not bad
                     else "FAILED: " + "; ".join(bad))


def test_draft_conservation():
    """[DRAFT-CONSERVATION]: a complete slot draft is conserved; dropping an
    act's worth of lines, saying a slot twice, or an unreadable plan is a
    hard problem, never a pass ([DUPLICATE-ID] owns repeated line ids)."""
    from pipeline import draft as D
    plan, _ab, slots = _layout()
    (PDIR / "plan.json").write_text(json.dumps(dict(plan, slots=slots)),
                                    encoding="utf-8")
    d = _filled_draft()
    for i, ln in enumerate(d["lines"], 1):
        ln["id"] = i
    ok_full = D.conservation_problems(PROJ, d) == []
    k2 = sorted({s["act"] for s in slots})[1]
    lost = {s["slot"] for s in slots if s["act"] == k2}
    cut = dict(d, lines=[l for l in d["lines"] if l.get("slot") not in lost])
    p_cut = D.conservation_problems(PROJ, cut)
    dup = dict(d, lines=d["lines"] + [dict(d["lines"][5], id=9999)])
    p_dup = D.conservation_problems(PROJ, dup)
    (PDIR / "plan.json").write_text("{not json", encoding="utf-8")
    p_bad = D.conservation_problems(PROJ, d)
    (PDIR / "plan.json").unlink()
    checks = [
        (ok_full, "a complete draft is conserved"),
        (any("missing from the draft" in m for m in p_cut),
         f"act {k2} dropped -> {p_cut[:1]}"),
        (any("said more than once" in m for m in p_dup),
         "a slot said twice is caught"),
        (any("cannot be read" in m for m in p_bad),
         "an unreadable plan is a problem, not a pass"),
    ]
    bad = [w for ok, w in checks if not ok]
    return not bad, ("; ".join(str(w) for _, w in checks) if not bad
                     else "FAILED: " + "; ".join(str(w) for w in bad))


def test_sequence_rules():
    """From Furious 7 run 6: 'that's the price' x3 across parallel acts,
    the outro plus a reaction on the last anchor ([PEAK-ORDER] 2 reactions),
    4 action lines with no stake. The layout prevents the first two; the
    act check catches the rest before the gates do."""
    _plan, _ab, slots = _layout()
    ev = [s for s in slots if s.get("form")]
    forms_vary = all(a["form"] != b["form"] for a, b in zip(ev, ev[1:]))
    out = next(s for s in slots if s["role"] == "outro")
    same_beat_react = [s["slot"] for s in slots if s["beat"] == out["beat"]
                       and s["role"] == "reaction"]
    mine = [s for s in slots if s["role"] in ("bridge", "action")][:6]
    tic = [{"slot": s["slot"], "narration": f"That's the price of {w} again.",
            "delivery": "normal", "payload": "rest"}
           for s, w in zip(mine[:3], ("loyalty", "speed", "trust"))]
    run = [{"slot": s["slot"], "narration": f"He swerves past truck {w}.",
            "delivery": "action", "payload": "rest"}
           for s, w in zip(mine[:4], ("one", "two", "three", "four"))]
    p_tic = WS._act_problems(tic, mine[:3], PDIR)
    p_run = WS._act_problems(run, mine[:4], PDIR)
    checks = [
        (forms_vary and len(ev) > 3,
         f"{len(ev)} EVAL reactions, no two neighbours share a form"),
        (not same_beat_react,
         f"the outro's beat {out['beat']} has no other reaction slot"),
        (any("that's the price" in m for m in p_tic),
         "a phrase repeated in an act is sent back as a tic"),
        (any("no stake" in m for m in p_run),
         "4 action lines with no stake are sent back"),
    ]
    bad = [w for ok, w in checks if not ok]
    return not bad, ("; ".join(w for _, w in checks) if not bad
                     else "FAILED: " + "; ".join(bad))


def test_review_defects():
    """The independent review's defects (2026-11-10), each reproduced:
    1 resolve's tags crashed on any hold line; 2 a slot lost by the fix
    reply could never come back; 3 the brief named narrator words the
    classifier does not hear; 4 sequence checks read the writer's labels,
    not the saved ones; 6 a quote longer than its footage; 7 a sweep shape
    on a slot under 30 words; 8 curly apostrophes failed the quote check."""
    import write_api as W
    from pipeline import pacing_gates as PG
    plan, _ab, slots = _layout()
    k = sorted({s["act"] for s in slots})[1]
    mine = WS.slots_for_act(slots, k)
    prev = WS.merge([_fill(s, i) for i, s in enumerate(mine)
                     if s["role"] not in ("hold", "film_speaks")], slots, k)
    # 1: every line of a real act through resolve's tag builder, holds too
    by_id = {str(l["id"]): l for l in prev}
    slot_of = {str(l["id"]): next(s for s in mine if s["slot"] == l["slot"])
               for l in prev if l.get("slot")}
    try:
        tags = W.resolve_tags(slot_of, by_id)
        ok1 = len(tags) == len(slot_of) and any(
            s["role"] == "hold" for s in slot_of.values())
    except Exception as e:                       # noqa: BLE001
        ok1, tags = False, {"err": repr(e)}
    # 2: a line the act lost comes back from the next reply
    said = [l for l in prev if str(l.get("narration") or "").strip()
            and l.get("slot")]
    lost = said[3]
    cut = [l for l in prev if l is not lost]
    back, notes = WS.merge_revision(cut, [dict(lost)], mine, k)
    ok2 = (any(l.get("slot") == lost["slot"] for l in back)
           and [l.get("slot") for l in back] == [l.get("slot") for l in prev])
    # 3: every narrator word the brief offers is heard and counted
    brief = WS.writer_brief(PDIR, dict(plan, slots=slots), k)
    voice = brief.split("REACTION (VOICE) slots")[1].split("\n")[0]
    offered = ["I", "you", "honestly", "frankly", "of course", "apparently",
               "somehow", "obviously", "naturally", "turns out"]
    deaf = [w for w in offered if w.lower() in voice.lower()
            and not PG.classify_judgment(f"Well, {w} saw it coming.")[0]]
    ok3 = not deaf and "NOT me / my / clearly" in voice
    # 4: the saved labels decide the sequence check
    act_like = [s for s in mine if s["role"] in ("action", "bridge")][:3]
    loop_s = dict(act_like[0], opens_loop=True, role="action")
    seq = [loop_s] + act_like[:3]
    lines4 = [{"slot": x["slot"], "narration": "He swerves past one truck.",
               "delivery": "action", "payload": "stake" if i == 0 else "rest"}
              for i, x in enumerate(seq)]
    ok4 = any("no stake" in m for m in WS._act_problems(
        [WS.code_labels(l, x) for l, x in zip(lines4, seq)], seq, PDIR))
    # 6 / 7: the layout never asks for the impossible
    ok6 = all(WS._wc(s["quote"]) + 2 <= s["max_words"]
              for s in slots if s.get("quote"))
    ok7 = all(s["max_words"] >= 30 for s in slots if s.get("shape") == "sweep")
    ok7 = ok7 and all(s["max_words"] >= WS.REACTION_MIN_WORDS
                      for s in slots if s["role"] == "reaction")
    # 8: curly apostrophes
    q = {"slot": "S1", "beat": "B1", "role": "quote", "anchor": False,
         "peak": False, "min_words": 1, "max_words": 30, "band": "long",
         "quote": "Don't you dare."}
    ok8 = not any("verbatim" in m for m in WS.line_deviations(
        {"narration": "He says, \u201cDon\u2019t you dare.\u201d"}, q))
    # second review (b33d830): a restored intro line got a duplicate id
    k1 = sorted({s["act"] for s in slots})[0]
    m1 = WS.slots_for_act(slots, k1)
    reply1 = [_fill(s, i) for i, s in enumerate(m1)
              if s["role"] not in ("hold", "film_speaks")]
    greet = next(r for r in reply1 if next(
        s for s in m1 if s["slot"] == r["slot"])["role"] == "intro")
    saved1 = WS.merge([r for r in reply1 if r is not greet], slots, k1)
    back1, _n = WS.merge_revision(saved1, [greet], m1, k1)
    ids1 = [l.get("id") for l in back1]
    ok9 = len(ids1) == len(set(ids1)) and any(
        l.get("slot") == greet["slot"] for l in back1)
    # ... a payload fix is taken when the deviation sent back was about it
    one = next(l for l in prev if l.get("slot") and next(
        s for s in mine if s["slot"] == l["slot"])["role"] == "action")
    relab = [dict(one, payload="stake")]
    no_lab, _n = WS.merge_revision(prev, relab, mine, k)
    lab, _n = WS.merge_revision(prev, relab, mine, k, allow_labels=True)
    pick = lambda ls: next(l for l in ls if l.get("slot") == one["slot"])
    ok10 = pick(lab)["payload"] == "stake" and \
        pick(no_lab)["payload"] == one.get("payload")
    # ... a quoted "you" / "?" is the character, not the narrator
    act_s = dict(next(s for s in mine if s["role"] == "action"),
                 min_words=1, max_words=40, band="long", anchor=False,
                 peak=False)
    ok11 = not any("budgeted to the VOICE" in m for m in WS.line_deviations(
        {"narration": 'Dom turns to him: "Where are you going this time?"'},
        act_s))
    checks = [(ok9, f"a restored intro line gets its own id {ids1[:4]}"),
              (ok10, "a payload fix is taken only when the finding is about "
                     "labels"),
              (ok11, "words inside a quotation are not narrator markers"),
              (ok1, f"resolve tags built for every line incl. holds "
                    f"({len(tags)})"),
              (ok2, f"a lost line restored in place ({notes[:1]})"),
              (ok3, f"brief's narrator words all heard (deaf: {deaf})"),
              (ok4, "a stake on a loop slot does not satisfy ACTION-STAKE"),
              (ok6, "no quote longer than its footage"),
              (ok7, "sweep only where 30 words fit; no reaction slot under "
                    f"{WS.REACTION_MIN_WORDS} words"),
              (ok8, "curly apostrophes match the quote")]
    bad = [w for ok, w in checks if not ok]
    return not bad, ("; ".join(w for _, w in checks) if not bad
                     else "FAILED: " + "; ".join(bad))


def test_sad_budget_and_relabel():
    """[TONE-BUDGET] by construction (Furious 7 came back 32.8% `sad`):
    a writer that marks every line sad gets sad only on SAD-OK slots, within
    the budget; and fix_line --relabel brings an already-written draft back
    under it without touching a word."""
    import io
    from contextlib import redirect_stdout
    import fix_line as FL
    plan, ab, slots = _layout()
    cap = int(float(config.TONE_SAD_MAX_FRACTION) * (sum(
        1 for s in slots if s["role"] != "film_speaks") + 1))
    ok_slots = [s for s in slots if s.get("sad_ok")]
    lines = []
    for k in sorted(ab):
        mine = WS.slots_for_act(slots, k)
        rep = [dict(_fill(s, i), delivery="sad") for i, s in enumerate(mine)
               if s["role"] not in ("hold", "film_speaks")]
        lines += WS.merge(rep, slots, k)
    sad = sum(1 for l in lines if l.get("delivery") == "sad")
    ok1 = len(ok_slots) <= cap and sad <= cap
    # relabel an already-written draft
    test_draft_slots()
    dj = PDIR / "draft.json"
    if not dj.exists():
        return False, "DRAFT-SLOTS left no draft.json to relabel"
    d = json.loads(dj.read_text(encoding="utf-8"))
    words = [l.get("narration") for l in d["lines"]]
    for l in d["lines"]:
        if l.get("narration") and l.get("slot"):     # the hook is code's
            l["delivery"] = "sad"
    dj.write_text(json.dumps(d), encoding="utf-8")
    for f in (PDIR / "draft.json.d").glob("act*.json"):
        o = json.loads(f.read_text(encoding="utf-8"))
        for l in o["lines"]:
            if l.get("narration") and l.get("slot"):
                l["delivery"] = "sad"
        f.write_text(json.dumps(o), encoding="utf-8")
    p = json.loads((PDIR / "plan.json").read_text(encoding="utf-8"))
    p["slots_version"] = 1
    (PDIR / "plan.json").write_text(json.dumps(p), encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
        FL.main(["--project", PROJ, "--relabel"])
    d2 = json.loads(dj.read_text(encoding="utf-8"))
    sad2 = sum(1 for l in d2["lines"] if l.get("delivery") == "sad")
    ok2 = (sad2 <= cap and [l.get("narration") for l in d2["lines"]] == words
           and "re-derived" in buf.getvalue())
    checks = [(ok1, f"all-sad writer -> {sad} sad line(s), cap {cap}, "
                    f"{len(ok_slots)} SAD-OK slot(s)"),
              (ok2, f"--relabel: {sad2} sad after (cap {cap}), text "
                    f"unchanged, slots re-derived")]
    bad = [w for ok, w in checks if not ok]
    return not bad, ("; ".join(w for _, w in checks) if not bad
                     else "FAILED: " + "; ".join(bad))


def test_bridge_by_construction():
    """[BRIDGE] (Furious 7: 27 skipped stretches, none recognised): with two
    runs of beats the plan skips, the slot after each opens with its own time
    jump, and bridge_audit on the filled draft finds every gap bridged. The
    same draft without the jumps is caught (known-bad), and each finding
    names the line after the gap so resolve can be pointed at it."""
    import copy
    import write_api as W
    import write_plan as WP
    from pipeline import draft as D, schemas
    plan, ab, _sl = _layout()
    p2 = copy.deepcopy(plan)
    mand = set(json.loads((PDIR / "coverage_policy.json").read_text(
        encoding="utf-8-sig")).get("mandatory") or [])
    beats = [b for b in p2["beats"]]
    runs, i = [], 1
    while i + 2 < len(beats) and len(runs) < 2:
        a, b, c = beats[i], beats[i + 1], beats[i + 2]
        if not ({a["beat"], b["beat"]} & mand) and c.get("lines"):
            a["lines"] = b["lines"] = 0
            a["footage"] = b["footage"] = False
            runs.append((a["beat"], b["beat"]))
            i += 6
        else:
            i += 1
    slots = WS.derive_slots(p2, PROJ, PDIR, ab)["slots"]
    marked = [s for s in slots if s.get("after_skip")]
    lines = [WP.hook_line(p2)]
    for k in sorted(ab):
        mine = WS.slots_for_act(slots, k)
        lines += WS.merge([_fill(s, i) for i, s in enumerate(mine)
                           if s["role"] not in ("hold", "film_speaks")],
                          slots, k)
    for n, ln in enumerate(lines, 1):
        ln["id"] = n

    def audit(ls):
        d = schemas.Draft(project=PROJ, lines=[schemas.Line(
            id=l["id"], narration=l.get("narration") or "",
            clip_start=l.get("clip_start"), clip_end=l.get("clip_end"),
            narration_silence_seconds=l.get("narration_silence_seconds"))
            for l in ls if l.get("clip_start") or l.get("narration")])
        return D.bridge_audit(PROJ, d, D.beat_coverage(PROJ, d))
    good = audit(lines)
    bad_lines = copy.deepcopy(lines)
    for l in bad_lines:
        if l.get("slot") in {s["slot"] for s in marked}:
            l["narration"] = l["narration"].split(", ", 1)[-1]
    bad = audit(bad_lines)
    named = all(g.get("line_after") is not None for g in bad["unbridged"])
    checks = [
        (len(runs) == 2 and len(marked) >= 2,
         f"{len(runs)} skipped run(s) -> {len(marked)} AFTER-A-SKIP slot(s), "
         f"jumps {[s['jump'] for s in marked]}"),
        (len({s['jump'] for s in marked}) == len(marked),
         "each bridge gets its own phrase"),
        (not good["unbridged"], f"filled draft: {len(good['gaps'])} gap(s), "
                                f"{len(good['unbridged'])} unbridged"),
        # (a planned hold inside a seam bridges a gap on its own, so the
        # known-bad may leave fewer than every gap open - at least one must)
        (len(bad["unbridged"]) >= 1 and named,
         f"without the jumps: {len(bad['unbridged'])} unbridged, each naming "
         f"the line after it"),
    ]
    bad_ = [w for ok, w in checks if not ok]
    return not bad_, ("; ".join(w for _, w in checks) if not bad_
                      else "FAILED: " + "; ".join(bad_))


TESTS = {
    "SLOT-LAYOUT":           test_slot_layout,
    "WINDOWS-BY-CODE":       test_windows_by_code,
    "GATES-BY-CONSTRUCTION": test_gates_by_construction,
    "BRIEF-FROM-CONSTANTS":  test_brief_from_constants,
    "DRAFT-SLOTS":           test_draft_slots,
    "COUNTS-FOLLOWED":       test_counts_followed,
    "REVISION-KEEPS-SLOTS":  test_revision_keeps_slots,
    "DRAFT-CONSERVATION":    test_draft_conservation,
    "SEQUENCE-RULES":        test_sequence_rules,
    "REVIEW-DEFECTS":        test_review_defects,
    "SAD-BUDGET-RELABEL":    test_sad_budget_and_relabel,
    "BRIDGE-BY-CONSTRUCTION": test_bridge_by_construction,
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
