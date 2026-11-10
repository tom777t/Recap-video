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

ROLES = ("intro", "action", "quote", "reaction", "bridge", "outro", "hold",
         "film_speaks")
# Bumped whenever derive_slots changes what it builds: a plan.json whose slots
# carry an older version is re-derived (write_api.cmd_draft), so a fix here
# reaches a project that already has a plan without re-buying the plan.
SLOTS_VERSION = 7
# [INTRO-OUTRO] / [FILM-INTRO]: the draft opens with the channel greeting and
# the film's facts, and closes on a thesis then a call to action. These are
# slots too - the first real film came back with no <intro> line at all.
INTRO_WORDS = (12, 40)
OUTRO_WORDS = (20, 45)
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
BANDS = {"short": (3, 7), "medium": (11, 18), "long": (24, 38)}
BAND_CYCLE = ("medium", "short", "long", "medium", "short", "medium",
              "long", "medium", "short", "long", "medium", "medium")
QUOTE_WORDS = (3, 16)            # a transcript line short enough to quote
HOLD_SEC = (2.5, 5.0)            # a planned hold (>= craft_gates.BAR_SILENCE_MIN)
TOL = 2                          # words either side of a band before it is a deviation
REACTION_MIN_WORDS = 9           # a reaction slot whose footage holds fewer is a bridge
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
    # the INTRO block: the channel greeting, then the film's facts - act 1,
    # straight after the hook, no clip window (over the credits)
    if order:
        k1 = order[0][0]
        slots = [{"slot": "", "act": k1, "beat": "INTRO", "role": "intro",
                  "intro_part": part, "anchor": False, "peak": False,
                  "a": None, "z": None} for part in ("greeting", "facts")] \
            + slots
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
    # [TRANSITION]: the first story line comes straight off the montage and
    # the credits - it opens on a time or a place, and is never a reaction
    if narrated:
        narrated[0]["transition"] = True
        if narrated[0]["role"] == "reaction":
            narrated[0]["role"] = "bridge"
    # [PERSONA] window: the gate walks PERSONA_WINDOW_SEC windows from the
    # first line and flags one holding >= 3 lines with no narrator presence
    # (peak beats exempt). The same walk here turns the window's last bridge
    # (else its last non-anchor action) into a reaction.
    w = float(config.PERSONA_WINDOW_SEC)
    # the walk sees the outro too (the gate does), but never converts it
    walk = narrated + [x for x in slots if x["role"] == "outro"]
    if narrated:
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
    if have < want:
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
    for s in slots:
        if s["role"] == "hold":
            s["hold"] = round(max(HOLD_SEC[0], min(HOLD_SEC[1],
                                                   s["z"] - s["a"])), 2)
            s["z"] = round(s["a"] + s["hold"], 3)
    # ids, and the windows as timestamps; no two windows overlap by
    # construction (contiguous splits of disjoint beats, only ever trimmed)
    for i, s in enumerate(slots, 1):
        s["slot"] = f"S{i:03d}"
        a_, z_ = s.pop("a"), s.pop("z")
        s["clip_start"] = _ts(a_) if a_ is not None else None
        s["clip_end"] = _ts(z_) if z_ is not None else None
    return {"slots": slots, "problems": problems,
            "version": SLOTS_VERSION}


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
ROLE_TEXT = {
    "action": "the moment itself - what happens and what it costs; not "
              "commentary (payload stake / reasoning / rest, never judgment)",
    "quote": "quote the transcript line VERBATIM inside the narration, "
             "INSIDE DOUBLE QUOTATION MARKS, attributed to its speaker",
    "reaction": "the narrator's reaction to what just happened - an opinion, "
                "an aside, a deadpan remark (payload judgment)",
    "bridge": "one line that carries the story across this beat (the "
              "compressed beats are where the dwelt-on ones get their room)",
    "intro": "the film-intro block, spoken over the opening credits (no "
             "footage): the GREETING slot says who you are and names the "
             "film and its year; the FACTS slot gives the director, 2-4 leads "
             "WITH their roles, and one production fact - only what "
             "film_facts.json states, nothing it withholds (delivery intro)",
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
        if s["role"] == "intro":
            rows.append(f"- {s['slot']} INTRO ({s.get('intro_part')}) no "
                        f"window - over the opening credits | "
                        f"{s['min_words']}-{s['max_words']} words, aim "
                        f"{s['target']}")
            continue
        band = (f"{s['band']} {s['min_words']}-{s['max_words']} words, aim "
                f"{s['target']}"
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
            + (" | OPENS THE STORY: begin with a time or a place (\"Los "
               "Angeles.\", \"Three years earlier, ...\")"
               if s.get("transition") else "")
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
        _intro_brief(pdir, plan, k),
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
    if not s["min_words"] - TOL <= n <= s["max_words"] + (
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
    if s["role"] == "reaction" and not heard:
        out.append(f"{s['slot']} ({s['beat']} REACTION): not heard as the "
                   f"narrator - use one of the moves the brief lists for "
                   f"a {str(s.get('voice') or 'voice').upper()} reaction")
    if s["role"] == "reaction" and s.get("voice") == "voice" and mk > 2:
        out.append(f"{s['slot']} (VOICE): {mk} narrator markers - one")
    if s["role"] == "reaction" and s.get("voice") == "eval" and mk:
        out.append(f"{s['slot']} (EVAL): uses I / you / a question / a "
                   f"stance adverb ({mk}) - a verdict without them")
    if s["role"] in ("action", "bridge") and mk:
        out.append(f"{s['slot']} ({s['role'].upper()}): uses I / you / a "
                   f"question / a stance adverb - those are budgeted to "
                   f"the VOICE slots")
    if (s["anchor"] or s["peak"]) and s["role"] in ("action", "quote",
                                                     "bridge") and heard:
        out.append(f"{s['slot']} ({s['beat']} {s['role'].upper()} on an "
                   f"anchor): reads as commentary ({why}) - the moment "
                   f"lands first and the beat's one REACTION slot reacts; "
                   f"drop that word here"
                   + (" (a quote goes inside double quotation marks - the "
                      "checker does not read words inside them)"
                      if s["role"] == "quote" else ""))
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
    return r


def _kind(msg: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"'.*?'|\".*?\"", "", msg))


def new_deviations(old: dict, new: dict, s: dict) -> list:
    """Deviations the rewrite has that the line before it did not (a line
    that already missed its band is not blocked for still missing it)."""
    had = {_kind(m) for m in line_deviations(old, s)}
    return [m for m in line_deviations(new, s) if _kind(m) not in had]


def merge_revision(prev: list, reply: list, slots: list, k: int,
                   allow_labels: bool = False) -> tuple:
    """A revision of an act, applied SLOT BY SLOT onto the act it revises.
    A slot the reply leaves out keeps its line; a rewrite that adds a
    deviation from its slot (or keeps the line's own role fault) is not
    taken; a slot the act LOST is restored from the reply. Labels change
    only when allow_labels (a finding about labels). Returns (lines, notes).
    The first real film lost ~60 beats of act 2 when a whole-act rewrite,
    sent back for two draft-wide findings, replaced the act wholesale."""
    mine = [x for x in slots if x["act"] == k and x["role"] != "film_speaks"]
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
        cand = {f: v for f, v in by_new[sid].items() if f in fields}
        cand = code_labels(dict(l, **cand), s)
        broke = new_deviations(l, cand, s) + unfixed_deviations(l, cand, s)
        if broke:
            notes.append(f"{sid}: rewrite not taken - {'; '.join(broke)}")
            out.append(l)
        else:
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
    commentary, a marker it may not carry, a missing quote) must clear it:
    a 'fix' that keeps the fault is not a fix. Length deviations may stay -
    the footage, not the writer, set that band."""
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
    elif s["role"] in ("action", "quote") and new.get("payload") == "judgment":
        new["payload"] = "stake"
    return new


def check_slots(lines: list, slots: list, pdir: Path | None = None) -> list:
    """Deviations of a reply from its slots; [] = it followed them."""
    from pipeline import craft_gates as CG
    from pipeline import pacing_gates as PG
    want = [s for s in slots if s["role"] not in ("hold", "film_speaks")]
    by = {}
    out = []
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
    for s in want:
        ln = by.get(s["slot"])
        if ln is None:
            out.append(f"{s['slot']} ({s['beat']} {s['role']}): no line")
            continue
        out += line_deviations(ln, s)
    # sequence rules read the labels as they will be SAVED (code_labels),
    # not as the writer sent them
    out += _act_problems([code_labels(by[s["slot"]], s) for s in want
                          if s["slot"] in by],
                         [s for s in want if s["slot"] in by], pdir)
    intro = [by.get(s["slot"]) for s in want if s["role"] == "intro"]
    if intro and pdir is not None:
        out += _intro_problems(" ".join(str((x or {}).get("narration") or "")
                                        for x in intro), pdir)
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
    n_ = int(getattr(config, "TIC_NGRAM_N", 3))
    floor = int(getattr(config, "TIC_MIN_CONTENT_WORDS", 2))
    names = MG._load_names(Path(pdir))[0] if pdir is not None else set()
    seen: dict = {}
    for ln, s in zip(lines, slots):
        here = set()
        for toks in MG._phrase_chunks(str(ln.get("narration") or "")):
            for i in range(max(0, len(toks) - n_ + 1)):
                g = toks[i:i + n_]
                if any(w in names for w in g) or MG._n_content(g) < floor:
                    continue
                ph = " ".join(g)
                if ph not in here:
                    here.add(ph)
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
    for k_, v in need.items():
        if v and v.lower() not in low:
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


def merge(lines: list, slots: list, k: int) -> list:
    """The act file's lines: each reply line on its slot's beat and window,
    the holds written by code. Film-intro lines (no slot) keep their place
    at the front."""
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
        ln = by.get(s["slot"])
        if ln is None:
            continue
        new = {f: v for f, v in ln.items()
               if f not in ("id", "note", "clip_start", "clip_end", "slot",
                            "film_intro", "over_montage")}
        out.append(dict(base, **code_labels(new, s)))
    for j, ln in enumerate(out):
        if ln.get("film_intro"):
            ln["id"] = k * 1000 + 900 + j
    return out
