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
     (action | quote | reaction | bridge | hold | film_speaks), a length band
     (short / medium / long, drawn so [RHYTHM]'s SD, long-sentence and punch
     bars land in band), whether it opens a loop ([LOOP-CADENCE]), and for a
     quote slot the transcript line to quote verbatim. Anchors run action ->
     quote -> ... -> one reaction ([PEAK-ORDER], [PERSONA] anchor ending);
     a reaction slot lands at least every PERSONA_WINDOW_SEC of film
     ([PERSONA] window); a loop opens at least every BAR_LOOP_GAP lines.
  3. CODE assigns every clip window: inside the slot's beat, from the
     catalogue's moments, never overlapping ([WINDOW-OVERLAP]), never across
     a reveal's landing ([REVEAL-TIMING]), sized to config.WINDOW_SPAN_RATIO
     of the band's narration, and capped so the band fits the render's
     capacity (preflight.budget_words). Holds are code's too. Black / text
     cards are moved afterwards by write_plan.fix_unwatchable.
  4. The act request carries the slots and a WRITER BRIEF generated from the
     same constants the gates read (writer_brief), so they cannot drift.
  5. check_slots() compares a reply to its slots at once; the deviations go
     back ONCE inside the stage. The gates stay the final check.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import config

ROLES = ("action", "quote", "reaction", "bridge", "hold", "film_speaks")
# words per line for each band. The bars they serve (craft_gates):
#   SD of words-per-line >= BAR_SD (9): short ~5, medium ~14, long ~28 in
#   the 30/45/25 mix below give an SD of ~9.5 before any within-band spread.
#   A `long` slot alternates two shapes: PUNCH (a >= 20-word sentence, then
#   one of <= 5 words - BAR_PUNCH_SHARE) and SWEEP (one sentence of >= 30
#   words - BAR_LONG_SHARE, kept far under BAR_LONG_SHARE_MAX).
BANDS = {"short": (3, 7), "medium": (11, 18), "long": (24, 38)}
BAND_CYCLE = ("medium", "short", "long", "medium", "short", "medium",
              "long", "medium", "short", "long", "medium", "medium")
