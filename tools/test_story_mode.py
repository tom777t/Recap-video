# -*- coding: utf-8 -*-
"""test_story_mode.py - the default writing construction (owner, 2026-11-16).

The owner read a hand-written act 3 of Furious 7 ("so it IS supposed to
sound like this, not like the old metaphors nobody can follow") and approved
the story structure. With config.STYLE_QUOTA_FLOORS False (the default), the
plan stops building lines to hit style proportions:

  NO-PLANNED-REACTIONS  no slot is a planned reaction; no slot opens a loop by
                        construction; no punch / sweep sentence shapes
  CAPACITY-ONLY         a slot carries only what its footage holds (band
                        "free", max = capacity), no aimed length
  BRIEF-TELLS-STORY     the brief carries the story rules and the bad->good
                        pairs, the readers' checklist as rules to write by
                        (referents, pronouns, habit claims), and NONE of the
                        old reaction forms ("That's the ...", "Nobody +
                        verb") or judgment quotas
  ASIDE-ALLOWED         a friend-style reaction on an ACTION slot is not a
                        deviation, and the writer's own `judgment` label
                        stands; over-capacity and a missing quote still are
  CAUSE-BRIDGES         "So the crew heads home", "To find Shaw, ..." cross a
                        skip; "So far" / "So much" do not
  GATES-PASS-STORY      a draft filled from story slots - plain story lines,
                        no asides, no loops - raises no style-floor finding
                        and passes the open / intro / transition contracts
  CONTOUR-NOT-A-QUOTA   the shipped flat draft (top-20% share 0.32, a run of
                        9 one-line beats) raises no contour ERROR; the numbers
                        are still reported and a short anchor is a WARNING;
                        repair_contour moves no line; the planner is told to
                        count lines from what happens, not from a share
  REACTION-CEILING      story mode: reactions up to 20% are clean, up to 25%
                        a warning, above that the draft goes back; legacy
                        keeps 35%
  PROMPTS-TELL-STORY    every prompt the angle and draft stages send carries
                        the story guide and none of the old teaching (a loop
                        every 12 lines, opinion quotas, signature moves,
                        varied lengths, running bits); the old guides are not
                        read by any stage
  ANGLE-NO-REFRAIN      an angle with SETUPS AND PAYOFFS "None." and no
                        signature moves is complete; the old RUNNING BITS
                        heading still parses
  WORD-FLOW-TAUGHT      the guide teaches how it sounds (fold the last event
                        in, goal then obstacle, feeling inside the line, the
                        surprise last at a reveal; tools, not a template) with examples from NO real film the
                        pipeline is tested on; the brief no longer forbids
                        "Meanwhile" and points at the guide
  FLOW-REPORT-ONLY      flow_stats scores a folded, goal-and-obstacle passage
                        above a chopped one on every number, and the draft
                        gates print [FLOW] without adding an error or a
                        finding (no quota, no rewrite)
  LEGACY-RESTORES       STYLE_QUOTA_FLOORS True brings the old construction
                        back (planned reactions and loops)

Run:  python tools/test_story_mode.py      (exit 0 = all pass)
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import test_write_plan as TWP  # noqa: E402   (sets the legacy flag on import)
import write_slots as WS  # noqa: E402

config.STYLE_QUOTA_FLOORS = False          # story mode: the default
PROJ, PDIR = TWP.PROJ, TWP.PDIR
_C: dict = {}


def _layout(floors: bool = False):
    key = f"r{floors}"
    if key not in _C:
        TWP._setup()
        plan = TWP._plan("good")
        from pipeline import angle_spec
        an = {b for a in angle_spec.load(PDIR)["anchors"] for b in a["beats"]}
        for b in plan["beats"]:
            b["hold_after"] = b["beat"] in an
        prev, saved = config.STYLE_QUOTA_FLOORS, WS._prev_open_shapes
        config.STYLE_QUOTA_FLOORS = floors
        WS._prev_open_shapes = lambda: []
        try:
            _C[key] = (plan, TWP._ab(),
                       WS.derive_slots(plan, PROJ, PDIR, TWP._ab())["slots"])
        finally:
            config.STYLE_QUOTA_FLOORS, WS._prev_open_shapes = prev, saved
    return _C[key]


def _story(slots):
    return [s for s in slots if s["role"] not in
            ("hold", "film_speaks", "intro", "outro", "open")]


def t_no_planned_reactions():
    _p, _ab, slots = _layout()
    st = _story(slots)
    react = [s["slot"] for s in st if s["role"] == "reaction"]
    loops = [s["slot"] for s in st if s.get("opens_loop")]
    shapes = [s["slot"] for s in st if s.get("shape")]
    ok = st and not react and not loops and not shapes
    return ok, (f"{len(st)} story slots: 0 planned reactions, 0 planned "
                f"loops, 0 punch/sweep shapes" if ok else
                f"reactions {react[:3]}, loops {loops[:3]}, shapes {shapes[:3]}")


def t_capacity_only():
    from pipeline.preflight import budget_words
    from pipeline.draft import parse_ts
    _p, _ab, slots = _layout()
    bad = []
    for s in _story(slots):
        cap = budget_words(parse_ts(s["clip_end"]) - parse_ts(s["clip_start"]))
        if s.get("band") != "free" or s.get("target") is not None:
            bad.append(f"{s['slot']} band {s.get('band')} aim {s.get('target')}")
        elif s["max_words"] > max(cap, WS.BANDS["free"][0]) + 1:
            bad.append(f"{s['slot']} max {s['max_words']} > capacity {cap}")
    txt = WS.slots_text(slots[:12])
    if "aim" in txt and "up to" not in txt:
        bad.append("slots_text still shows an aimed band")
    return not bad, ("every story slot: capacity only, no aim; the writer "
                     "sees 'up to N words'" if not bad else "; ".join(bad[:4]))


def t_brief():
    plan, _ab, _slots = _layout()
    b = WS.writer_brief(PDIR, plan, 2)
    must = ("WHO does WHAT", "CHANGES HANDS", "friend watching with you",
            "Jakande's men take the laptop", "NO aphorisms",
            "an EARLIER line of yours introduced it", "two possible owners",
            "habit or repetition")
    never = ("REACTION (EVAL)", "\"That's the ...\" / \"Here's the ...\";",
             "Judgment lines:", "OPENS A LOOP", "Nobody / No one / Everyone")
    miss = [m for m in must if m not in b]
    bad = [n for n in never if n in b]
    return not miss and not bad, (
        "story rules + bad->good pairs present; no reaction forms, no "
        "judgment quota" if not miss and not bad
        else f"missing {miss}; still teaches {bad}")


def t_aside_allowed():
    _p, _ab, slots = _layout()
    s = next(x for x in _story(slots) if x["role"] == "action"
             and x["max_words"] >= 12)
    ok_line = {"slot": s["slot"], "narration": "Hobbs cracks his cast off. "
               "That is not how casts work.", "payload": "judgment"}
    dev = WS.line_deviations(ok_line, s)
    lab = WS.code_labels(ok_line, s).get("payload")
    long_line = dict(ok_line, narration=" ".join(["word"] * (s["max_words"] + 6)))
    dev_long = WS.line_deviations(long_line, s)
    q = next((x for x in _story(slots) if x["role"] == "quote"), None)
    dev_q = WS.line_deviations({"slot": q["slot"], "narration": "He says "
                                "something else entirely."}, q) if q else ["-"]
    ok = not dev and lab == "judgment" and dev_long and dev_q
    return ok, ("an aside on an action slot passes and keeps its label; "
                "over-capacity and a dropped quote still deviate" if ok else
                f"aside dev {dev}, label {lab}, long {bool(dev_long)}, "
                f"quote {bool(dev_q)}")


def t_cause_bridges():
    from pipeline.draft import crosses_skip
    yes = ["So the crew heads home to Los Angeles.",
           "To find Shaw, Dom calls Mr. Nobody.",
           "Because the tower is gone, the hack is dead.",
           "With God's Eye gone, Ramsey has one chance left."]
    no = ["So far, so good.", "So much for the plan.", "Dom smiles.",
          "Sophie walks in."]
    miss = [t for t in yes if not crosses_skip(t)]
    wrong = [t for t in no if crosses_skip(t)]
    return not miss and not wrong, (
        f"{len(yes)} cause openers cross a skip, {len(no)} non-bridges do not"
        if not miss and not wrong else f"missed {miss}, wrong {wrong}")


def _fill(s, i):
    if s["role"] == "intro":
        f = WS._facts(PDIR)
        cast = [c for c in f.get("cast") or [] if c.get("lead")][:2]
        t = (f"This is {config.CHANNEL_NAME}, and today it is "
             f"{f.get('title')} from {f.get('year')}."
             if s.get("intro_part") == "greeting" else
             f"{f.get('director')} directs it, with "
             + " and ".join(f"{c['actor']} as {c['role']}" for c in cast)
             + ", shot on real streets at night.")
        return {"slot": s["slot"], "narration": t, "payload": "rest",
                "delivery": "intro"}
    if s["role"] == "outro":
        return {"slot": s["slot"], "narration": "In the end the only car that "
                "was ever really his is the one he gave back. Subscribe and "
                "tell me what to recap next.", "payload": "judgment",
                "delivery": "outro"}
    n = max(3, min(s["max_words"], 9 + (i % 5)))
    if s["role"] == "quote":
        t = f"\"{s['quote']}\" he warns, because the uncle wants the money."
    else:
        base = ("Sean races the uncle's car because he owes him the money, "
                "so he loses the bumper and the deal").split()
        t = " ".join(base[:n]) + "."
    if s.get("transition"):
        t = "Arizona, " + t[0].lower() + t[1:]
    elif s.get("after_skip"):
        t = "So " + t[0].lower() + t[1:]
    if s["role"] == "open" and s.get("open_hook"):
        t = ("One more wreck takes the last thing his father gave him."
             if s.get("closing") == "stake" else
             "Will " + t[0].lower() + t[1:].rstrip(".") + "?")
    return {"slot": s["slot"], "narration": t,
            "payload": ("stake", "reasoning")[i % 2], "delivery": "normal"}


def t_gates_pass():
    from pipeline import craft_gates as CG
    from pipeline import pacing_gates as PG
    plan, ab, slots = _layout()
    lines = []
    for k in sorted(ab):
        mine = WS.slots_for_act(slots, k)
        rep = [_fill(s, i) for i, s in enumerate(mine)
               if s["role"] not in ("hold", "film_speaks")]
        lines += WS.merge(rep, slots, k)
    d = {"title": plan["title"], "lines": lines, "_dir": str(PDIR),
         "open_mode": plan.get("open_mode"), "lever": plan.get("lever")}
    msgs = []
    for r in (CG.craft_report(d), PG.pacing_report(d, PDIR)):
        msgs += r["errors"] + r["warns"]
    floors = ("below the bar", "punch sentence", "[NARRATOR-VOICE]",
              "[LOOP-CADENCE] no line", "with no open loop",
              "under the 15% floor", "carry no narrator presence",
              "end on description", "below the floor of")
    contracts = ("[INTRO-OUTRO]", "[FILM-INTRO]", "[TRANSITION]")
    loud = [m for m in msgs if any(f in m for f in floors)
            or m.startswith(contracts)]
    return not loud, (f"{len(lines)} plain story lines: no style-floor "
                      f"finding; intro/outro, film-intro and transition "
                      f"contracts hold" if not loud else str(loud[:3]))


def t_contour_not_a_quota():
    import copy
    import json
    from pathlib import Path
    import test_pacing as TP
    import write_plan as WP
    from pipeline import pacing_gates as PG
    d = TP._flat()
    r = PG.pacing_report(d, TP.PROJ)
    bad = []
    hard = [e for e in r["errors"] if e.startswith("[PACING-CONTOUR]")
            and ("FLAT" in e or "in a row" in e or "contract is" in e
                 or "are below" in e)]
    if hard:
        bad.append(f"contour quota still an error: {hard[0][:90]}")
    st = r.get("stats") or {}
    if "top20_line_share" not in st or "longest_one_line_run" not in st:
        bad.append("the contour numbers are no longer reported")
    # the plan: code moves nothing
    plan, _ab, _sl = _layout()
    before = [(b["beat"], b.get("lines"), b.get("footage"))
              for b in plan["beats"]]
    p2 = copy.deepcopy(plan)
    ch = WP.repair_contour(p2, PDIR)
    after = [(b["beat"], b.get("lines"), b.get("footage")) for b in p2["beats"]]
    if ch or before != after:
        bad.append(f"repair_contour changed {len(ch)} count(s)")
    t = WP.thresholds_text()
    if "top 20%" in t or "in a row" in t:
        bad.append("the planner is still told the share / run quota")
    if "what HAPPENS" not in t or "changes hands" not in t:
        bad.append("the planner is not told to count from the story")
    # legacy still enforces
    prev = config.STYLE_QUOTA_FLOORS
    config.STYLE_QUOTA_FLOORS = True
    try:
        rl = PG.pacing_report(d, TP.PROJ)
    finally:
        config.STYLE_QUOTA_FLOORS = prev
    if not any("FLAT" in e for e in rl["errors"]):
        bad.append("floors on no longer fails the flat contour")
    return not bad, (f"flat draft (share {st.get('top20_line_share')}, run "
                     f"{st.get('longest_one_line_run')}): reported, not "
                     f"failed; repair_contour moves 0 lines; legacy still "
                     f"fails it" if not bad else "; ".join(bad))


def t_reaction_ceiling():
    import test_pacing as TP
    from pipeline import pacing_gates as PG
    d = {k: TP._mkdraft([("J" if i < k else "P", f"C{i:02d}")
                         for i in range(20)]) for k in (4, 5, 6)}

    def find(dd):
        r = PG.pacing_report(dd, TP.PROJ)
        return ([e for e in r["errors"] if e.startswith("[PERSONA-CEILING]")],
                [w for w in r["warns"] if w.startswith("[PERSONA-CEILING]")],
                r["stats"].get("judgment_share"))
    e4, w4, s4 = find(d[4])
    e5, w5, s5 = find(d[5])
    e6, w6, s6 = find(d[6])
    story = (not e4 and not w4 and not e5 and w5 and e6)
    prev = config.STYLE_QUOTA_FLOORS
    config.STYLE_QUOTA_FLOORS = True
    try:
        legacy = not find(d[6])[0]
    finally:
        config.STYLE_QUOTA_FLOORS = prev
    ok = bool(story) and legacy
    return ok, (f"story: {s4:.0%} clean, {s5:.0%} a warning, {s6:.0%} goes "
                f"back; legacy lets {s6:.0%} through" if ok else
                f"{s4}/{s5}/{s6}: errors {bool(e4)},{bool(e5)},{bool(e6)} "
                f"warns {bool(w4)},{bool(w5)}; legacy {legacy}")


def t_prompts_tell_story():
    import write_api as W
    from pathlib import Path as _P
    bad = []
    old = ("A `loop` at least every 12 lines", "A `judgment` at least every",
           "You are now **required** to have a point of view",
           "rejects anything below 9.0", "Signature moves:**` 2-3",
           "Dangle an OPEN LOOP", "2-4 numbered motifs")
    texts = {"draft_prompt": W._read(W.PROMPTS["draft"]),
             "angle_prompt": W._read(W.PROMPTS["angle"]),
             "story_guide": W._read(W.GUIDE)}
    for n, t in texts.items():
        bad += [f"{n}: {o!r}" for o in old if o in t]
    # the blocks each stage really sends
    ang = W.angle_request(PDIR)["system"]
    dr = W.draft_system(PDIR)
    for n, blocks in (("angle", ang), ("draft", dr)):
        joined = "\n".join(b["text"] for b in blocks)
        if "# Story guide: how this channel tells a film" not in joined:
            bad.append(f"{n} stage does not send the story guide")
        if "PILLAR ZERO" in joined or "The single decisive finding" in joined:
            bad.append(f"{n} stage still sends an old guide")
    src = (_P(W.__file__)).read_text(encoding="utf-8")
    if "recap_style.md\")" in src or "NARRATOR_VOICE.md\")" in src:
        bad.append("write_api still opens an old guide")
    words = len(texts["story_guide"].split())
    ok = not bad and words < 2500
    return ok, (f"angle + draft send the {words}-word story guide; no old "
                f"teaching in any stage prompt" if ok else "; ".join(bad[:4]))


def t_angle_no_refrain():
    import tempfile
    from pathlib import Path as _P
    from pipeline import angle_spec
    import write_api as W
    src = (PDIR / "angle.md").read_text(encoding="utf-8")
    import re as _re
    new = _re.sub(r"(?ms)^## RUNNING BITS\s*$.*?(?=^## )",
                  "## SETUPS AND PAYOFFS\n\nNone.\n\n", src)
    new = _re.sub(r"(?ms)^\*\*Signature moves:\*\*.*?(?=^\*\*Never|^## )",
                  "", new)
    d = _P(tempfile.mkdtemp())
    (d / "angle.md").write_text(new, encoding="utf-8")
    bad = []
    try:
        spec = angle_spec.require(d)
        if spec["motifs"]:
            bad.append("'None.' parsed as a setup")
    except Exception as e:
        bad.append(f"require() rejects it: {e}")
    prob = W.angle_problems(angle_spec.load(d), {
        "angle_md": new, "coverage_policy": {"mandatory": ["B01"]}})
    if prob:
        bad.append(f"angle_problems: {prob}")
    old_spec = angle_spec.load(PDIR)
    if not old_spec["motifs"]:
        bad.append("the old RUNNING BITS heading no longer parses")
    return not bad, ("SETUPS AND PAYOFFS 'None.' + no signature moves is a "
                     "complete angle; the old heading still parses" if not bad
                     else "; ".join(bad))


def t_word_flow_taught():
    import re as _re
    import write_api as W
    g = W._read(W.GUIDE)
    sec = g[g.index("## 3. Word flow"):g.index("## 4. ")]
    bad = []
    for m in ("Fold what just happened", "Goal, then obstacle",
              "only to", "Put feeling inside the narration",
              "the surprise goes last", "tools, not a template"):
        if m not in sec:
            bad.append(f"guide misses {m!r}")
    for film_name in ("Dom", "Ramsey", "Jakande", "Mr. Nobody", "Hobbs",
                      "Shaw", "Natalie", "Sebastian", "Sean"):
        if _re.search(rf"\b{_re.escape(film_name)}\b", sec):
            bad.append(f"word-flow example uses {film_name!r} (leaks into a "
                       f"test film)")
    plan, _ab, _sl = _layout()
    b = WS.writer_brief(PDIR, plan, 2)
    if 'Do not string scenes together with "Later", "Meanwhile"' in b:
        bad.append("the brief still forbids Meanwhile")
    if "Fold the last event into the next sentence" not in b:
        bad.append("the brief does not point at word flow")
    return not bad, ("word flow taught in the guide and the brief, examples "
                     "from no test film" if not bad else "; ".join(bad))


def t_flow_report_only():
    from pipeline import flow_stats as FS
    good = [{"narration": "Hearing the guards coming, Maya pulls the boy "
             "behind a crate to hide him, but the dog finds them anyway. "
             "Desperate to buy time, she begs the guard to let the boy go, "
             "only to realise he is her brother."}]
    chop = [{"narration": "Maya hears the guards. She pulls the boy behind a "
             "crate. The dog finds them. She talks to the guard. He is her "
             "brother."}]
    g, c = FS.flow_stats(good), FS.flow_stats(chop)
    bad = [k for k in ("words_per_sentence", "folded_share", "but_per_k",
                       "purpose_per_k", "feeling_per_k") if not g[k] > c[k]]
    src = open(os.path.join(ROOT, "pipeline", "draft.py"),
               encoding="utf-8").read()
    i = src.index("# [FLOW]")
    block = src[i:i + 700]
    if "errors" in block or "append" in block:
        bad.append("the [FLOW] block in draft.py touches the error list")
    line = FS.flow_line(c)
    if not line.startswith("[FLOW] (report only"):
        bad.append("flow_line does not say it is report-only")
    return not bad, (f"folded passage beats chopped on all 5 numbers "
                     f"(folded {g['folded_share']:.0%} vs "
                     f"{c['folded_share']:.0%}); printed, never an error"
                     if not bad else "; ".join(bad))


def t_legacy_restores():
    _p, _ab, slots = _layout(floors=True)
    st = [s for s in slots if s["role"] not in ("hold", "film_speaks",
                                                "intro", "outro", "open")]
    r = sum(1 for s in st if s["role"] == "reaction")
    lp = sum(1 for s in st if s.get("opens_loop"))
    return r > 0 and lp > 0, (f"floors on: {r} planned reactions, {lp} "
                              f"planned loops - the old construction")


TESTS = [("NO-PLANNED-REACTIONS", t_no_planned_reactions),
         ("CAPACITY-ONLY", t_capacity_only),
         ("BRIEF-TELLS-STORY", t_brief),
         ("ASIDE-ALLOWED", t_aside_allowed),
         ("CAUSE-BRIDGES", t_cause_bridges),
         ("GATES-PASS-STORY", t_gates_pass),
         ("CONTOUR-NOT-A-QUOTA", t_contour_not_a_quota),
         ("REACTION-CEILING", t_reaction_ceiling),
         ("PROMPTS-TELL-STORY", t_prompts_tell_story),
         ("ANGLE-NO-REFRAIN", t_angle_no_refrain),
         ("WORD-FLOW-TAUGHT", t_word_flow_taught),
         ("FLOW-REPORT-ONLY", t_flow_report_only),
         ("LEGACY-RESTORES", t_legacy_restores)]

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
        print(f"{'PASS' if ok else 'FAIL'}  {name:22s} {msg}")
    print("-" * 60)
    print("test_story_mode: all pass" if not fails
          else f"test_story_mode: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
