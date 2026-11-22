# -*- coding: utf-8 -*-
"""write_slots.py - the plan as SLOTS: structure by construction.

Used by tools/write_api.py (plan + draft). Nothing film-specific lives here.

WHY. "Write first, judge later" kept stopping the first real film on new
gate errors after every round: the writer picked the timestamps, the line
lengths, where the loops open and where the narrator reacts, and the gates
then graded each choice. Most of those are not writing decisions at all -
they follow from the plan's per-beat counts and the gates' own rules. So:

  1. The MODEL chooses only the per-beat line counts (plan.json `beats`).
  2. CODE derives one SLOT per line (derive_slots): its beat, its role
     (open | action | quote | reaction | bridge | hold | film_speaks),
     a length band (short / medium / long, drawn so [RHYTHM]'s SD, long-
     sentence and punch bars land in band), whether it opens a loop
     ([LOOP-CADENCE]), and for a quote slot the transcript line to quote
     verbatim. Anchors run action -> quote -> ... -> one reaction
     ([PEAK-ORDER], [PERSONA] anchor ending); a reaction slot lands at
     least every PERSONA_WINDOW_SEC of film ([PERSONA] window); a loop
     opens at least every BAR_LOOP_GAP lines.
  3. The draft OPENS on the film's own picture (R0-R4 of the opening
     study): pipeline/opening.py picks the cold-open scene, and the
     first slots are OPEN slots bound to it, told in-media-res. The
     channel greeting and the film facts follow them (INTRO slots),
     never at 0:00 - the biggest recap channels deleted the greeting
     from frame one and the study measured it.
  4. CODE assigns every clip window: inside the slot's beat, from the
     catalogue's moments, never overlapping ([WINDOW-OVERLAP]), never across
     a reveal's landing ([REVEAL-TIMING]), sized to config.WINDOW_SPAN_RATIO
     of the band's narration, and capped so the band fits the render's
     capacity (preflight.budget_words). Holds are code's too. Black / text
     cards are moved afterwards by write_plan.fix_unwatchable.
  5. The act request carries the slots and a WRITER BRIEF generated from
     the same constants the gates read (writer_brief), so they cannot drift.
  6. check_slots() compares a reply to its slots at once; the deviations go
     back ONCE inside the stage. The gates stay the final check.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import config

ROLES = ("open", "intro", "action", "quote", "reaction", "bridge", "outro",
         "hold", "film_speaks")
# Bumped whenever derive_slots changes what it builds: a plan.json whose slots
# carry an older version is re-derived (write_api.cmd_draft), so a fix here
# reaches a project that already has a plan without re-buying the plan.
SLOTS_VERSION = 20     # 20: no more lines than a beat holds sentences (19: reveal points, 18: budget, 17: holds)


def story_mode() -> bool:
    """STORY MODE (default since 2026-11-16, owner decision): the plan no
    longer builds lines to hit style proportions. With
    config.STYLE_QUOTA_FLOORS False there is no length-band cycle, no
    punch / sweep shapes, no planned loop or reaction slots, and no brief
    that teaches reaction FORMS ("That's the ...", "Nobody + verb" - the
    aphorisms the owner could not follow). A slot carries its footage's
    word CAPACITY, and the writer tells the story in it. True restores
    the old construction exactly."""
    return not bool(getattr(config, "STYLE_QUOTA_FLOORS", False))
# [INTRO-OUTRO] / [FILM-INTRO]: the greeting and the film's facts still
# exist as slots - but AFTER the cold open (R0), never at 0:00.
INTRO_WORDS = (12, 40)
OUTRO_WORDS = (20, 45)
# The cold open itself (R3): 2-4 slots, ~25-54 words, the last one the
# unanswered loop the video exists to answer - question OR stated stake,
# rotated by pipeline.opening.choose_open_shape.


def _r(n: int) -> range:
    return range(n)


def _prev_open_shapes() -> list:
    """The shipped videos' open shapes, newest last, from the channel
    history - the rotation input. A test overrides this function rather
    than the disk. A MISSING store is reported through the notes (the
    rotation cannot run, and 'no history' must not silently impersonate
    video 1); an EMPTY one genuinely is video 1."""
    try:
        from pipeline import variation as V
        hist = V.load_history()
    except Exception:
        return []
    if hist is None:
        # say it once, where the operator reads the plan problems
        return [{"missing_store": str(V.HISTORY)}]
    out = []
    for snap in sorted(hist.values(),
                       key=lambda s: str(s.get("shipped_at") or "")):
        if snap.get("closing_shape") or snap.get("open_len"):
            out.append({"open_len": snap.get("open_len"),
                        "closing": snap.get("closing_shape")})
    return out


# [PERSONA] counts lines where the writer's label AND the classifier agree on
# judgment, over ALL lines; the slots plan this much above the floor, because
# a reaction the classifier does not hear is not counted.
REACTION_SHARE_MARGIN = 0.08
# words per line for each band. The bars they serve (craft_gates):
#   SD of words-per-line >= BAR_SD (9): short ~5, medium ~14, long ~28 in
#   the 30/45/25 mix below give an SD of ~9.5 before any within-band spread.
#   A `long` slot alternates two shapes: PUNCH (a >= 20-word sentence, then
#   one of <= 5 words - BAR_PUNCH_SHARE) and SWEEP (one sentence of >= 30
#   words - BAR_LONG_SHARE, kept far under BAR_LONG_SHARE_MAX).
BANDS = {"short": (3, 7), "medium": (11, 18), "long": (24, 38),
         "free": (3, 40)}     # story mode: capacity only, the writer picks
BAND_CYCLE = ("medium", "short", "long", "medium", "short", "medium",
              "long", "medium", "short", "long", "medium", "medium")
QUOTE_WORDS = (3, 16)            # a transcript line short enough to quote
HOLD_SEC = (2.5, 5.0)            # a planned hold (>= craft_gates.BAR_SILENCE_MIN)
TOL = 2                          # words either side of a band before it is a deviation
REACTION_MIN_WORDS = 9           # a reaction slot whose footage holds fewer is a bridge
MIN_WINDOW = 1.5                 # seconds; a narrower slot window is not bindable
LINE_MIN_SEC = 3.5               # footage one narrated line needs to be a sentence


def _ts(sec: float) -> str:
    h, r = divmod(max(0.0, sec), 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def _pt(ts) -> float:
    from pipeline.draft import parse_ts
    return parse_ts(ts)


def _wc(s: str) -> int:
    return len(str(s or "").split())


def _norm(s: str) -> str:
    s = str(s or "").replace("\u2019", "'").replace("\u2018", "'")
    return " ".join(re.sub(r"[^\w' ]+", " ", s.lower()).split())


# --------------------------------------------------------------------------- #
# inputs
# --------------------------------------------------------------------------- #
def moments(pdir: Path) -> list:
    """[(start, end)] from the catalogue act_payload.py shows the writers."""
    p = next((q for q in (pdir / "shots.json", pdir / "shots_machine.json")
              if q.exists()), None)
    if p is None:
        return []
    out = []
    for s in json.loads(p.read_text(encoding="utf-8-sig")).get("shots") or []:
        try:
            a, b = _pt(s["clip_start"]), _pt(s["clip_end"])
        except Exception:
            continue
        if b > a:
            out.append((a, b))
    return sorted(set(out))


def speech(pdir: Path) -> list:
    """[(start, end, text)] - transcript segments act_payload.py trusts,
    without the sung ones."""
    p = pdir / "transcript.json"
    if not p.exists():
        return []
    try:
        segs = json.loads(p.read_text(encoding="utf-8-sig")).get("segments") or []
    except ValueError:
        return []
    out = [(float(s["start"]), float(s["end"]), str(s.get("text") or "").strip())
           for s in segs if isinstance(s.get("start"), (int, float))
           and float(s["end"]) - float(s["start"]) <= 30.0
           and str(s.get("text") or "").strip()]
    # a sung line is not a line anyone says - never a quote (pipeline/sung.py;
    # Furious 7 quoted the ending song's chorus as Dom's words)
    from pipeline import sung
    return sung.dialogue_only(out, pdir)


def _anchors(pdir: Path) -> tuple:
    """(anchor beats, peak beats) - the angle's anchors, and those whose kind
    or why names a peak (pacing_gates.PEAK_WORDS, PEAK-ORDER's own set)."""
    from pipeline import angle_spec
    from pipeline.pacing_gates import PEAK_WORDS
    try:
        an = angle_spec.load(pdir).get("anchors") or []
    except Exception:
        an = []
    beats = {b for a in an for b in a.get("beats") or []}
    peaks = {b for a in an for b in a.get("beats") or []
             if any(w in f"{a.get('kind', '')} {a.get('why', '')}".lower()
                    for w in PEAK_WORDS)}
    return beats, peaks


# [TONE-BUDGET]: `sad` is for real loss or grief, at most
# TONE_SAD_MAX_FRACTION of the lines. Which anchors are grief is in the
# angle's own words; the writer picks `sad` freely and Furious 7 came back
# 32.8% sad. Code decides where it may go.
GRIEF_WORDS = ("death", "dies", "die ", "dead", "funeral", "grief", "griev",
               "mourn", "loss", "farewell", "goodbye", "burial", "killed",
               "bereave", "tribute")


def _grief_beats(pdir: Path) -> list:
    """Anchor beats whose kind or why names a loss, in the angle's order."""
    from pipeline import angle_spec
    try:
        an = angle_spec.load(pdir).get("anchors") or []
    except Exception:
        an = []
    out = []
    for a in an:
        txt = f"{a.get('kind', '')} {a.get('why', '')} ".lower()
        if any(w in txt for w in GRIEF_WORDS):
            out += [b for b in a.get("beats") or [] if b not in out]
    return out


# [BRIDGE]: a run of >= 2 beats the plan gives no line and no hold is a
# skip; the first line after it must carry the viewer across it. HOW is the
# writer's call, made from WHAT was skipped - code hands the slot the
# skipped beats' own descriptions and the film time they span. Until
# SLOTS_VERSION 9 code handed out a clock phrase in rotation ("By morning",
# "That night", "In the end", ...) by COUNT, and seven of Furious 7's 27
# seams said something false ("By morning" on a chase the same day, "In the
# end" mid-heist). A phrase chosen without the facts is a guess.
SKIP_SHOWN = 4          # skipped beats described per seam (the rest counted)
SKIP_TEXT = 110         # characters of each skipped beat's description


def _beat_texts(project: str) -> dict:
    try:
        from pipeline import catalogue
        return {str(b.get("id")): str(b.get("text") or "")
                for b in catalogue.parse_beats(project).get("beats") or []}
    except Exception:
        return {}


def _short(t: str, n: int = SKIP_TEXT) -> str:
    t = " ".join(str(t).split())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " ..."


# A day-scale phrase says a night passed; it may open a seam only when the
# beat map's own words for the skipped beats (or the scene it lands on) show
# a change of time. Furious 7: "By morning," on a chase the same day.
DAY_PHRASE = re.compile(
    r"(?i)\b(?:(?:the\s+)?next\s+(?:morning|day|night|evening|week)|"
    r"the\s+following\s+(?:morning|day|night|week)|by\s+(?:morning|dawn|"
    r"nightfall)|that\s+(?:night|evening|week)|overnight|"
    r"(?:days?|weeks?|months?|years?)\s+later)\b")
END_PHRASE = re.compile(r"(?i)\bin\s+the\s+end\b")
TIME_WORDS = re.compile(
    r"(?i)\b(?:night|nights|morning|dawn|dusk|evening|sunrise|sunset|"
    r"overnight|next\s+day|days?\s+later|weeks?|months?|years?|later|"
    r"tomorrow|daylight|dark)\b")


def _mark_after_skip(slots: list, order: list, by: dict, project: str = "",
                     rng: dict | None = None) -> None:
    rng = rng or {}
    last_act = max((k for k, _b in order), default=None)
    has = {}
    for x in slots:
        if x["role"] != "film_speaks":   # not in the draft until its stage
            has.setdefault(x["beat"], []).append(x)
    texts = _beat_texts(project) if project else {}
    run = []
    for _k, bid in order:
        b = by.get(bid) or {}
        if not has.get(bid) and not b.get("footage"):
            run.append(bid)
            continue
        if len(run) >= 2:
            nar = [x for x in has.get(bid, []) if x["role"] not in (
                "hold", "film_speaks", "intro", "outro")]
            if nar:
                s = nar[0]
                s["after_skip"] = True
                s["skipped"] = list(run)
                t0, t1 = rng.get(run[0], (None,))[0], rng.get(bid, (None,))[0]
                if t0 is not None and t1 is not None:
                    s["skip_secs"] = int(round(t1 - t0))
                s["skip_what"] = [f"{x}: {_short(texts[x])}" for x in
                                  run[:SKIP_SHOWN] if texts.get(x)]
                # what code can decide, code decides: may this seam say a
                # night passed / the story ended? (the beat map's own words)
                said = " ".join(texts.get(x, "") for x in run + [bid])
                s["skip_time_ok"] = bool(TIME_WORDS.search(said))
                s["skip_end_ok"] = s.get("act") == last_act
                if len(run) > SKIP_SHOWN:
                    s["skip_what"].append(f"... and {len(run) - SKIP_SHOWN} "
                                          f"more beat(s)")
        run = []


def _mmss(sec) -> str:
    try:
        sec = int(sec)
    except (TypeError, ValueError):
        return "?"
    return f"{sec // 60}m{sec % 60:02d}s"


def skip_note(s: dict) -> str:
    """What the writer (and a reviser) sees about the skip before a slot."""
    if not s.get("after_skip"):
        return ""
    sk = s.get("skipped") or []
    span = f"{sk[0]}-{sk[-1]}" if sk else "?"
    return (f"AFTER A SKIP of {len(sk)} beat(s) ({span}, "
            f"{_mmss(s.get('skip_secs'))} of film the viewer does not see: "
            + ("; ".join(s.get("skip_what") or []) or "no description")
            + ")"
            + ("" if s.get("skip_time_ok", True) else
               " - the beat map shows NO change of time here: no "
               "\"next morning\" / \"that night\" / \"days later\""))


BRIDGE_RULE = (
    "- AFTER A SKIP: the viewer must not feel the film teleport. Open the "
    "line on what CHANGED across the skipped beats listed with the slot - "
    "the CAUSE that carries the story on (\"So the crew heads home to Los "
    "Angeles.\", \"To find Shaw, Dom ...\", \"Because the tower is gone, "
    "...\"), "
    "a place (\"Back at the hangar,\", \"In Abu Dhabi,\"), the skipped "
    "event in a clause (\"After a chase through the city, ...\"), a "
    "parallel thread (\"Meanwhile,\"), or a time phrase ONLY when the "
    "skipped beats show that time passed (\"The next morning,\" needs a "
    "night in between; \"In the end\" is for endings). A few minutes of "
    "continuous action is \"Moments later,\" / \"Before long,\", never "
    "a new day. Do not repeat the same opener across seams.")


def _sad_budget(slots: list, pdir: Path) -> None:
    """Mark sad_ok on narrated slots of grief anchors, up to the budget."""
    # the gate divides by the draft's LINES: every slot but film_speaks
    # (added later, and only ever enlarging the denominator) plus the hook
    n_lines = sum(1 for x in slots if x["role"] != "film_speaks") + 1
    cap = int(float(getattr(config, "TONE_SAD_MAX_FRACTION", 0.05)) * n_lines)
    for b in _grief_beats(pdir):
        for x in slots:
            if cap <= 0:
                return
            if x["beat"] == b and x["role"] not in ("hold", "film_speaks",
                                                    "intro"):
                x["sad_ok"] = True
                cap -= 1


def _anchor_inner_beats(pdir: Path) -> set:
    from pipeline import angle_spec
    try:
        an = angle_spec.load(pdir).get("anchors") or []
    except Exception:
        an = []
    return {b for a in an for b in (a.get("beats") or [])[:-1]}


def _landings(project: str) -> list:
    from pipeline.draft import parse_reveal_map
    try:
        return sorted(r["land_sec"] for r in parse_reveal_map(project)
                      if r.get("land_sec") not in (None, float("inf")))
    except Exception:
        return []


def _plan_opening(project: str, pdir: Path) -> dict | None:
    """R1/R2: the picker's cold open for this project, or None when the
    catalogue is not there yet. The opener's window is snapped to the
    catalogue moments inside the picker's shot so the OPEN slots bind to
    real footage."""
    from pipeline import opening as OP
    try:
        data = OP.read(project)
    except (OSError, ValueError):
        return None
    if not data["candidates"]:
        return None
    # old projects' film_facts carry no `genre` (the facts stage only
    # started writing it); the intro style preset names a genre well
    # enough to keep comedies off THRILL (horror/romance/epic are the
    # unambiguous three)
    fallback = ""
    sp = Path(pdir) / "intro_style.txt"
    if sp.exists():
        fallback = sp.read_text(encoding="utf-8-sig").strip()
    lever, lever_source = OP.lever_for(data["facts"], fallback=fallback)
    pick = OP.choose(data["candidates"], lever=lever,
                     lands=data["lands"], runtime_sec=data["runtime_sec"])
    if not pick.get("opener") or pick["opener"].get("score", 0) <= 0:
        return None
    op = pick["opener"]
    by = {c["id"]: c for c in data["candidates"]}
    c = by.get(op["id"]) or {}
    a, z = float(c.get("start") or 0.0), float(c.get("end") or 0.0)
    moms = [m for m in moments(Path(pdir)) if a <= m[0] < z]
    if moms:
        a = moms[0][0]
        z = max(z for _x, z in moms if a <= _x < z)
    return {"opener": dict(op, window=(a, z)), "open_mode": pick["open_mode"],
            "lever": lever, "lever_source": lever_source,
            "notes": pick.get("notes") or []}


def _beat_ranges(project: str, beats: list) -> dict:
    from pipeline.draft import beat_times
    try:
        bt = beat_times(project).get("ordered") or []
    except Exception:
        bt = []
    rng = {}
    for i, (bid, t) in enumerate(bt):
        rng[bid] = (t, bt[i + 1][1] if i + 1 < len(bt) else t + 120.0)
    return rng


def _secs(words: int, tag: str | None = None) -> float:
    from pipeline.schemas import estimate_narration_seconds
    return estimate_narration_seconds(words, tag)


# --------------------------------------------------------------------------- #
# the layout
# --------------------------------------------------------------------------- #
def _roles(n: int, has_quote: bool) -> list:
    """One role per narrated line of a beat: a bridge alone; otherwise the
    moment first (action), the film's own words second when the beat has a
    quotable line, and ONE reaction last - the shape [PEAK-ORDER] and the
    [PERSONA] anchor-ending rule ask of an anchor, used for every dwelt-on
    beat so the shape never depends on the writer."""
    if n <= 0:
        return []
    if n == 1:
        return ["bridge"]
    if story_mode():
        # no reaction is PLANNED: the writer may react anywhere it helps,
        # and the gates' ceilings stop too much of it
        if n == 2:
            return ["action", "action"]
        return ["action", "quote" if has_quote else "action"] + \
            ["action"] * (n - 2)
    if n == 2:
        return ["action", "reaction"]
    mid = ["quote" if has_quote else "action"] + ["action"] * (n - 3)
    return ["action"] + mid + ["reaction"]


def _split(a: float, b: float, k: int, moms: list) -> list:
    """k contiguous, non-overlapping windows inside [a, b): whole catalogue
    moments grouped by cumulative length when there are at least k of them
    (a window then follows the film's own cuts), else an even split."""
    ms = [(x, min(b, y)) for x, y in moms if a <= x < b]
    ms = [(x, y) for x, y in ms if y - x > 0.2]
    if len(ms) >= k:
        tot = sum(y - x for x, y in ms)
        groups, cur, acc = [], [], 0.0
        for i, m in enumerate(ms):
            cur.append(m)
            acc += m[1] - m[0]
            need = k - len(groups) - 1          # groups still to open after this
            left = len(ms) - i - 1
            if need and (acc >= tot * (len(groups) + 1) / k or left == need):
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        if len(groups) == k:
            return [(g[0][0], g[-1][1]) for g in groups]
    step = (b - a) / k
    return [(a + i * step, a + (i + 1) * step) for i in range(k)]


POINT_MIN_WORDS = 12     # a story point moved past a reveal needs a sentence
_COPULA = {"is": "be", "was": "be", "are": "be", "were": "be", "'s": "be"}


def _toks(text: str) -> list:
    out = []
    for w in re.findall(r"[a-z0-9]+|'s", str(text).lower()):
        if w in ("the", "a", "an"):
            continue
        out.append(_COPULA.get(w, w))
    return out


def _states(text: str, term: str) -> bool:
    """Does `text` state the protected `term` - the term's words in order,
    articles dropped and any form of the copula alike ("the hospital is a
    set" states "the hospital was a set"; "Chen Mai ... the impostor" does
    not state "Chen Mai is an impostor")?"""
    t, n = _toks(text), _toks(term)
    return bool(n) and any(t[i:i + len(n)] == n
                           for i in range(len(t) - len(n) + 1))


def _hidden_names(project: str) -> list:
    """[(time, [name])] for a SECOND identity of one person: two characters
    in names.json played by the same actor (Lost in the Stars: the lawyer
    Chen Mai and Shen Man, both Ni Ni). The name the beat map shows later is
    a secret until then - a story point that names it earlier spoils who
    she is ("Muzi's location is now with Shen Man and the troupe" at B102,
    before the B115 unmasking). Treated like a reveal landing at the beat
    where that name first appears."""
    from pipeline import catalogue as CAT
    from pipeline.draft import parse_ts
    try:
        names = json.loads((config.project_dir(project) / "names.json")
                           .read_text(encoding="utf-8-sig")).get("names") or []
        beats = CAT.parse_beats(project).get("beats") or []
    except Exception:
        return []
    by_actor: dict = {}
    for n in names:
        a = str(n.get("actor") or "").strip().lower()
        if a and n.get("character"):
            by_actor.setdefault(a, []).append(str(n["character"]))
    first: dict = {}
    for b in beats:
        try:
            t = parse_ts(b.get("ts") or b.get("time"))
        except Exception:
            continue
        for c in b.get("chars") or []:
            first.setdefault(str(c).lower(), t)
    out = []
    for chars in by_actor.values():
        seen = [(first[c.lower()], c) for c in chars if c.lower() in first]
        if len(chars) < 2 or len(seen) < 2:
            continue
        seen.sort()
        out += [(t, [c]) for t, c in seen[1:] if t > seen[0][0]]
    return out


def reveal_marks(project: str) -> list:
    """[(land_sec, terms)]: the reveal map's landings and the hidden second
    identities - what a story point must not state before its time."""
    try:
        from pipeline.draft import parse_reveal_map
        rv = [(r["land_sec"], list(r.get("holds") or []))
              for r in parse_reveal_map(project)
              if r.get("land_sec") not in (None, float("inf"))]
    except Exception:
        rv = []
    return rv + _hidden_names(project)


def remark_points(project: str, pdir: Path) -> list:
    """Re-place the story points on plan.json's EXISTING slots (the layout
    itself untouched) - for a written draft whose slots a newer layout may
    not re-derive (that would move lines). Returns the slots whose point
    changed; plan.json is rewritten only then."""
    from pipeline.draft import parse_ts
    p = Path(pdir) / "plan.json"
    try:
        plan = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    slots = plan.get("slots") or []
    if not slots:
        return []
    work = []
    for x in slots:
        y = {k: v for k, v in x.items() if k not in ("must_say", "must_keys")}
        try:
            y["a"] = parse_ts(x["clip_start"]) if x.get("clip_start") else None
        except Exception:
            y["a"] = None
        work.append(y)
    _mark_story_points(work, plan, reveal_marks(project))
    changed = []
    for x, y in zip(slots, work):
        if (x.get("must_say") or None, x.get("must_keys") or None) != (
                y.get("must_say") or None, y.get("must_keys") or None):
            changed.append(x.get("slot"))
            for k in ("must_say", "must_keys"):
                if y.get(k):
                    x[k] = y[k]
                else:
                    x.pop(k, None)
    if changed:
        p.write_text(json.dumps(plan, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    return changed


def _mark_story_points(slots: list, plan: dict,
                       reveals: list | None = None) -> None:
    """Each spine step / holder change rides on the FIRST story slot of its
    beat as `must_say` (+ the names that line must contain) - or, when it
    states a reveal (`reveals`: [(land_sec, hold terms)]), on the first story
    slot after that reveal lands. The plan gave
    the beat a line for it (write_plan.repair_story_points); this tells the
    writer what that line is FOR."""
    import write_plan as WP
    pts = WP.story_points(plan)
    story = [s for s in slots if s["role"] not in (
        "hold", "film_speaks", "open", "intro")]
    done = set()
    for s in story:
        b = s.get("beat")
        if b not in pts or b in done:
            continue
        done.add(b)
        for p in pts[b]:
            # a point that STATES a reveal is said once the reveal has
            # landed: on the first story line at or after its landing
            # (Lost in the Stars B113: "...the hospital is a set; Chen Mai is
            # Shen Man" sat on 01:36:47, before both reveals - the slot made
            # the writer spoil them, and REVEAL-TIMING then refused the fix)
            land = max([t for t, holds in (reveals or [])
                        if t > (s.get("a") or 0) + 0.5
                        and any(_states(p["say"], h) for h in holds)]
                       or [None], key=lambda x: -1 if x is None else x)
            to = s
            if land is not None:
                after = [x for x in story if x.get("a") is not None
                         and x["a"] >= land - 0.5]
                # the first one with room to say it (B115's 1.6 s slots
                # hold four words; the point needs a sentence)
                roomy = [x for x in after
                         if (x.get("max_words") or 0) >= POINT_MIN_WORDS]
                # one point per line where the footage allows
                to = next((x for x in roomy if not x.get("must_say")),
                          roomy[0] if roomy else (after[0] if after else s))
            to["must_say"] = "; ".join(
                [x for x in [to.get("must_say"), p["say"]] if x])
            if p["keys"]:
                to.setdefault("must_keys", []).append(p["keys"])


def derive_slots(plan: dict, project: str, pdir: Path, ab: dict) -> dict:
    """{"slots": [...], "problems": [...]} - deterministic from the plan."""
    from pipeline import craft_gates as CG
    from pipeline.preflight import budget_words
    pdir = Path(pdir)
    by = {b["beat"]: b for b in plan.get("beats") or []}
    order = [(k, bid) for k in sorted(ab) for bid in ab[k]]
    rng = _beat_ranges(project, [b for _k, b in order])
    moms, segs = moments(pdir), speech(pdir)
    anchors, peaks = _anchors(pdir)
    # a multi-beat anchor ("B79/B80") is ONE peak: only its last beat ends on
    # the reaction ([PEAK-ORDER] counts reactions over the whole anchor)
    not_last = _anchor_inner_beats(pdir)
    lands = _landings(project)
    ratio = float(getattr(config, "WINDOW_SPAN_RATIO", 1.7))
    slots, problems = [], []
    for k, bid in order:
        b = by.get(bid) or {}
        n = int(b.get("lines") or 0)
        lo, hi = rng.get(bid, (None, None))
        if lo is None:
            if n:
                problems.append(f"{bid}: no time in the beat map - no slot "
                                f"window can be assigned")
            continue
        inbeat = [s for s in segs if lo <= s[0] < hi
                  and QUOTE_WORDS[0] <= _wc(s[2]) <= QUOTE_WORDS[1]]
        # no more lines than the beat's footage holds sentences: Lost in the
        # Stars B115 (8.9 s) was planned 4 lines + a hold - four 1.6 s slots
        # the writer filled with "Shen Man leads." / "Chen Mai, unmasked." /
        # "He Fei, exposed." / "Nowhere to run." and the film's main twist
        # was never said in a sentence
        room = (hi - lo) - (HOLD_SEC[0] if b.get("hold_after") else 0.0)
        fit = max(1, int(room // LINE_MIN_SEC))
        if n > fit:
            problems.append(f"{bid}: {n} line(s) planned on {hi - lo:.1f}s "
                            f"of footage - {fit} slot(s), so each line has "
                            f"room for a sentence")
            n = fit
        roles = _roles(n, bool(inbeat))
        if bid in not_last and roles and roles[-1] == "reaction":
            roles[-1] = "action"
        if n == 0 and b.get("footage"):
            roles = ["hold"]
        if b.get("hold_after") and n:
            roles = roles + ["hold"]
        if b.get("film_speaks"):
            roles = roles + ["film_speaks"]
        if not roles:
            continue
        # a window may not straddle a reveal's landing: the beat is cut there
        wins = _split(lo, hi, len(roles), moms)
        for i, role in enumerate(roles):
            a, z = wins[i]
            for t in lands:
                if a < t < z:
                    if t - a >= MIN_WINDOW:
                        z = t
                    else:
                        a = t
            slots.append({"slot": "", "act": k, "beat": bid, "role": role,
                          "anchor": bid in anchors, "peak": bid in peaks,
                          "a": round(a, 3), "z": round(z, 3)})
    # the OUTRO is the last narrated slot of the last act; nothing is held
    # after it (the film's own end is credits - black - and a hold there is
    # a silence unit that follows no reveal, death or climax)
    nar_i = [i for i, x in enumerate(slots)
             if x["role"] not in ("hold", "film_speaks")]
    if nar_i:
        last = nar_i[-1]
        slots[last]["role"] = "outro"
        slots = slots[:last + 1]
        # the outro is a judgment line: on its own beat it IS the reaction
        # ([PEAK-ORDER] allows one; Furious 7's last anchor carried two)
        ob = slots[last]["beat"]
        for x in slots[:last]:
            if x["beat"] == ob and x["role"] == "reaction":
                x["role"] = "bridge"
    # the cold open (R0-R2): OPEN slots on the picker's scene come FIRST;
    # the greeting and the facts follow them, never at 0:00. When the
    # picker cannot run (no catalogue yet) the problems say so and the
    # draft keeps the old greeting-first shape - [OPEN] then reports
    # not-constructed rather than passing silently.
    opening = _plan_opening(project, pdir)
    open_slots: list = []
    if opening and opening.get("opener"):
        op = opening["opener"]
        c0, c1 = op["window"]
        # the story slot whose window contains the opener's would overlap
        # it ([WINDOW-OVERLAP]): give the opener the front of it and move
        # the story slot's start to where the cold open ends - the body
        # continues the moment instead of repeating it. A story slot too
        # short to survive that is dropped; its beat keeps the rest.
        for s in slots:
            if s["role"] in ("hold", "film_speaks") or s["a"] is None:
                continue
            if s["a"] <= c0 and c1 <= s["z"]:
                if s["z"] - c1 >= MIN_WINDOW:
                    s["a"] = c1
                elif s["a"] < c0:
                    s["a"] = c0
                else:
                    slots.remove(s)
                break
        k1 = order[0][0] if order else 1
        # the open's SHAPE rotates against the channel's own history
        # (2-4 lines, closing on a question or a stated stake): a fixed
        # three-line question shape is the robotic tell even when every
        # line in it is good
        from pipeline import opening as OP
        _shapes = _prev_open_shapes()
        if any(s.get("missing_store") for s in _shapes):
            problems.append(
                "opening: shape rotation NOT RUN - the channel history "
                "store is missing at " + str(
                    _shapes[-1]["missing_store"])
                + ". Every worktree shares that one fixed path; put the "
                  "store back (or ship the first video with "
                  "tools/ship.py) - a missing store is not video 1.")
        shape = OP.choose_open_shape(
            [s for s in _shapes if not s.get("missing_store")])
        # the lines run over ONE scene: contiguous sub-windows of the
        # opener, so [WINDOW-OVERLAP] sees the same shape as anywhere
        # else - the scene plays unbroken under the open's lines
        sub = _split(c0, c1, shape["n_lines"],
                     [(m[0], m[1]) for m in moments(Path(pdir))
                      if c0 <= m[0] < c1])
        open_slots = [{"slot": "", "act": k1, "beat": "OPEN", "role": "open",
                       "anchor": False, "peak": False, "a": sub[i][0],
                       "z": sub[i][1],
                       "open_mode": opening["open_mode"],
                       "lever": opening["lever"]}
                      for i in _r(shape["n_lines"])]
        open_slots[-1]["open_hook"] = True
        open_slots[-1]["closing"] = shape["closing"]
        open_slots[-1]["hook_question"] = str(
            (plan.get("hook") or {}).get("hook_question") or "").strip()
        if opening["open_mode"] == "B":
            # the fragment pivots back: the story's own start needs the
            # anchor ([TRANSITION]), the fragment itself does not
            open_slots[0]["pivot"] = True
        opening["shape"] = shape
    else:
        problems.append("opening: no cold open - the opener picker found "
                        "nothing (shots.json missing or empty)")
    # the INTRO block: the channel greeting, then the film's facts - act 1,
    # straight after the cold open, no clip window (over the brand block)
    if order:
        k1 = order[0][0]
        intro_slots = [{"slot": "", "act": k1, "beat": "INTRO",
                        "role": "intro", "intro_part": part, "anchor": False,
                        "peak": False, "a": None, "z": None}
                       for part in ("greeting", "facts")]
        slots = open_slots + intro_slots + slots
    # quotes: the transcript line inside the slot's own window (or its beat)
    used_q = set()
    for s in slots:
        if s["role"] != "quote":
            continue
        lo, hi = rng[s["beat"]]
        # a transcript segment is cut where the speaker paused, not where the
        # sentence ends ("I'm also the last man on Earth whose computer");
        # a quote is a WHOLE sentence inside the segment, or no quote
        def _whole(lo_, hi_):
            return [(x[0], x[1], q) for x in segs if lo_ <= x[0] < hi_
                    for q in whole_sentences(x[2])
                    if QUOTE_WORDS[0] <= _wc(q) <= QUOTE_WORDS[1]]
        c = _whole(s["a"], s["z"]) or _whole(lo, hi)
        c = [x for x in c if x[2] not in used_q]
        if c:
            q = max(c, key=lambda x: (_wc(x[2]) <= 10, _wc(x[2])))
            s["quote"] = q[2]
            used_q.add(q[2])
        else:
            s["role"] = "action"
    narrated = [s for s in slots
                if s["role"] not in ("hold", "film_speaks", "intro", "outro")]
    # [TRANSITION] after the opening study: OPEN-A is the story's own start,
    # so ITS first line carries the time-or-place anchor; OPEN-B is a
    # flash-forward, so the anchor belongs to the first STORY line after
    # the intro block instead - the fragment opens mid-scene by design.
    story = [s for s in narrated if s.get("beat") != "OPEN"]
    if open_slots and open_slots[0].get("open_mode") == "A":
        open_slots[0]["transition"] = True
        if open_slots[0]["role"] == "reaction":
            open_slots[0]["role"] = "bridge"
    elif story:
        story[0]["transition"] = True
        if story[0]["role"] == "reaction":
            story[0]["role"] = "bridge"
    # [PERSONA] window: the gate walks PERSONA_WINDOW_SEC windows from the
    # first line and flags one holding >= 3 lines with no narrator presence
    # (peak beats exempt). The same walk here turns the window's last bridge
    # (else its last non-anchor action) into a reaction.
    w = float(config.PERSONA_WINDOW_SEC)
    # the walk sees the outro too (the gate does), but never converts it
    walk = narrated + [x for x in slots if x["role"] == "outro"]
    if narrated and not story_mode():
        t0 = _pt(narrated[0]["clip_start"]) if "clip_start" in narrated[0] \
            else narrated[0]["a"]
        t = t0
        end = walk[-1]["a"]
        while t <= end:
            inside = [x for x in walk if t <= x["a"] < t + w]
            if len(inside) >= 3 and not any(
                    x["role"] == "reaction" or x["peak"] for x in inside):
                c = [x for x in inside if x["role"] == "bridge"
                     and not x.get("transition")] or \
                    [x for x in inside if x["role"] == "action"
                     and not x["anchor"] and not x.get("transition")]
                if c:
                    c[-1]["role"] = "reaction"
            t += w
    # [PERSONA] share: enough REACTION slots that the agreed judgment share
    # clears the floor - more bridges become reactions, spread evenly, never
    # on an anchor and never next to another reaction ([PERSONA-RUN])
    want = int(-(-len(slots) * (float(config.PERSONA_JUDGMENT_SHARE_MIN)
                                + REACTION_SHARE_MARGIN) // 1))
    have = sum(1 for x in narrated if x["role"] == "reaction")
    if have < want and not story_mode():
        idx = [i for i, x in enumerate(narrated) if x["role"] == "bridge"
               and not x["anchor"] and not x["peak"]
               and not x.get("transition")]
        need = want - have
        step = max(1.0, len(idx) / max(1, need))
        pick, j = [], 0.0
        while j < len(idx) and len(pick) < need:
            pick.append(idx[int(j)])
            j += step
        for i in pick:
            near = narrated[max(0, i - 1):i + 2]
            if any(x["role"] == "reaction" for x in near):
                continue
            narrated[i]["role"] = "reaction"
    # [LOOP-CADENCE]: a loop at least every BAR_LOOP_GAP lines - planned at
    # BAR_LOOP_GAP - 2, preferring a beat's last line (a promise of the next)
    gap = max(3, int(CG.BAR_LOOP_GAP) - 2)
    since = 0
    for i, s in enumerate(narrated):
        since += 1
        s["opens_loop"] = False
        nxt_new = i + 1 >= len(narrated) or narrated[i + 1]["beat"] != s["beat"]
        if story_mode():
            continue          # no loop is planned; the writer may open one
        if since >= gap or (since >= gap - 3 and nxt_new
                            and s["role"] in ("bridge", "action")):
            if s["role"] != "reaction" and not s["peak"]:
                s["opens_loop"] = True
                since = 0
    # length bands: the cycle's mix, honoured even where one window is too
    # short for its band - the band it could not take is DEBT, paid by the
    # next slot with the footage for it. Then the window is trimmed to the
    # band (WINDOW_SPAN_RATIO), never widened.
    long_n, debt = 0, 0
    j = 0          # the cycle counts STORY lines; the open slots carry theirs
    _open_bands = (((opening or {}).get("shape") or {}).get("bands")
                   or ("medium", "short", "medium"))
    scale = _act_scale(narrated, plan) if story_mode() else {}
    for i, s in enumerate(narrated):
        if s["role"] == "open":
            n_open = sum(1 for x in narrated[:i] if x["role"] == "open")
            band = _open_bands[min(n_open, len(_open_bands) - 1)]
        elif story_mode():
            # capacity only: as many words as the footage holds, as few as
            # the story needs. No cycle, no debt, no punch / sweep shape.
            cap = budget_words(s["z"] - s["a"])
            if s["act"] in scale:
                full = min(BANDS["free"][1], cap)
                cap = int(full * scale[s["act"]])
                if s["role"] == "quote":
                    # the quote and its attribution still fit
                    cap = min(full, max(cap, _wc(s.get("quote")) + 2))
            s["band"] = "free"
            s["max_words"] = int(max(1, min(BANDS["free"][1], cap)))
            s["min_words"] = int(min(BANDS["free"][0], s["max_words"]))
            s["target"] = None
            if s["role"] == "quote" and _wc(s.get("quote")) + 2 > \
                    s["max_words"]:
                s["role"] = "action"
                s.pop("quote", None)
            want = s["a"] + ratio * _secs(s["max_words"])
            if want < s["z"] - 0.05:
                s["z"] = round(max(want, s["a"] + MIN_WINDOW), 3)
            if s["z"] - s["a"] < MIN_WINDOW:
                problems.append(f"{s['beat']}: a {s['role']} slot has only "
                                f"{s['z'] - s['a']:.1f}s of footage")
            continue
        else:
            band = BAND_CYCLE[j % len(BAND_CYCLE)]
            j += 1
        cap = budget_words(s["z"] - s["a"])
        if band == "long" and (s["role"] in ("quote", "reaction")
                               or cap < BANDS["long"][0]):
            debt += 1
            band = "medium"
        elif band != "long" and debt and s["role"] not in (
                "quote", "reaction") and cap >= BANDS["long"][0]:
            debt -= 1
            band = "long"
        if s["role"] in ("quote", "reaction") and band == "short":
            band = "medium"
        while band != "short" and cap < BANDS[band][0]:
            band = {"long": "medium", "medium": "short"}[band]
        s["band"] = band
        s["max_words"] = int(min(BANDS[band][1], cap))
        s["min_words"] = int(min(BANDS[band][0], s["max_words"]))
        if s["role"] == "reaction" and s["max_words"] < REACTION_MIN_WORDS:
            # a reaction must be heard as the narrator AND be clear; in 3-7
            # words it is rarely both (Furious 7 line 40: three resolve
            # rounds could not fit one). The beat's moment carries it.
            s["role"] = "bridge"
        if s["role"] == "quote" and _wc(s.get("quote")) + 2 > s["max_words"]:
            # the footage cannot hold the quote and its attribution: a slot
            # that cannot be filled is not a slot (it was S083, 3-4 words
            # for a 13-word quote)
            s["role"] = "action"
            s.pop("quote", None)
        # an aim inside the band, alternating low / high, so the act's
        # words-per-line SD lands over [RHYTHM]'s bar by construction
        lo_, hi_ = s["min_words"], s["max_words"]
        s["target"] = int(round(lo_ + (hi_ - lo_) * (0.2 if i % 2 else 0.85)))
        if band == "long":
            long_n += 1
            s["shape"] = ("sweep" if long_n % 3 == 0 and s["max_words"] >= 30
                          else "punch")
        want = s["a"] + ratio * _secs(s["max_words"])
        if want < s["z"] - 0.05:
            s["z"] = round(max(want, s["a"] + MIN_WINDOW), 3)
        if s["z"] - s["a"] < MIN_WINDOW:
            problems.append(f"{s['beat']}: a {s['role']} slot has only "
                            f"{s['z'] - s['a']:.1f}s of footage")
    for s in slots:
        if s["role"] == "intro":
            s["band"] = "intro"
            s["min_words"], s["max_words"] = INTRO_WORDS
            s["target"] = 18 if s.get("intro_part") == "greeting" else 32
            s["opens_loop"] = False
        elif s["role"] == "outro":
            cap = budget_words(s["z"] - s["a"])
            s["band"] = "outro"
            s["max_words"] = int(max(OUTRO_WORDS[0], min(OUTRO_WORDS[1], cap)))
            s["min_words"] = OUTRO_WORDS[0]
            s["target"] = int((s["min_words"] + s["max_words"]) / 2)
            s["opens_loop"] = False
            if cap < OUTRO_WORDS[0]:
                problems.append(f"{s['beat']}: the outro's footage holds "
                                f"{cap} words, under the {OUTRO_WORDS[0]} an "
                                f"outro needs - it will run over its window")
    _voice_budget(slots)
    _sad_budget(slots, pdir)
    _mark_after_skip(slots, order, by, project, rng)
    _mark_story_points(slots, plan, reveal_marks(project))
    _size_holds(slots)
    # ids, and the windows as timestamps; no two windows overlap by
    # construction (contiguous splits of disjoint beats, only ever trimmed)
    for i, s in enumerate(slots, 1):
        s["slot"] = f"S{i:03d}"
        a_, z_ = s.pop("a"), s.pop("z")
        s["clip_start"] = _ts(a_) if a_ is not None else None
        s["clip_end"] = _ts(z_) if z_ is not None else None
    return {"slots": slots, "problems": problems
            + [f"opening: {n}" for n in (opening or {}).get("notes")
               or []]
            + ([f"opening: lever THRILL (default, no genre) - no genre "
                f"in film_facts.json and no intro_style preset spoke; "
                f"type the film's lead-sentence genre into "
                f"film_facts.json `genre` and re-derive to change it"]
               if (opening or {}).get("lever_source") == "default"
               else []),
            "version": SLOTS_VERSION,
            "open_mode": (opening or {}).get("open_mode"),
            "lever": (opening or {}).get("lever"),
            "lever_source": (opening or {}).get("lever_source"),
            "opener": (opening or {}).get("opener"),
            "open_len": ((opening or {}).get("shape") or {}).get("n_lines"),
            "closing_shape": ((opening or {}).get("shape") or
                              {}).get("closing")}


def _act_scale(narrated: list, plan: dict) -> dict:
    """{act: factor} that shrinks story slots' word capacity so the act's
    slots together hold its plan word budget, not their footage's capacity.

    Story mode gave each slot as many words as its footage holds; Lost in the
    Stars' 225 slots held 7,691 words against a plan of 3,550, the writers
    wrote 4,436 (every act over its budget, 7-45%), and [RUNTIME-BAND]
    blocked the draft at 22.1 finished minutes. Built right instead: the
    act's budget, less what its intro / outro / open slots carry, is shared
    over the rest in proportion to their footage (a quote keeps room for
    itself). Never above 1 - a budget bigger than the footage is the
    footage's limit."""
    from pipeline.preflight import budget_words
    budgets = {int(a["act"]): int(a.get("word_budget") or 0)
               for a in plan.get("acts") or []
               if str(a.get("act", "")).isdigit()}
    caps: dict = {}
    fixed: dict = {}
    for s in narrated:
        k = s.get("act")
        if s["role"] in ("open", "intro", "outro"):
            fixed[k] = fixed.get(k, 0) + {"intro": INTRO_WORDS[1],
                                          "outro": OUTRO_WORDS[1]}.get(
                s["role"], BANDS["medium"][1])
        else:
            caps[k] = caps.get(k, 0) + min(BANDS["free"][1], budget_words(
                s["z"] - s["a"]))
    out = {}
    for k, c in caps.items():
        b = budgets.get(k)
        if b and c > 0:
            out[k] = max(0.2, min(1.0, (b - fixed.get(k, 0)) / c))
    return out


def _size_holds(slots: list) -> None:
    """A hold's length: its window clamped to HOLD_SEC. A window SHORTER
    than the minimum used to be stretched past its end - into the next
    line's footage (Lost in the Stars: hold 220 grew to 5930.4-5932.9 over
    line 221 at 5932.375, [WINDOW-OVERLAP]). The hold may grow only into
    footage no other slot holds: forward up to the next window, then back
    to the previous one, then out of the start of the narrated window after
    it while that keeps what its line needs; else it keeps what fits."""
    from pipeline.preflight import budget_words
    wins = sorted((x["a"], x["z"], id(x)) for x in slots
                  if x.get("a") is not None and x.get("z") is not None)
    for s in slots:
        if s["role"] != "hold" or s.get("a") is None:
            continue
        a, z = s["a"], s["z"]
        want = max(HOLD_SEC[0], min(HOLD_SEC[1], z - a))
        nxt = min([w[0] for w in wins if w[2] != id(s) and w[0] >= a - 1e-6
                   and w[0] < a + want + 1e-6] or [a + want])
        prv = max([w[1] for w in wins if w[2] != id(s) and w[1] <= a + 1e-6]
                  or [a - want])
        z = min(a + want, nxt)
        if z - a < want:
            a = max(prv, z - want)
        if z - a < want - 1e-3:
            # still short (a beat of 3.6 s holding a line AND a hold): take
            # the rest from the START of the narrated window right after it,
            # if that window keeps the footage its shortest line needs - and
            # cap that line's words to what is left
            for n in slots:
                if (n is s or n.get("a") is None or abs(n["a"] - z) > 1e-3
                        or n["role"] in ("hold", "film_speaks", "intro")):
                    continue
                keep = max(MIN_WINDOW, _secs(n.get("min_words") or 3))
                take = min(want - (z - a), (n["z"] - n["a"]) - keep)
                if take > 0.05:
                    n["a"] = round(n["a"] + take, 3)
                    z += take
                    if n.get("max_words") is not None:
                        n["max_words"] = int(max(1, min(
                            n["max_words"], budget_words(n["z"] - n["a"]))))
                        n["min_words"] = int(min(n.get("min_words") or 1,
                                                 n["max_words"]))
                        if n.get("target") is not None:
                            n["target"] = min(n["target"], n["max_words"])
                    wins = [(n["a"], n["z"], id(n)) if w[2] == id(n) else w
                            for w in wins]
                break
        s["a"], s["z"] = round(a, 3), round(z, 3)
        s["hold"] = round(z - a, 2)
        wins = [(s["a"], s["z"], id(s)) if w[2] == id(s) else w
                for w in wins]


_SENT = re.compile(r"[A-Z\"'][^.?!]*[.?!]")


def whole_sentences(text: str) -> list:
    """The complete sentences in a transcript segment: a capital (or an
    opening quote) to a full stop, question or exclamation mark."""
    return [m.group(0).strip() for m in _SENT.finditer(str(text or ""))]


# One per EVAL reaction, in rotation - each is a pattern the judgment
# classifier hears (pipeline/pacing_gates._EVAL); the noun is the writer's.
EVAL_FORMS = (
    "\"That's the <noun> ...\"",
    "\"Nobody / No one + verb ...\"",
    "\"The whole <noun> ...\"",
    "\"..., which is why / how ...\"",
    "one judgement word: loyal / petty / cruel / generous / decent / brave / "
    "clever / pointless / cheap / odd",
    "\"Here's the <noun> ...\"",
    "\"Everyone / Everything + verb ...\"",
    "\"The only <noun> ...\"",
    "\"the best / the worst <noun> ...\" or \"the most / the least + word\"",
    "\"The problem / mistake / trick / truth / joke / cost / difference ...\"",
    "\"..., and that's <word>\"",
)


def markers(text: str, skip_quotes: bool = False) -> int:
    """[VOICE-PRESENCE]'s own count: I / you / stance adverbs / questions.
    skip_quotes: leave out words inside double quotation marks - a quoted
    character saying "you" or asking a question is not the narrator, and
    the per-slot rules must not make a verbatim quote unfixable."""
    from pipeline import craft_gates as CG
    t = str(text or "")
    if skip_quotes:
        t = re.sub(r"[\"\u201c][^\"\u201d]*[\"\u201d]", " ", t)
    return sum(len(rx.findall(t)) for rx in CG._VOICE_SHARED.values())


def _voice_budget(slots: list) -> None:
    """[VOICE-PRESENCE] has a floor AND a ceiling on narrator markers per
    minute, and [PERSONA] needs every reaction heard. So the reactions are
    split: VOICE reactions carry one marker (you / I / a question / a stance
    adverb), EVAL reactions a verdict with none ("that's the...", "nobody...")
    - as many VOICE ones as put the draft at the middle of the band, spread
    evenly. The intro, the outro and the fixed quotes are counted first."""
    from pipeline import craft_gates as CG
    wpm = float(getattr(config, "TTS_WORDS_PER_MINUTE", 186) or 186)
    gap = float(getattr(config, "GAP_BETWEEN_LINES", 0.18) or 0.18)
    nar = [x for x in slots if x["role"] not in ("hold", "film_speaks")]
    if not nar:
        return
    words = sum(int(x.get("target") or 0) for x in nar)
    mins = words / wpm + gap * len(nar) / 60.0
    aim = (CG.BAR_VOICE_PER_MIN_MIN + CG.BAR_VOICE_PER_MIN_MAX) / 2.0
    fixed = (sum(markers(x.get("quote")) for x in nar if x["role"] == "quote")
             + 2 * sum(1 for x in nar if x["role"] == "intro")
             + sum(1 for x in nar if x["role"] == "outro"))
    reac = [x for x in nar if x["role"] == "reaction"]
    n_voice = max(0, min(len(reac), int(round(aim * mins)) - fixed))
    for x in reac:
        x["voice"] = "eval"
    if n_voice:
        step = len(reac) / n_voice
        for i in range(n_voice):
            reac[int(i * step)]["voice"] = "voice"
    # [TIC-REPETITION]: four acts written in parallel each reached for the
    # first form in the list ("that's the price" x3). Each EVAL reaction is
    # handed its own form, in rotation, so the draft varies by construction.
    ev = [x for x in reac if x["voice"] == "eval"]
    for i, x in enumerate(ev):
        x["form"] = EVAL_FORMS[i % len(EVAL_FORMS)]


def _first_of_beat(narr: list, i: int):
    j = i
    while j > 0 and narr[j - 1]["beat"] == narr[i]["beat"]:
        j -= 1
    return narr[j]


# --------------------------------------------------------------------------- #
# what the writer is told
# --------------------------------------------------------------------------- #
ROLE_TEXT_STORY = {
    "action": "tell what happens here - who does what, and why or with what "
              "result; a short reaction of your own may follow when it "
              "helps",
    "quote": "the transcript line is the payoff: quote it VERBATIM inside "
             "DOUBLE QUOTATION MARKS, attributed to its speaker",
    "bridge": "carry the story across this beat in one plain line: what "
              "changed, and why",
    "outro": "the closing thought on the whole story, then the call to "
             "action",
}

ROLE_TEXT = {
    "open": "the cold open - the film's own charged scene told in-media-res; "
            "sentence 1 a concrete situation or image (NO greeting, NO meta "
            "word like recap/film, NO title, year or director, at most ONE "
            "proper name across the whole open); the LAST open slot ENDS on "
            "the unanswered question the video exists to answer (payload "
            "loop)",
    "action": "the moment itself - what happens and what it costs; not "
              "commentary (payload stake / reasoning / rest, never judgment)",
    "quote": "quote the transcript line VERBATIM inside the narration, "
             "INSIDE DOUBLE QUOTATION MARKS, attributed to its speaker",
    "reaction": "the narrator's reaction to what just happened - an opinion, "
                "an aside, a deadpan remark (payload judgment)",
    "bridge": "one line that carries the story across this beat (the "
              "compressed beats are where the dwelt-on ones get their room)",
    "intro": "the film-intro block, AFTER the cold open, spoken over the "
             "brand block (no footage): the GREETING slot says who you are "
             "and names the film and its year; the FACTS slot gives the "
             "director, 2-4 leads WITH their roles, and one production fact "
             "- only what film_facts.json states, nothing it withholds "
             "(delivery intro)",
    "outro": "the last line: first what the ending MEANS (a thesis, its own "
             "sentence), then a call to action (subscribe / tell me what to "
             "recap next) - at least two sentences, the CTA never first "
             "(delivery outro)",
}


def _band_top(s: dict) -> int:
    """The band's own ceiling (intro / outro slots carry theirs)."""
    return {"intro": INTRO_WORDS[1], "outro": OUTRO_WORDS[1]}.get(
        s["band"], BANDS.get(s["band"], (0, s["max_words"]))[1])


def slots_for_act(slots: list, k: int) -> list:
    return [s for s in slots if s["act"] == k]


def slots_text(slots: list) -> str:
    rows = []
    for s in slots:
        if s["role"] in ("hold", "film_speaks"):
            rows.append(f"- {s['slot']} {s['beat']} {s['role'].upper()} "
                        f"{s['clip_start']}-{s['clip_end']} (written by code "
                        f"- do not reply for it)")
            continue
        if s["role"] == "open" and story_mode():
            rows.append(
                f"- {s['slot']} HOOK {s['clip_start']}-{s['clip_end']} | up "
                f"to {s['max_words']} words"
                + (" | the last hook line: end on a question or a plain "
                   "statement, whichever the scene earns"
                   if s.get("open_hook") else ""))
            continue
        if s["role"] == "open":
            rows.append(
                f"- {s['slot']} OPEN ({s.get('lever')} / OPEN-"
                f"{s.get('open_mode')}) {s['clip_start']}-{s['clip_end']} | "
                f"{s['min_words']}-{s['max_words']} words, aim {s['target']}"
                + ((" | CLOSE ON THE "
                    + ("QUESTION: end on the hook question, unanswered"
                       if s.get("closing") != "stake" else
                       "STAKE: state the cost, withhold the outcome, no "
                       "question mark"))
                   if s.get("open_hook") else "")
                + (" | mid-scene: open ON the action, no time or place "
                   "anchor" if s.get("pivot") else ""))
            continue
        if s["role"] == "intro":
            rows.append(f"- {s['slot']} INTRO ({s.get('intro_part')}) no "
                        f"window - over the opening credits | "
                        f"{s['min_words']}-{s['max_words']} words, aim "
                        f"{s['target']}")
            continue
        band = ((f"up to {s['max_words']} words (what the footage holds)"
                 if s.get("band") == "free" else
                 f"{s['band']} {s['min_words']}-{s['max_words']} words, aim "
                 f"{s['target']}")
                + (" (one sentence of 20+ words, then one of <= 5)"
                   if s.get("shape") == "punch" else
                   " (one sentence of 30+ words)" if s.get("shape") == "sweep"
                   else ""))
        rows.append(
            f"- {s['slot']} {s['beat']} {s['role'].upper()}"
            + (f" ({s['voice'].upper()})" if s.get("voice") else "")
            + (f" FORM {s['form']}" if s.get("form") else "")
            + (" SAD-OK" if s.get("sad_ok") else "")
            + f" {s['clip_start']}-{s['clip_end']} | {band}"
            + (f" | {skip_note(s)}" if s.get("after_skip") else "")
            + (" | OPENS THE STORY: begin with a time or a place (\"Los "
               "Angeles.\", \"Three years earlier, ...\")"
               if s.get("transition") else "")
            + (" | OPENS A LOOP (payload loop)" if s.get("opens_loop") else "")
            + (f" | QUOTE: \"{s['quote']}\"" if s.get("quote") else "")
            + (f" | MUST SAY (a story point - name who): {s['must_say']}"
               if s.get("must_say") else ""))
    return "\n".join(rows)


STORY_RULES = """\
# HOW TO TELL IT (story mode - the owner's rules, from a human recap that
# viewers follow on ONE hearing)
1. Every line says WHO does WHAT, and WHY or WITH WHAT RESULT - for someone
   who has never seen the film. Name the person; use "he" / "she" only when
   nobody else in the scene could be meant.
2. Connect events by cause: "so", "because", "but", "to (do X)", "only
   to", "it turns out". "Then" and "Meanwhile" are fine links, but they are
   never ENOUGH across something important you skipped: say what happened.
3. When something important CHANGES HANDS - an object, an alliance, a
   secret, who is winning - say it in one plain sentence ("Jakande's men
   take the laptop with God's Eye on it."). A slot marked MUST SAY carries
   one of these story points: say it on THAT line, naming who.
4. Tell the WHOLE story: every event the plot needs, in order. In an action
   scene, say what CHANGES the story (who is hurt, who holds what, who
   escapes); pure spectacle can play without words.
5. Paraphrase dialogue. Quote only a line that is itself the payoff.
6. A reaction of your own is welcome WHEN it helps - the kind of thing a
   friend watching with you would say: concrete, often funny, understood on
   one hearing ("That is not how casts work. But it is how Hobbs works.").
   No more than about one line in five. NO aphorisms or riddles: nothing
   the listener has to decode ("the ledger turns out to have a heart",
   "That's the real heist"). No "That's the ..." / "Here's the ..." lines.
7. Write names that cannot be heard as ordinary words in full ("Mr.
   Nobody", never a bare "Nobody").

# WHAT THE READERS CHECK AFTER YOU - avoid it while writing (the cold read
# and the reviewer flag exactly these; every finding costs a fix round)
8. Never refer to something as already known ("the deal", "that promise",
   "his partner") unless an EARLIER line of yours introduced it.
9. No pronoun with two possible owners: if two people were just named,
   name the one you mean. Same for outcomes - say plainly whether someone
   died, won, lost, gave or took.
10. No claim about habit or repetition ("always", "keeps", "never once",
   "the whole film") unless the transcript shows it more than once.
11. Do not reuse the same phrase or the same opener in nearby lines.

# HOW IT SOUNDS (story guide section 3 - the delivery matters as much as
# the facts)
12. Fold the last event into the next sentence ("Hearing the guards
   coming, she ..."; "Now that the police have his name, he ..."); give an
   action its goal and its obstacle ("to stop her, only to watch the train
   pull out"); let one sentence carry actions that belong together; put the
   feeling inside the story line ("she begs", "he realises", "luckily")
   instead of a separate comment; at a reveal, put the surprise last.
   These are tools, not a template - three lines opening the same way
   sound like a machine.
13. One line may run across slots IN A ROW (two or more) when they tell
   ONE chain of actions. Reply with ONE line: "slot" = the first slot, "join"
   = the slot ids in order, and a '|' in the narration where each next
   slot's footage begins ("So they turn her into the ball in a game of
   keep-away, | passing her from car to car while Dom goes after Shaw.").
   Each piece stays within its own slot's words and tells what that
   slot's footage shows. Never join across a HOLD, a skip, the open, the
   intro or the outro.

BAD -> GOOD (from our own past drafts):
- "Mr. Nobody, who took a bullet meant for all of them, still holds the
  leash on God's Eye."  (wrong, and a riddle)
  -> "In the chaos, Jakande's men take the laptop with God's Eye on it."
- "By then, Hobbs walks in."  (the climax happened off the page)
  -> "Dom drives his Charger up the crumbling garage, launches it at the
  helicopter, and throws a bag of grenades inside in mid-air."
- "The cost of the film, said by the one who forgot, is what stings."
  -> "For two movies she couldn't remember marrying him. The memory comes
  back at the exact moment she's about to lose him."
"""


def _story_brief(pdir: Path, plan: dict, k: int) -> str:
    """The writer brief in story mode: the mechanics the code needs (one
    line per slot, labels, claims) plus STORY_RULES. Nothing here asks for
    a proportion of asides, loops or sentence shapes."""
    from pipeline import angle_spec
    from pipeline import craft_gates as CG
    from pipeline import pacing_gates as PG
    try:
        per = angle_spec.load(Path(pdir)).get("persona") or {}
    except Exception:
        per = {}
    budget = next((a.get("word_budget") for a in plan.get("acts") or []
                   if str(a.get("act")) == str(k)), None)
    jargon = PG._JARGON.pattern.replace("\\b", "").replace("(?:", "(")
    never = "\n".join(f"  - {m}" for m in (per.get("never") or [])[:6])
    return "\n".join([
        "# WRITER BRIEF",
        f"- Word budget for this act: about {budget} words. Each slot says "
        f"how many words its footage holds; use fewer when the story needs "
        f"fewer.",
        "- ONE reply line per slot, in slot order, with `slot` set to its "
        "id. Do not add, drop, merge or reorder slots. You write the words, "
        "`delivery`, `payload` and an optional `claim`; code sets the id, "
        "the beat (`note`), the clip window and the holds.",
        "- Roles: " + "; ".join(f"{r.upper()} = {t}" for r, t in
                                ROLE_TEXT_STORY.items()),
        f"- `payload` is one of {', '.join(CG.PAYLOAD_KINDS)} - label each "
        f"line honestly: `judgment` for your own reaction, `loop` for a "
        f"promise of what comes next, otherwise stake / reasoning / rest.",
        f"- Never editing/camera jargon ({jargon}).",
        f"- `delivery` is one of {', '.join(sorted(config.TTS_DELIVERY))}; "
        f"no `hook` - the hook and the title are already written "
        f"(title: {plan.get('title')!r}).",
        "- A line whose evidence is speech carries "
        '"claim": {"type": "speech", "subject": "<the speaker>"}.',
        _open_brief(plan, k),
        _intro_brief(pdir, plan, k),
        BRIDGE_RULE,
        "- delivery `sad` only on slots marked SAD-OK (real loss or grief).",
        STORY_RULES,
        "- NARRATOR (angle.md):" + (f" {per.get('stance')}" if
                                     per.get("stance") else " plain, warm"),
        "- The narrator never:", never or "  - (none listed)",
    ])


def writer_brief(pdir: Path, plan: dict, k: int) -> str:
    """The rules a writer must meet, generated from the constants the gates
    read - so the brief and the gates cannot say different things."""
    if story_mode():
        return _story_brief(pdir, plan, k)
    from pipeline import angle_spec
    from pipeline import craft_gates as CG
    from pipeline import pacing_gates as PG
    try:
        per = angle_spec.load(Path(pdir)).get("persona") or {}
    except Exception:
        per = {}
    budget = next((a.get("word_budget") for a in plan.get("acts") or []
                   if str(a.get("act")) == str(k)), None)
    jargon = PG._JARGON.pattern.replace("\\b", "").replace("(?:", "(")
    moves = "\n".join(f"  - {m}" for m in (per.get("moves") or [])[:6])
    never = "\n".join(f"  - {m}" for m in (per.get("never") or [])[:6])
    return "\n".join([
        "# WRITER BRIEF (generated from the gates' own thresholds)",
        f"- Word budget for this act: {budget} words. Stay inside your "
        f"slots' bands; together they are the budget.",
        "- ONE reply line per slot, in slot order, with `slot` set to its "
        "id. Do not add, drop, merge or reorder slots. You write the words, "
        "`delivery`, `payload` and an optional `claim`; code sets the id, "
        "the beat (`note`), the clip window and the holds.",
        "- Roles: " + "; ".join(f"{r.upper()} = {t}" for r, t in
                                ROLE_TEXT.items()),
        f"- `payload` is one of {', '.join(CG.PAYLOAD_KINDS)}; `rest` on at "
        f"most {CG.BAR_REST_SHARE:.0%} of lines, never {CG.BAR_REST_RUN} in "
        f"a row; a slot marked OPENS A LOOP carries `loop`.",
        f"- Judgment lines: {config.PERSONA_JUDGMENT_SHARE_MIN:.0%}-"
        f"{config.PERSONA_JUDGMENT_SHARE_MAX:.0%} of lines, never more than "
        f"{config.PERSONA_JUDGMENT_RUN_MAX} in a row; at a peak at most "
        f"{config.PERSONA_PEAK_REACTION_MAX} reaction.",
        f"- At most {config.PERSONA_FRAME_ONLY_SHARE_MAX:.0%} of lines may "
        f"only report what is on screen - say what it MEANS.",
        f"- Never editing/camera jargon (the gate's list: {jargon}).",
        f"- `delivery` is one of {', '.join(sorted(config.TTS_DELIVERY))}; "
        f"no `hook` - the hook and the title are already written "
        f"(title: {plan.get('title')!r}).",
        "- A line whose evidence is speech carries "
        '"claim": {"type": "speech", "subject": "<the speaker>"}; claim.type '
        "is never a shot tag such as aftermath / establishing / montage.",
        _open_brief(plan, k),
        _intro_brief(pdir, plan, k),
        BRIDGE_RULE,
        "- delivery `sad` only on slots marked SAD-OK (real loss or grief); "
        "everywhere else it becomes normal - a tense scene is `tense`, a "
        "setback is not sad.",
        "- REACTION (VOICE) slots: the narrator speaks - exactly ONE of: "
        "I / I'm, you / your, a question to the viewer, or honestly / "
        "frankly / of course / apparently / somehow / obviously / "
        "naturally / turns out (NOT me / my / clearly - the checker does not "
        "hear those).",
        "- REACTION (EVAL) slots: a verdict with NONE of those words, built "
        "on one of THESE exact forms (the checker hears only these): "
        "\"That's the ...\" / \"Here's the ...\"; \"the whole / the only / "
        "the point / the problem / the mistake / the trick / the truth / the "
        "joke / the cost / the price / the difference ...\" (with THE); "
        "\"Nobody / No one / Everyone / Nothing / Everything + verb\"; "
        "\"... which is why / how / what ...\"; \"... and that's ...\"; "
        "\"the most / the least + word\"; \"the best / the worst ...\"; or one of: "
        "loyal, petty, cruel, ridiculous, generous, brave, clever, decent, "
        "pointless, cheap, odd, stupid, honest.",
        "- Every OTHER slot (action, quote framing, bridge) uses none of the "
        "VOICE words and no question mark - the narrator's presence is "
        "budgeted to the VOICE slots so it lands, not chatters. On an ANCHOR "
        "beat no other slot passes judgement either: the moment lands "
        "before the opinion of it, once.",
        "- NARRATOR PERSONA (angle.md):" + (f" {per.get('stance')}" if
                                            per.get("stance") else ""),
        moves or "  - (none listed)",
        "- The persona never:", never or "  - (none listed)",
    ])


def _facts(pdir: Path) -> dict:
    try:
        return json.loads((Path(pdir) / "film_facts.json").read_text(
            encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def _open_brief(plan: dict, k: int) -> str:
    """R3/R4 for the act that carries the OPEN slots: the cold open's
    sentence contract and the film's genre lever, generated from the
    picker's own choice so the brief and the gates cannot disagree. The
    closing SHAPE comes from the rotation - a question this video, a
    stated stake the next - never the same twice running."""
    opens = [s for s in plan.get("slots") or []
             if s.get("role") == "open" and s.get("act") == k]
    if not opens:
        return "- No OPEN slots in this act."
    lever, mode = opens[0].get("lever") or "THRILL", opens[0].get(
        "open_mode") or "A"
    closing = opens[-1].get("closing") or "question"
    if story_mode():
        # owner, 18 Nov: a short HOOK on an early scene, then the intro as
        # usual (greeting, title + year, director, cast), then the story.
        # No lever words, no question/stake rotation, no one-name rule.
        return "\n".join([
            f"- HOOK ({len(opens)} line(s), the OPEN slots, on the film's own "
            f"EARLY scene): give a viewer a reason to stay. Choose what THIS "
            f"scene really offers - what the moment MEANS for the people in "
            f"it, something STRANGE in it, or the QUESTION it raises.",
            "- Concrete and specific to this film: name the people with their "
            "role, and say where (and when) we are within the first two "
            "lines. It may end on a question or on a plain statement, "
            "whichever the scene earns.",
            "- Never a cliche (\"the truth was closer than anyone could "
            "imagine\", \"nothing would ever be the same\", \"you won't "
            "believe\"), never a hint at the twist or the ending, no "
            "greeting or channel name - the intro slots that follow do that.",
        ])
    lever_text = {
        "FEAR": "an ORDINARY detail done wrong (the clocks were striking "
                "thirteen); never name the monster in the open; death only "
                "as something happening, never itemised",
        "DESIRE": "a re-loaded proximity or a charged habit (after six "
                  "years, she saw him again), one concrete body-adjacent "
                  "image; desire spoken must be paid for visually in the "
                  "next line",
        "THRILL": "ONE of: a number that matters (a countdown, a streak, a "
                  "threshold), a debt coming due, a clock already running "
                  "- consequence first, cause withheld",
        "AWE": "scale through one impossible concrete image or reveal-verb; "
               "motion enters mid-fall or mid-chase",
        "PLAY": "a dare, a party or an embarrassment already in motion; "
                "the joke sets up, the stakes land dry - never explain "
                "the funny",
        "DRAMA": "the cost is personal and uncounted - a face, a "
                 "silence, a decision half-made; the stakes are "
                 "relational (who forgives, who stays), never a number",
    }.get(lever, "")
    closing_text = {
        "question": "the LAST open slot ENDS on the unanswered question "
                    "(it reads as the viewer's own question)",
        "stake": "the LAST open slot STATES the stake and stops - one "
                 "plain declarative sentence, the cost named, the outcome "
                 "withheld, NO question mark anywhere in the open",
    }[closing]
    return "\n".join([
        f"- COLD OPEN (OPEN-{mode}, lever {lever}, {len(opens)} line(s), "
        f"closes on a {closing}): present tense, third person, on the "
        f"film's own scene. Sentence 1: a concrete situation or image - "
        f"never backstory, never why. {lever_text}",
        "- Escalate in one straight line across the open; at most ONE "
        "proper name in the whole open; " + closing_text + ".",
    ] + (["- OPEN-B fragment: open mid-scene, no time-or-place anchor; the "
          "pivot line (\"But to understand how we got here...\") is the "
          "story's, not the open's."] if mode == "B" else []),
    )


def _intro_brief(pdir: Path, plan: dict, k: int) -> str:
    """The film-intro facts, for the act that carries the INTRO slots."""
    if not any(s.get("role") == "intro" and s.get("act") == k
               for s in plan.get("slots") or []):
        return "- No INTRO slots in this act."
    f = _facts(pdir)
    leads = [c for c in f.get("cast") or [] if c.get("lead")][:4]
    bans = sorted({str(t) for w in f.get("withheld") or []
                   for t in w.get("ban") or []})
    return "\n".join([
        f"- INTRO GREETING: open with \"This is {config.CHANNEL_NAME}\", "
        f"name the film - {f.get('title')!r} - and its year {f.get('year')}.",
        f"- INTRO FACTS: the director {f.get('director')!r}; 2-4 of these "
        f"leads WITH their roles: "
        + "; ".join(f"{c.get('actor')} as {c.get('role')}" for c in leads)
        + (f"; its place in the franchise: {f.get('franchise_position')}"
           if f.get("franchise_position") else "")
        + "; one of these facts: "
        + " | ".join(str(x.get("text")) for x in (f.get("facts") or [])[:6]),
        "- The intro says NOTHING that is not in those two bullets"
        + (f", and never these (withheld - they give a reveal away): "
           + ", ".join(bans) if bans else "") + ".",
    ])


# --------------------------------------------------------------------------- #
# the reply, against its slots
# --------------------------------------------------------------------------- #
def line_deviations(ln: dict, s: dict) -> list:
    """How ONE line misses its slot; [] = it fits. The same rules hold when
    the line is first written (check_slots) and whenever it is later
    rewritten (write_api resolve) - a fix may not undo the construction."""
    from pipeline import craft_gates as CG
    from pipeline import pacing_gates as PG
    out = []
    if s.get("role") in ("hold", "film_speaks") or s.get("min_words") is None:
        return out                 # code writes these; nothing to deviate from
    n = _wc(ln.get("narration"))
    parts = ln.get("parts") if len(ln.get("parts") or []) > 1 else None
    if parts:
        if parts_intact(ln):
            for p_ in parts:
                pn, mx = _wc(p_.get("text")), int(p_.get("max_words") or 0)
                if mx and pn > mx + TOL:
                    out.append(f"{p_['slot']} ({p_['beat']} joined): {pn} "
                               f"words, the slot is {p_.get('min_words')}-"
                               f"{mx} (its footage holds no more)")
        else:
            cap = sum(int(p_.get("max_words") or 0) for p_ in parts)
            if cap and n > cap + TOL:
                out.append(f"{s['slot']} ({s['beat']} joined over "
                           f"{len(parts)} slots): {n} words, the slots hold "
                           f"{cap}")
    elif not s["min_words"] - TOL <= n <= s["max_words"] + (
            TOL if s["max_words"] == _band_top(s) else 0):
        out.append(f"{s['slot']} ({s['beat']} {s['role']}): {n} words, "
                   f"the slot is {s['min_words']}-{s['max_words']}"
                   + (" (its footage holds no more)"
                      if s["max_words"] < _band_top(s) else ""))
    # payload labels for loop / reaction / action are set by CODE in
    # merge(); what code cannot set is whether the WORDS are heard as
    # the narrator - the same classifier [PERSONA] and [PEAK-ORDER] use
    text = str(ln.get("narration") or "")
    heard, why = PG.classify_judgment(text)
    mk = markers(text, skip_quotes=True)
    if story_mode():
        heard = False      # no planned reaction; the ceilings cap asides
    if s["role"] == "reaction" and not heard and not story_mode():
        out.append(f"{s['slot']} ({s['beat']} REACTION): not heard as the "
                   f"narrator - use one of the moves the brief lists for "
                   f"a {str(s.get('voice') or 'voice').upper()} reaction")
    if s["role"] == "reaction" and s.get("voice") == "voice" and mk > 2:
        out.append(f"{s['slot']} (VOICE): {mk} narrator markers - one")
    if s["role"] == "reaction" and s.get("voice") == "eval" and mk:
        out.append(f"{s['slot']} (EVAL): uses I / you / a question / a "
                   f"stance adverb ({mk}) - a verdict without them")
    if s["role"] in ("open", "action", "bridge") and mk \
            and not story_mode() \
            and not (s["role"] == "open" and s.get("open_hook")):
        # the open_hook slot's trailing question is the HOOK itself, not
        # a narrator marker - R3 requires it, the marker budget cannot
        # forbid it
        out.append(f"{s['slot']} ({s['role'].upper()}): uses I / you / a "
                   f"question / a stance adverb - those are budgeted to "
                   f"the VOICE slots")
    if s["role"] == "open" and s.get("open_hook") and not story_mode():
        # the closing shape ROTATES (a question this video, a stated
        # stake the next) - whichever this slot carries, the words must
        # match it, or the rotation is decorative
        if s.get("closing") == "stake" and text.strip().endswith("?"):
            out.append(f"{s['slot']} (OPEN, stake close): ends on a "
                       f"question mark - this video's close STATES the "
                       f"stake (one plain sentence, outcome withheld)")
        elif s.get("closing") != "stake" \
                and not text.strip().endswith("?"):
            out.append(f"{s['slot']} (OPEN, question close): must END on "
                       f"the unanswered question - got "
                       f"{text.strip()[-45:]!r}")
    if s["role"] == "open" and s.get("pivot") \
            and CG._ANCHOR.match(text.strip()):
        out.append(f"{s['slot']} (OPEN-B): opens on a time or place anchor - "
                   f"the fragment opens mid-scene; save the anchor for the "
                   f"story's own first line")
    if (s["anchor"] or s["peak"]) and s["role"] in ("action", "quote",
                                                     "bridge") and heard:
        out.append(f"{s['slot']} ({s['beat']} {s['role'].upper()} on an "
                   f"anchor): reads as commentary ({why}) - the moment "
                   f"lands first and the beat's one REACTION slot reacts; "
                   f"drop that word here"
                   + (" (a quote goes inside double quotation marks - the "
                      "checker does not read words inside them)"
                      if s["role"] == "quote" else ""))
    if s.get("after_skip") and DAY_PHRASE.search(text) and \
            not s.get("skip_time_ok", True):
        out.append(f"{s['slot']} comes after a skip where the beat map shows "
                   f"no change of time - "
                   f"\"{DAY_PHRASE.search(text).group(0)}\" says a night or "
                   f"days passed; open on the place, the skipped event, or "
                   f"\"Later,\" / \"Meanwhile,\"")
    if s.get("after_skip") and END_PHRASE.search(text) and \
            not s.get("skip_end_ok", True):
        out.append(f"{s['slot']}: \"{END_PHRASE.search(text).group(0)}\" "
                   f"opens a seam in the middle of the story - it is for the "
                   f"ending")
    if s.get("after_skip"):
        from pipeline.draft import crosses_skip
        if not crosses_skip(text):
            out.append(f"{s['slot']} comes {skip_note(s)} - open on what "
                       f"changed: a place, the skipped event in a clause, "
                       f"\"Meanwhile,\", or a time phrase the skipped beats "
                       f"support")
    if s.get("transition") and not CG._ANCHOR.match(text.strip()):
        out.append(f"{s['slot']} opens the story: begin with a time or a "
                   f"place - got {text.strip()[:40]!r}")
    if s["role"] == "outro":
        sents = CG._sentences(text)
        cta = [i for i, x in enumerate(sents) if CG._CTA.search(x)]
        if len(sents) < 2 or not cta or cta[0] == 0:
            out.append(f"{s['slot']} OUTRO: a thesis sentence first, then "
                       f"a call to action (subscribe / tell me what to "
                       f"recap next) - got {len(sents)} sentence(s), CTA "
                       f"{'first' if cta and cta[0] == 0 else 'present' if cta else 'missing'}")
    if s["role"] == "quote" and _norm(s.get("quote")) not in _norm(
            ln.get("narration")):
        out.append(f"{s['slot']}: the quote \"{s.get('quote')}\" is not "
                   f"in the line verbatim")
    # a story point must be HEARD as that event: the line names at least
    # one of its people (or the object) - "the enemy of my enemy" with no
    # name is not "Shaw teams up with Jakande"
    for p_ in (parts or [])[1:]:
        if p_.get("quote") and _norm(p_["quote"]) not in _norm(text):
            out.append(f"{p_['slot']}: the quote \"{p_['quote']}\" is not "
                       f"in the line verbatim")
    for keys in list(s.get("must_keys") or []) + [
            k_ for p_ in (parts or [])[1:] for k_ in p_.get("must_keys") or []]:
        low = text.lower()
        if not any(re.search(r"\b" + re.escape(k_.lower()) + r"\b", low)
                   for k_ in keys):
            out.append(f"{s['slot']} ({s['beat']}): must say "
                       f"\"{s.get('must_say')}\" - name "
                       f"{' / '.join(keys[:3])}")
            break
    return out


def slot_tag(s: dict) -> str:
    """The slot as a reviser needs to see it beside the line: role, the
    word band its footage holds, and the quote it must keep."""
    r = s["role"].upper()
    if s.get("voice"):
        r += f" {s['voice'].upper()}"
    if s.get("anchor") or s.get("peak"):
        r += " on an ANCHOR"
    if s.get("min_words") is not None and s["role"] != "hold":
        r += f", {s['min_words']}-{s['max_words']} words"
    if s.get("quote"):
        r += f", keep verbatim: \"{s['quote']}\""
    if s.get("must_say"):
        r += f"; must say: {s['must_say']}"
    if s.get("after_skip"):
        r += f"; {skip_note(s)}"
    return r


def _kind(msg: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"'.*?'|\".*?\"", "", msg))


def new_deviations(old: dict, new: dict, s: dict) -> list:
    """Deviations the rewrite has that the line before it did not (a line
    that already missed its band is not blocked for still missing it)."""
    had = {_kind(m) for m in line_deviations(old, s)}
    out = [m for m in line_deviations(new, s) if _kind(m) not in had]
    # a line already over its band may stay over - but may not GROW: the
    # footage set that band (Furious 7: a bridge opener took line 5 from
    # 13 to 15 words in a 3.7 s window and froze the picture)
    if s.get("max_words") is not None and s.get("role") not in (
            "hold", "film_speaks"):
        n_old, n_new = _wc(old.get("narration")), _wc(new.get("narration"))
        if n_new > s["max_words"] and n_new > n_old and not any(
                _length_only(m) for m in out):
            out.append(f"{s['slot']} ({s['beat']} {s['role']}): {n_new} "
                       f"words, the slot is {s['min_words']}-{s['max_words']}"
                       f" and the line had {n_old} - a fix may not make it "
                       f"longer than its footage")
    return out


def second_try(refused, key, still: list) -> bool:
    """May a rewrite that keeps its line's old fault be taken? Not the first
    time - it goes back, saying what is still wrong (a 'fix' that keeps the
    fault is not a fix). The SECOND time the same fault comes back, yes: the
    rewrite is no worse than the line, and refusing it for ever froze every
    OTHER fix to that line (Lost in the Stars line 103: three rounds removed
    a reviewer's unsupported claim, all refused because the slot still came
    after a skip; the finding never closed and the draft halted). The fault
    stays reported for the gates. `refused` is the caller's {key: kinds}
    across rounds; None = never take one (the old rule)."""
    if refused is None:
        return False
    kinds = {_kind(m) for m in still}
    if kinds <= set(refused.get(key) or ()):
        return True
    refused[key] = set(refused.get(key) or ()) | kinds
    return False


def merge_revision(prev: list, reply: list, slots: list, k: int,
                   allow_labels: bool = False,
                   refused: dict | None = None) -> tuple:
    """A revision of an act, applied SLOT BY SLOT onto the act it revises.
    A slot the reply leaves out keeps its line; a rewrite that adds a
    deviation from its slot (or keeps the line's own role fault) is not
    taken; a slot the act LOST is restored from the reply. Labels change
    only when allow_labels (a finding about labels). Returns (lines, notes).
    The first real film lost ~60 beats of act 2 when a whole-act rewrite,
    sent back for two draft-wide findings, replaced the act wholesale."""
    mine = [x for x in slots if x["act"] == k and x["role"] != "film_speaks"]
    carried = joined_slots(prev)
    act_all = [x for x in slots if x["act"] == k]
    by_prev = {str(l.get("slot") or ""): l for l in prev if l.get("slot")}
    by_new = {str(l.get("slot") or ""): l for l in reply if l.get("slot")}
    fresh = {str(l.get("slot")): l for l in merge(reply, slots, k)
             if l.get("slot")}
    fields = ("narration", "claim", "narration_silence_seconds") + (
        ("payload", "delivery") if allow_labels else ())
    out = [l for l in prev if not l.get("slot")]       # hook, unslotted intro
    notes, restored = [], []
    for s in mine:
        sid = s["slot"]
        if sid in carried:
            continue                 # the joined line before it carries it
        l = by_prev.get(sid)
        if l is None:
            if sid in fresh:
                # merge() numbers by position in the reply, so a restored
                # line can collide with a kept one (S001 restored as 1900
                # beside S002's 1900: resolve then edited both) - fresh id
                used = {x.get("id") for x in prev} | {x.get("id") for x in out}
                ln = dict(fresh[sid])
                if ln.get("id") in used:
                    ln["id"] = max([i for i in used if isinstance(i, int)]
                                   or [k * 1000]) + 1
                out.append(ln)
                restored.append(sid)
            elif s["role"] not in ("hold",):
                notes.append(f"{sid}: still missing (the reply did not "
                             f"write it either)")
            continue
        if sid not in by_new or s["role"] == "hold":
            out.append(l)
            continue
        rep = by_new[sid]
        if l.get("parts") or rep.get("join"):
            # v1: a revision keeps the join structure as it is - same
            # slots, a '|' per piece. Changing it would move lines between
            # slots, which a slot-by-slot merge cannot conserve.
            want_j = [p_["slot"] for p_ in l.get("parts") or []]
            got_j = [str(x) for x in rep.get("join") or []]
            if want_j != got_j:
                notes.append(f"{sid}: rewrite not taken - it would change "
                             f"the join ({want_j or 'none'} -> "
                             f"{got_j or 'none'})")
                out.append(l)
                continue
            rep2, jp = apply_join(rep, act_all)
            if jp:
                notes.append(f"{sid}: rewrite not taken - {jp[0]}")
                out.append(l)
                continue
            rep = rep2
        cand = {f: v for f, v in rep.items() if f in fields + ("parts",)}
        cand = code_labels(dict(l, **cand), s)
        broke = new_deviations(l, cand, s)
        still = unfixed_deviations(l, cand, s)
        if still and not broke and not second_try(refused, sid, still):
            broke = still
        if broke:
            notes.append(f"{sid}: rewrite not taken - {'; '.join(broke)}")
            out.append(l)
        else:
            if still:
                notes.append(f"{sid}: rewrite taken on the second try, "
                             f"still: {'; '.join(still)}")
            out.append(cand)
    if restored:
        notes.append(f"restored {len(restored)} line(s) the act had lost: "
                     f"{restored[:8]}")
    stray = [x for x in by_new if x not in {m["slot"] for m in mine}]
    if stray:
        notes.append(f"line(s) for no slot of this act ignored: {stray[:6]}")
    return out, notes


def _length_only(m: str) -> bool:
    return "words, the slot is" in m


def unfixed_deviations(old: dict, new: dict, s: dict) -> list:
    """A rewrite of a line that had a role deviation (not heard, reads as
    commentary, a marker it may not carry, a missing quote, an unbridged
    skip) should clear it: a 'fix' that keeps the fault is not a fix - the
    first time (second_try says when it is taken anyway). Length deviations
    may stay - the footage, not the writer, set that band."""
    had = {_kind(m) for m in line_deviations(old, s) if not _length_only(m)}
    return [m for m in line_deviations(new, s)
            if not _length_only(m) and _kind(m) in had]


def code_labels(new: dict, s: dict) -> dict:
    """The labels a slot decides are CODE's, not the writer's (nor a
    reviser's): delivery for intro / outro, payload for reaction / loop /
    outro, and no commentary label on an action or a quote."""
    new = dict(new)
    if s["role"] == "intro":
        new["delivery"], new["film_intro"] = "intro", True
        new["payload"] = new.get("payload") or "rest"
        return new
    if s["role"] == "open":
        if new.get("delivery") in ("intro", "outro", "hook"):
            new["delivery"] = "normal"
        elif new.get("delivery") == "sad" and not s.get("sad_ok"):
            new["delivery"] = "normal"   # sad is budgeted to grief anchors
        # the question slot is the loop the video answers; the rest of the
        # open is the moment, never commentary
        new["payload"] = "loop" if s.get("open_hook") else (
            "stake" if new.get("payload") == "judgment"
            else new.get("payload") or "stake")
        if s.get("open_hook") and s.get("hook_question"):
            new["hook_question"] = s["hook_question"]
        return new
    if s["role"] == "outro":
        new["delivery"] = "outro"
    elif new.get("delivery") in ("intro", "outro", "hook"):
        new["delivery"] = "normal"
    elif new.get("delivery") == "sad" and not s.get("sad_ok"):
        new["delivery"] = "normal"      # sad is budgeted to grief anchors
    if s["role"] in ("reaction", "outro"):
        new["payload"] = "judgment"
    elif s.get("opens_loop"):
        new["payload"] = "loop"
    elif s["role"] in ("action", "quote") and new.get("payload") == "judgment" \
            and not story_mode():
        new["payload"] = "stake"
    return new


def check_slots(lines: list, slots: list, pdir: Path | None = None) -> list:
    """Deviations of a reply from its slots; [] = it followed them."""
    from pipeline import craft_gates as CG
    from pipeline import pacing_gates as PG
    want = [s for s in slots if s["role"] not in ("hold", "film_speaks")]
    by = {}
    out = []
    joined = []
    for ln in lines:
        if isinstance(ln, dict) and ln.get("join"):
            ln2, jp = apply_join(ln, slots)
            out += jp
            joined.append(ln2)
        else:
            joined.append(ln)
    lines = joined
    consumed = joined_slots(lines)
    for ln in lines:
        sid = str(ln.get("slot") or "")
        if not sid and (ln.get("film_intro") or ln.get("over_montage")
                        or ln.get("delivery") == "hook"):
            continue          # the hook (code's, from the plan) / old intro
        if sid in by:
            out.append(f"slot {sid} answered twice")
        by[sid] = ln
    ids = {s["slot"] for s in want}
    codes = {s["slot"] for s in slots if s["role"] in ("hold", "film_speaks")}
    extra = [x for x in by if x not in ids and x not in codes]  # holds: code's
    if extra:
        out.append(f"line(s) for no slot of yours: {extra[:8]} - one line per "
                   f"slot, `slot` set to its id")
    twice = [x for x in consumed if x in by]
    if twice:
        out.append(f"slot(s) {sorted(twice)[:6]} said twice: inside a joined "
                   f"line and on their own")
    for s in want:
        if s["slot"] in consumed:
            continue                 # carried by the joined line before it
        ln = by.get(s["slot"])
        if ln is None:
            out.append(f"{s['slot']} ({s['beat']} {s['role']}): no line")
            continue
        out += line_deviations(ln, s)
    # sequence rules read the labels as they will be SAVED (code_labels),
    # not as the writer sent them
    out += _act_problems([code_labels(by[s["slot"]], s) for s in want
                          if s["slot"] in by and s["slot"] not in consumed],
                         [s for s in want if s["slot"] in by
                          and s["slot"] not in consumed], pdir)
    intro = [by.get(s["slot"]) for s in want if s["role"] == "intro"]
    if intro and pdir is not None:
        out += _intro_problems(" ".join(str((x or {}).get("narration") or "")
                                        for x in intro), pdir)
    open_lines = [by.get(s["slot"]) for s in want if s["role"] == "open"]
    if open_lines:
        out += _open_problems([x for x in open_lines if x], pdir)
    return out


# R0's open rules live in craft_gates ([OPEN] reads them too) - one
# source, both places, so the write-time check and the final gate
# cannot drift.
from pipeline.craft_gates import _open_banned_hits, _open_proper_names  # noqa: E402


def _open_problems(lines: list, pdir: Path | None) -> list:
    """R0 on the cold open: no greeting, no meta framing, no title / year /
    director, and at most ONE proper name across the whole open - a cold
    open full of names is a listings entry, not a hook."""
    out = []
    blob = " ".join(str(ln.get("narration") or "") for ln in lines)
    low = blob.lower()
    for t in _open_banned_hits(blob):
        out.append(f"OPEN: says {t!r} - the cold open has no greeting, "
                   f"no meta framing, no credits; it is the film's own "
                   f"moment")
    year = ""
    f = _facts(pdir) if pdir is not None else {}
    if f:
        year = str(f.get("year") or "")
        title = str(f.get("title") or "").split(":")[-1].strip().lower()
        for w in [w for w in re.findall(r"[a-z']+", title) if len(w) > 3]:
            if w in low and w not in ("the", "and"):
                out.append(f"OPEN: says the title word {w!r} - the title "
                           f"lives in the video title, not the voice")
                break
    if year and re.search(r"(?<!\d)" + re.escape(year) + r"(?!\d)", low):
        out.append(f"OPEN: says the year {year} - a time anchor may be the "
                   f"film's OWN time (\"In 2035\"), not its release year")
    # proper names: the film's KNOWN names - the SAME exact check the
    # final gate runs (_open_proper_names, one function both places)
    if pdir is not None:
        used, _exact = _open_proper_names(blob, Path(pdir))
        if len(used) > 1:
            out.append(f"OPEN: names {len(used)} characters "
                       f"({', '.join(used[:4])}) - at most ONE proper name "
                       f"survives a cold open")
    return out


def _act_problems(lines: list, slots: list, pdir=None) -> list:
    """Sequence rules no single slot can see: [ACTION-STAKE] (4 action /
    tense lines in a row need one that restates the stake) and
    [TIC-REPETITION] (a 3-word phrase twice in the act, outside quotes)."""
    from pipeline import craft_gates as CG
    out, run, gap = [], [], 0
    every = int(CG.BAR_ACTION_STAKE_EVERY)
    for ln, s in zip(lines, slots):
        if ln.get("delivery") in CG._ACTION_DELIVERY:
            gap = 0 if str(ln.get("payload")) in ("stake", "reasoning") \
                else gap + 1
            if s["role"] not in ("reaction", "outro", "intro") \
                    and not s.get("opens_loop"):
                run.append(s["slot"])        # slots whose payload is free
            if gap >= every:
                out.append(f"{', '.join(run[-every:]) or 'these lines'}: "
                           f"{every} action/tense lines with no stake - make "
                           f"one of them say what is at stake (payload stake)")
                gap = 0
        else:
            run, gap = [], 0
    # the gate's OWN counting (motif_gates): n-grams with enough content
    # words, names excluded, once per line
    from pipeline import motif_gates as MG
    names = MG.tic_names(Path(pdir), [str(x.get("narration") or "")
                                      for x in lines]) \
        if pdir is not None else set()
    seen: dict = {}
    for ln, s in zip(lines, slots):
        for ph in sorted(MG.tic_phrases(ln.get("narration") or "", names)):
            seen.setdefault(ph, []).append(s["slot"])
    for g, where in seen.items():
        if len(where) > int(getattr(config, "TIC_NGRAM_MAX", 1)):
            out.append(f"{', '.join(where)}: \"{g}\" in {len(where)} lines - "
                       f"vary it (a repeated phrase is a tic)")
    return out


def _intro_problems(blob: str, pdir: Path) -> list:
    """[FILM-INTRO]'s required elements and bans, on the INTRO slots."""
    f = _facts(pdir)
    if not f:
        return []
    low = blob.lower()
    out = []
    if str(config.CHANNEL_NAME).lower() not in low:
        out.append(f"INTRO: the greeting never says {config.CHANNEL_NAME!r}")
    need = {"title": str(f.get("title", "")).split(":")[-1].strip(),
            "year": str(f.get("year", "")),
            "director": str(f.get("director", ""))}
    from pipeline.craft_gates import fact_stated
    for k_, v in need.items():
        if v and not fact_stated(k_, v, low):
            out.append(f"INTRO: never states the {k_} ({v!r})")
    named = [c for c in f.get("cast") or []
             if str(c.get("actor", "")).lower() in low]
    if not 2 <= len(named) <= 4:
        out.append(f"INTRO: names {len(named)} cast member(s); 2-4 leads "
                   f"with their roles")
    for w in f.get("withheld") or []:
        for t in w.get("ban") or []:
            if re.search(r"\b" + re.escape(str(t).lower()) + r"\b", low):
                out.append(f"INTRO: says {t!r}, which film_facts.json "
                           f"withholds ({w.get('reveal', '?')})")
    return out


# --------------------------------------------------------------------------- #
# JOINED SLOTS (owner, 17-18 Nov): one sentence may run across 2+ adjacent
# slots - "So they turn Ramsey into the ball in a game of keep-away, |
# passing her from car to car ..." - with a '|' where each next slot's
# footage begins. The saved line keeps `parts` (each piece, its slot, window
# and caps), so every later check reads the caps per piece, and the voice
# stage and render can switch the picture when the voice reaches each piece.
# --------------------------------------------------------------------------- #
# owner, 18 Nov: as many slots as ONE chain of actions runs over - 3 was
# an arbitrary cap. 8 is only a technical ceiling: a longer run is a whole
# scene, told better as several lines.
JOIN_MAX = 8
JOIN_GAP = 0.6           # seconds: joined footage must be continuous
NO_JOIN = ("hold", "film_speaks", "open", "intro", "outro")


def apply_join(ln: dict, act_slots: list) -> tuple:
    """(line, problems). A reply line with `join` becomes ONE line over its
    slots: narration without the '|', the window of all of them, `parts`.
    A join that is not allowed comes back as a plain line on its own slot
    (the '|' removed) with the reason - one fix round, like any deviation."""
    j = ln.get("join")
    if not j:
        return ln, []
    sid = str(ln.get("slot") or "")
    narr = str(ln.get("narration") or "")
    chunks = [c.strip() for c in narr.split("|")]
    jl = [str(x) for x in j] if isinstance(j, list) else []

    def bad(why):
        clean = {f: v for f, v in ln.items() if f not in ("join", "parts")}
        clean["narration"] = " ".join(c for c in chunks if c)
        return clean, [f"{sid}: join {jl} not allowed - {why}"]
    order = [x for x in act_slots]
    idx = {x["slot"]: i for i, x in enumerate(order)}
    if not 2 <= len(jl) <= JOIN_MAX or len(set(jl)) != len(jl):
        return bad(f"join 2-{JOIN_MAX} different slots")
    if jl[0] != sid:
        return bad("the join starts at the line's own slot")
    if any(x not in idx for x in jl):
        return bad("a slot that is not in this act")
    ii = [idx[x] for x in jl]
    if ii != list(range(ii[0], ii[0] + len(jl))):
        return bad("the slots are not next to each other (a hold or another "
                   "slot sits between them)")
    ss = [order[i] for i in ii]
    if any(x["role"] in NO_JOIN for x in ss):
        return bad("open, intro, outro, hold and film-speaks slots are "
                   "never joined")
    if any(x.get("after_skip") or x.get("transition") for x in ss[1:]):
        return bad(f"{next(x['slot'] for x in ss[1:] if x.get('after_skip') or x.get('transition'))} "
                   f"starts after a skip - the story jumps there, so it "
                   f"keeps its own line")
    for a_, b_ in zip(ss, ss[1:]):
        if abs(_pt(b_["clip_start"]) - _pt(a_["clip_end"])) > JOIN_GAP:
            return bad(f"{a_['slot']} and {b_['slot']} are not continuous "
                       f"footage")
    if len(chunks) != len(jl) or not all(chunks):
        return bad(f"put exactly {len(jl) - 1} '|' in the narration, where "
                   f"each next slot's footage begins")
    parts = []
    for x, c in zip(ss, chunks):
        p_ = {"slot": x["slot"], "beat": x["beat"],
              "clip_start": x["clip_start"], "clip_end": x["clip_end"],
              "text": c, "min_words": x.get("min_words"),
              "max_words": x.get("max_words")}
        if x.get("quote"):
            p_["quote"] = x["quote"]
        if x.get("must_keys"):
            p_["must_keys"], p_["must_say"] = x["must_keys"], x.get("must_say")
        parts.append(p_)
    out = {f: v for f, v in ln.items() if f != "join"}
    out.update(narration=" ".join(chunks), parts=parts,
               clip_start=ss[0]["clip_start"], clip_end=ss[-1]["clip_end"])
    return out, []


def joined_slots(lines: list) -> set:
    """The slots a joined line carries beyond its own (they have no line of
    their own, and that is conserved, not lost)."""
    return {str(p.get("slot")) for ln in lines if isinstance(ln, dict)
            for p in (ln.get("parts") or [])[1:] if p.get("slot")}


def parts_intact(ln: dict) -> bool:
    """True while the narration is still exactly its pieces (a later rewrite
    without '|' leaves the parts stale: the render then splits evenly)."""
    ps = ln.get("parts") or []
    return len(ps) > 1 and _norm(" ".join(str(p.get("text") or "")
                                          for p in ps)) == _norm(
        ln.get("narration"))


def merge(lines: list, slots: list, k: int) -> list:
    """The act file's lines: each reply line on its slot's beat and window,
    the holds written by code. Film-intro lines (no slot) keep their place
    at the front."""
    act = [x for x in slots if x["act"] == k]
    lines = [apply_join(ln, act)[0] if isinstance(ln, dict) else ln
             for ln in lines]
    consumed = joined_slots(lines)
    by = {str(ln.get("slot") or ""): ln for ln in lines}
    has_intro = any(s["role"] == "intro" and s["act"] == k for s in slots)
    # a writer's own unslotted intro lines are dropped when the act has
    # INTRO slots - the block would otherwise be said twice
    out = [] if has_intro else [dict(ln) for ln in lines if not ln.get("slot")
                                and ln.get("film_intro")]
    i = 0
    for s in slots:
        if s["act"] != k or s["role"] == "film_speaks":
            continue
        i += 1
        if s["role"] == "intro":
            ln = by.get(s["slot"])
            if ln is None:
                continue
            new = {f: v for f, v in ln.items()
                   if f not in ("id", "note", "clip_start", "clip_end", "slot",
                                "over_montage")}
            out.append(dict(code_labels(new, s), id=k * 1000 + i,
                            note="INTRO", slot=s["slot"]))
            continue
        base = {"id": k * 1000 + i, "note": s["beat"], "slot": s["slot"],
                "clip_start": s["clip_start"], "clip_end": s["clip_end"]}
        if s["role"] == "hold":
            out.append(dict(base, narration="", delivery="normal",
                            payload="rest",
                            narration_silence_seconds=s["hold"]))
            continue
        if s["slot"] in consumed:
            continue               # said inside the joined line before it
        ln = by.get(s["slot"])
        if ln is None:
            continue
        new = {f: v for f, v in ln.items()
               if f not in ("id", "note", "clip_start", "clip_end", "slot",
                            "film_intro", "over_montage")}
        if ln.get("parts"):
            base = dict(base, clip_start=ln["clip_start"],
                        clip_end=ln["clip_end"])
        out.append(dict(base, **code_labels(new, s)))
    for j, ln in enumerate(out):
        if ln.get("film_intro"):
            ln["id"] = k * 1000 + 900 + j
    return out