QUOTE_WORDS = (3, 16)            # a transcript line short enough to quote
HOLD_SEC = (2.5, 5.0)            # a planned hold (>= craft_gates.BAR_SILENCE_MIN)
TOL = 2                          # words either side of a band before it is a deviation
MIN_WINDOW = 1.5                 # seconds; a narrower slot window is not bindable


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
    return " ".join(re.sub(r"[^\w' ]+", " ", str(s or "").lower()).split())


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
    """[(start, end, text)] - transcript segments act_payload.py trusts."""
    p = pdir / "transcript.json"
    if not p.exists():
        return []
    try:
        segs = json.loads(p.read_text(encoding="utf-8-sig")).get("segments") or []
    except ValueError:
        return []
    return [(float(s["start"]), float(s["end"]), str(s.get("text") or "").strip())
            for s in segs if isinstance(s.get("start"), (int, float))
            and float(s["end"]) - float(s["start"]) <= 30.0
            and str(s.get("text") or "").strip()]


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
    # quotes: the transcript line inside the slot's own window (or its beat)
    used_q = set()
    for s in slots:
        if s["role"] != "quote":
            continue
        lo, hi = rng[s["beat"]]
        c = [x for x in segs if s["a"] <= x[0] < s["z"]
             and QUOTE_WORDS[0] <= _wc(x[2]) <= QUOTE_WORDS[1]] or \
            [x for x in segs if lo <= x[0] < hi
             and QUOTE_WORDS[0] <= _wc(x[2]) <= QUOTE_WORDS[1]]
        c = [x for x in c if x[2] not in used_q]
        if c:
            q = max(c, key=lambda x: (_wc(x[2]) <= 10, _wc(x[2])))
            s["quote"] = q[2]
            used_q.add(q[2])
        else:
            s["role"] = "action"
    narrated = [s for s in slots if s["role"] not in ("hold", "film_speaks")]
    # [PERSONA] window: the gate walks PERSONA_WINDOW_SEC windows from the
    # first line and flags one holding >= 3 lines with no narrator presence
    # (peak beats exempt). The same walk here turns the window's last bridge
    # (else its last non-anchor action) into a reaction.
    w = float(config.PERSONA_WINDOW_SEC)
    if narrated:
        t0 = _pt(narrated[0]["clip_start"]) if "clip_start" in narrated[0] \
            else narrated[0]["a"]
        t = t0
        end = narrated[-1]["a"]
        while t <= end:
            inside = [x for x in narrated if t <= x["a"] < t + w]
            if len(inside) >= 3 and not any(
                    x["role"] == "reaction" or x["peak"] for x in inside):
                c = [x for x in inside if x["role"] == "bridge"] or \
                    [x for x in inside if x["role"] == "action"
                     and not x["anchor"]]
                if c:
                    c[-1]["role"] = "reaction"
            t += w
    # [LOOP-CADENCE]: a loop at least every BAR_LOOP_GAP lines - planned at
    # BAR_LOOP_GAP - 2, preferring a beat's last line (a promise of the next)
    gap = max(3, int(CG.BAR_LOOP_GAP) - 2)
    since = 0
    for i, s in enumerate(narrated):
        since += 1
        s["opens_loop"] = False
        nxt_new = i + 1 >= len(narrated) or narrated[i + 1]["beat"] != s["beat"]
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
    for i, s in enumerate(narrated):
        band = BAND_CYCLE[i % len(BAND_CYCLE)]
        cap = budget_words(s["z"] - s["a"])
        if band == "long" and (s["role"] in ("quote", "reaction")
                               or cap < BANDS["long"][0]):
            debt += 1
            band = "medium"
        elif band != "long" and debt and s["role"] not in (
                "quote", "reaction") and cap >= BANDS["long"][0]:
            debt -= 1
            band = "long"
        if s["role"] == "quote" and band == "short":
            band = "medium"
        while band != "short" and cap < BANDS[band][0]:
            band = {"long": "medium", "medium": "short"}[band]
        s["band"] = band
        s["max_words"] = int(min(BANDS[band][1], cap))
        s["min_words"] = int(min(BANDS[band][0], s["max_words"]))
        # an aim inside the band, alternating low / high, so the act's
        # words-per-line SD lands over [RHYTHM]'s bar by construction
        lo_, hi_ = s["min_words"], s["max_words"]
        s["target"] = int(round(lo_ + (hi_ - lo_) * (0.2 if i % 2 else 0.85)))
        if band == "long":
            long_n += 1
            s["shape"] = "sweep" if long_n % 3 == 0 else "punch"
        want = s["a"] + ratio * _secs(s["max_words"])
        if want < s["z"] - 0.05:
            s["z"] = round(max(want, s["a"] + MIN_WINDOW), 3)
        if s["z"] - s["a"] < MIN_WINDOW:
            problems.append(f"{s['beat']}: a {s['role']} slot has only "
                            f"{s['z'] - s['a']:.1f}s of footage")
    for s in slots:
        if s["role"] == "hold":
            s["hold"] = round(max(HOLD_SEC[0], min(HOLD_SEC[1],
                                                   s["z"] - s["a"])), 2)
            s["z"] = round(s["a"] + s["hold"], 3)
    # ids, and the windows as timestamps; no two windows overlap by
    # construction (contiguous splits of disjoint beats, only ever trimmed)
    for i, s in enumerate(slots, 1):
        s["slot"] = f"S{i:03d}"
        s["clip_start"], s["clip_end"] = _ts(s.pop("a")), _ts(s.pop("z"))
    return {"slots": slots, "problems": problems}


def _first_of_beat(narr: list, i: int):
    j = i
    while j > 0 and narr[j - 1]["beat"] == narr[i]["beat"]:
        j -= 1
    return narr[j]


# --------------------------------------------------------------------------- #
# what the writer is told
# --------------------------------------------------------------------------- #
ROLE_TEXT = {
    "action": "the moment itself - what happens and what it costs; not "
              "commentary (payload stake / reasoning / rest, never judgment)",
    "quote": "quote the transcript line VERBATIM inside the narration, "
             "attributed to its speaker",
    "reaction": "the narrator's reaction to what just happened - an opinion, "
                "an aside, a deadpan remark (payload judgment)",
    "bridge": "one line that carries the story across this beat (the "
              "compressed beats are where the dwelt-on ones get their room)",
}


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
        band = (f"{s['band']} {s['min_words']}-{s['max_words']} words, aim "
                f"{s['target']}"
                + (" (one sentence of 20+ words, then one of <= 5)"
                   if s.get("shape") == "punch" else
                   " (one sentence of 30+ words)" if s.get("shape") == "sweep"
                   else ""))
        rows.append(
            f"- {s['slot']} {s['beat']} {s['role'].upper()} "
            f"{s['clip_start']}-{s['clip_end']} | {band}"
            + (" | OPENS A LOOP (payload loop)" if s.get("opens_loop") else "")
            + (f" | QUOTE: \"{s['quote']}\"" if s.get("quote") else ""))
    return "\n".join(rows)


def writer_brief(pdir: Path, plan: dict, k: int) -> str:
    """The rules a writer must meet, generated from the constants the gates
    read - so the brief and the gates cannot say different things."""
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
        "- NARRATOR PERSONA (angle.md):" + (f" {per.get('stance')}" if
                                            per.get("stance") else ""),
        moves or "  - (none listed)",
        "- The persona never:", never or "  - (none listed)",
    ])


# --------------------------------------------------------------------------- #
# the reply, against its slots
# --------------------------------------------------------------------------- #
def check_slots(lines: list, slots: list) -> list:
    """Deviations of a reply from its slots; [] = it followed them."""
    want = [s for s in slots if s["role"] not in ("hold", "film_speaks")]
    by = {}
    out = []
    for ln in lines:
        sid = str(ln.get("slot") or "")
        if not sid and ln.get("film_intro"):
            continue
        if sid in by:
            out.append(f"slot {sid} answered twice")
        by[sid] = ln
    ids = {s["slot"] for s in want}
    extra = [x for x in by if x not in ids]
    if extra:
        out.append(f"line(s) for no slot of yours: {extra[:8]} - one line per "
                   f"slot, `slot` set to its id")
    for s in want:
        ln = by.get(s["slot"])
        if ln is None:
            out.append(f"{s['slot']} ({s['beat']} {s['role']}): no line")
            continue
        n = _wc(ln.get("narration"))
        if not s["min_words"] - TOL <= n <= s["max_words"] + (
                TOL if s["max_words"] == BANDS[s["band"]][1] else 0):
            out.append(f"{s['slot']} ({s['beat']} {s['role']}): {n} words, "
                       f"the slot is {s['min_words']}-{s['max_words']}"
                       + (" (its footage holds no more)"
                          if s["max_words"] < BANDS[s["band"]][1] else ""))
        pl = ln.get("payload")
        if s.get("opens_loop") and pl != "loop":
            out.append(f"{s['slot']}: opens a loop - payload must be loop, "
                       f"got {pl!r}")
        if s["role"] == "reaction" and pl != "judgment":
            out.append(f"{s['slot']}: a REACTION slot - payload judgment, "
                       f"got {pl!r}")
        if s["role"] == "action" and pl == "judgment":
            out.append(f"{s['slot']}: an ACTION slot is the moment, not "
                       f"commentary - not payload judgment")
        if s["role"] == "quote" and _norm(s.get("quote")) not in _norm(
                ln.get("narration")):
            out.append(f"{s['slot']}: the quote \"{s.get('quote')}\" is not "
                       f"in the line verbatim")
    return out


def merge(lines: list, slots: list, k: int) -> list:
    """The act file's lines: each reply line on its slot's beat and window,
    the holds written by code. Film-intro lines (no slot) keep their place
    at the front."""
    by = {str(ln.get("slot") or ""): ln for ln in lines}
    out = [dict(ln) for ln in lines if not ln.get("slot") and ln.get("film_intro")]
    i = 0
    for s in slots:
        if s["act"] != k or s["role"] == "film_speaks":
            continue
        i += 1
        base = {"id": k * 1000 + i, "note": s["beat"], "slot": s["slot"],
                "clip_start": s["clip_start"], "clip_end": s["clip_end"]}
        if s["role"] == "hold":
            out.append(dict(base, narration="", delivery="normal",
                            payload="rest",
                            narration_silence_seconds=s["hold"]))
            continue
        ln = by.get(s["slot"])
        if ln is None:
            continue
        new = {f: v for f, v in ln.items()
               if f not in ("id", "note", "clip_start", "clip_end", "slot")}
        out.append(dict(base, **new))
    for j, ln in enumerate(out):
        if ln.get("film_intro"):
            ln["id"] = k * 1000 + 900 + j
    return out
