# -*- coding: utf-8 -*-
"""write_plan.py - the two stages the agentic draft path did implicitly.

Used by tools/write_api.py (subcommands `plan`, `draft`, `resolve`).

WHY. The first real API run (furious72015) wrote 224 lines, ONE LINE PER BEAT
(53 single-line beats in a row), anchors at one line, the title still the
project id and a 19-word hook; then review_api filed 123 findings nothing
closed. The gates caught all of it. A subagent writing an act PLANS before it
writes - it decides which beats are bridges and which it dwells on - and it
ACTS ON the review. The API path did neither. So:

1. PLAN (one request, before any act): per beat 0 (drop or footage), 1
   (bridge) or 2-5 lines (an anchor gets dwell), holds after reveals, deaths
   and the climax, film_speaks spots, a word budget per act, the title and the
   hook. It is validated DETERMINISTICALLY before a single line is written,
   with the GATES' OWN CODE: a placeholder draft is built from the plan and
   run through pacing_gates.pacing_report (contour, one-line runs, anchor
   dwell), the hook/title rules are craft_gates' own patterns, the word band
   is the RUNTIME-BAND gate's formula. On failure ONE revision request gets
   the violations. Each act request then gets the plan for its beats, and
   check_plan_counts() verifies the act followed it.
2. RESOLVE: per act, the open cold-read / reviewer / ending-read findings and
   the open SAME-POINT pairs on its lines go to one request that returns the
   revised lines and, for EVERY finding, RESOLVED (what changed) or ANSWERED
   (a reason of >= REVIEW_ANSWER_MIN_WORDS words). This module writes those
   entries into the artifacts' review-findings blocks with the finding's own
   kind and ids (so they close it by review_artifacts' rule) and re-signs only
   the lines that changed.
3. UNWATCHABLE-FOOTAGE: a bound window on black or a text card is moved
   MECHANICALLY first - trimmed or shifted inside its beat, never onto
   another line's footage, a flagged shot or across a reveal's landing.

Nothing film-specific lives here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import config

LINES_MAX = 5


# --------------------------------------------------------------------------- #
# inputs
# --------------------------------------------------------------------------- #
def act_beats(project: str, tool) -> dict:
    """{act: [beat ids]} from act_payload.py's BEATS list - the same split
    the act writers are given."""
    from write_api import n_acts
    pdir = config.project_dir(project)
    out = {}
    for k in range(1, n_acts(pdir) + 1):
        txt = tool("act_payload.py", project, k)
        head = txt.split("AVAILABLE MACHINE MOMENTS")[0]
        out[k] = re.findall(r"^\s+(B\d{2,3})\s*\|", head, re.M)
    return out


def word_band(project: str) -> tuple:
    """(min_words, max_words) for the finished recap: the RUNTIME-BAND gate's
    formula (pipeline/draft.py) run backwards - minutes / measured
    render-over-draft factor x TTS_WORDS_PER_MINUTE, capped by the share
    guard. None, None when the film's length is unknown."""
    from pipeline.draft import _film_duration
    film = _film_duration(project)
    if not film:
        return None, None
    wpm = float(getattr(config, "TTS_WORDS_PER_MINUTE", 210) or 210)
    k = float(getattr(config, "RECAP_RUNTIME_RENDER_OVER_DRAFT", 1.0))
    mx = float(getattr(config, "RECAP_RUNTIME_MAX_MINUTES", 19.0))
    mn = float(getattr(config, "RECAP_RUNTIME_MIN_MINUTES", 14.0))
    phi = float(getattr(config, "RECAP_RUNTIME_PCT_HI", 20.0))
    top = min(mx, film / 60.0 * phi / 100.0)
    return int(mn / k * wpm), int(top / k * wpm)


def thresholds_text() -> str:
    from pipeline import craft_gates as CG
    return (
        "GATE THRESHOLDS (the draft is rejected if it misses any):\n"
        f"- every ANCHOR beat (angle.md ## ANCHORS) gets >= "
        f"{config.PACING_ANCHOR_MIN_LINES} narration lines\n"
        f"- the top 20% of beats by line count carry >= "
        f"{config.PACING_TOP20_LINE_SHARE_MIN:.0%} of all narration lines "
        f"(dwell on anchors, compress the rest)\n"
        f"- never more than {config.PACING_ONE_LINE_RUN_MAX} one-line beats in "
        f"a row; a beat held on footage (lines 0, footage true) breaks a run, "
        f"a dropped beat does not\n"
        f"- every beat in coverage_policy.json 'mandatory' gets >= 1 line\n"
        f"- a beat has 0-{LINES_MAX} lines\n"
        f"- the title is a PREMISE with a verb, never '<film> (<year>)'\n"
        f"- the hook opens with a sentence of <= {CG.BAR_HOOK_OPENER_WORDS} "
        f"words and names the question it raises (hook_question)\n")


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "hook": {"type": "object", "properties": {
            "narration": {"type": "string"},
            "hook_question": {"type": "string"}},
            "required": ["narration", "hook_question"],
            "additionalProperties": False},
        "acts": {"type": "array", "items": {"type": "object", "properties": {
            "act": {"type": "integer"}, "word_budget": {"type": "integer"}},
            "required": ["act", "word_budget"], "additionalProperties": False}},
        "beats": {"type": "array", "items": {"type": "object", "properties": {
            "beat": {"type": "string"},
            "lines": {"type": "integer"},
            "footage": {"type": "boolean"},
            "hold_after": {"type": "boolean"},
            "film_speaks": {"type": "boolean"},
            "why": {"type": "string"}},
            "required": ["beat", "lines", "footage", "hold_after",
                         "film_speaks", "why"],
            "additionalProperties": False}},
    },
    "required": ["title", "hook", "acts", "beats"],
    "additionalProperties": False,
}

# The plan request's system prompt is tools/plan_prompt.md.


def plan_user(project: str, pdir: Path, tool, read) -> str:
    lo, hi = word_band(project)
    ab = act_beats(project, tool)
    band = (f"WORD BAND for the whole recap: {lo}-{hi} words (the runtime "
            f"band x {getattr(config, 'TTS_WORDS_PER_MINUTE', 210)} WPM, "
            f"converted by the measured render factor)" if lo else
            "WORD BAND: unknown (no film length) - plan about 3200 words")
    acts = "\n".join(f"- act {k}: {', '.join(v)}" for k, v in ab.items())
    return "\n\n".join([
        thresholds_text(), band, "ACTS (the beats each act writer gets):\n"
        + acts,
        "# angle.md\n\n" + read(pdir / "angle.md"),
        "# coverage_policy.json\n\n" + read(pdir / "coverage_policy.json", True),
        "# beats_proposal.md\n\n" + read(pdir / "beats_proposal.md"),
        "# reveals.json\n\n" + read(pdir / "reveals.json", True)])


# --------------------------------------------------------------------------- #
# deterministic validation - the gates' own code
# --------------------------------------------------------------------------- #
def placeholder_draft(plan: dict) -> dict:
    """A draft with the plan's SHAPE: N placeholder lines per beat, a hold
    unit for a footage beat, nothing for a dropped one - exactly what the
    contour gate will later see of the real draft."""
    lines, i = [], 0
    for b in plan.get("beats") or []:
        n = int(b.get("lines") or 0)
        for _ in range(n):
            i += 1
            lines.append({"id": i, "note": b["beat"],
                          "narration": "placeholder words for the plan"})
        if n == 0 and b.get("footage"):
            i += 1
            lines.append({"id": i, "note": b["beat"], "narration": "",
                          "narration_silence_seconds": 2.0})
    return {"title": plan.get("title"), "lines": lines}


# --------------------------------------------------------------------------- #
# CONTOUR REPAIR - the plan's line COUNTS are arithmetic, so code makes them
# satisfy [PACING-CONTOUR]; the model only decides what matters (which beats
# are anchors, which are bridges). Two plan attempts on Furious 7 each missed
# one number (top-20% share 38.3% < 40%; a run of 5 one-line beats) and the
# stage stopped - a counting job the gate itself can do exactly.
#
# Moves, in order, each re-measured with the gate's own definitions:
#   1. every anchor gets PACING_ANCHOR_MIN_LINES (lines added to its biggest beat)
#   2. a run of one-line beats over the maximum is broken by holding one beat
#      that is NOT mandatory / anchor / promise on footage (a silent beat
#      breaks a run - config); if every beat in the run is mandatory, the
#      middle one gets a second line
#   3. while the top 20% share is under the floor (+ a small margin): one line
#      moves from the weakest non-top beat (a 2+ beat loses one; else a
#      non-mandatory 1-line beat goes to footage) to the strongest beat with
#      room, anchors first
# Mandatory beats never drop below 1 line, anchors never below the minimum,
# no beat goes above LINES_MAX. Every change is listed and printed.
# --------------------------------------------------------------------------- #
CONTOUR_SHARE_MARGIN = 0.02


def _contour_facts(pdir: Path) -> tuple:
    """(anchor groups [[beats]], protected beat set) from angle + coverage."""
    groups, protect = [], set()
    try:
        from pipeline import angle_spec
        spec = angle_spec.load(pdir)
        groups = [list(a["beats"]) for a in spec.get("anchors") or []]
        for pr in spec.get("promises") or []:
            protect.update(pr.get("beats") or [])
    except Exception:
        pass
    try:
        protect.update(json.loads((pdir / "coverage_policy.json").read_text(
            encoding="utf-8-sig")).get("mandatory") or [])
    except (OSError, ValueError):
        pass
    for g in groups:
        protect.update(g)
    return groups, protect


def _present(beats: list) -> list:
    """The beats the contour gate sees, in order (a dropped beat is absent)."""
    return [b for b in beats if int(b.get("lines") or 0) > 0 or b.get("footage")]


def _share_and_top(beats: list) -> tuple:
    t = _present(beats)
    if not t:
        return 1.0, set()
    k = max(1, round(len(t) * 0.20))
    top = sorted(t, key=lambda b: -int(b.get("lines") or 0))[:k]
    tot = sum(int(b.get("lines") or 0) for b in t) or 1
    return (sum(int(b.get("lines") or 0) for b in top) / tot,
            {id(b) for b in top})


def _worst_run(beats: list) -> list:
    best, run = [], []
    for b in _present(beats):
        if int(b.get("lines") or 0) == 1:
            run.append(b)
            if len(run) > len(best):
                best = list(run)
        else:
            run = []
    return best


def _mark(b: dict, what: str) -> None:
    b["why"] = (str(b.get("why") or "").rstrip() + f" [code: {what}]").strip()


def repair_contour(plan: dict, pdir: Path) -> list:
    """Make the plan's counts pass [PACING-CONTOUR] in place; return the
    changes as readable strings ([] = nothing needed)."""
    beats = plan.get("beats") or []
    if not beats:
        return []
    groups, protect = _contour_facts(pdir)
    by = {b.get("beat"): b for b in beats}
    anchor_beats = {x for g in groups for x in g}
    changes: list = []
    lmax = LINES_MAX

    def n(b):
        return int(b.get("lines") or 0)

    def setn(b, v, why):
        old = n(b)
        b["lines"] = v
        if v > 0:
            b["footage"] = False
        changes.append(f"{b['beat']}: {old} -> {v} line(s) ({why})")
        _mark(b, why)

    # 1. anchors dwell
    need = int(config.PACING_ANCHOR_MIN_LINES)
    for g in groups:
        bs = [by[x] for x in g if x in by]
        if not bs:
            continue
        while sum(n(b) for b in bs) < need:
            room = [b for b in bs if n(b) < lmax]
            if not room:
                break
            b = max(room, key=n)
            setn(b, n(b) + 1, "anchor dwell")

    run_max = int(config.PACING_ONE_LINE_RUN_MAX)
    floor = float(config.PACING_TOP20_LINE_SHARE_MIN) + CONTOUR_SHARE_MARGIN
    for _ in range(400):
        run = _worst_run(beats)
        if len(run) > run_max:
            mid = len(run) // 2
            order = sorted(range(len(run)), key=lambda i: abs(i - mid))
            free = [run[i] for i in order if run[i].get("beat") not in protect]
            if free:
                b = free[0]
                old = n(b)
                b["lines"], b["footage"] = 0, True
                changes.append(f"{b['beat']}: {old} -> 0, held on footage "
                               f"(breaks a run of {len(run)} one-line beats)")
                _mark(b, "footage, breaks a one-line run")
            else:
                setn(run[order[0]], 2, f"breaks a run of {len(run)} one-line "
                                       f"beats that are all mandatory")
            continue
        share, top = _share_and_top(beats)
        if share >= floor:
            break
        pres = _present(beats)
        rec = sorted([b for b in pres if id(b) in top and n(b) < lmax],
                     key=lambda b: (b.get("beat") not in anchor_beats, -n(b)))
        if not rec:
            rec = sorted([b for b in pres if n(b) < lmax and n(b) > 0],
                         key=lambda b: (b.get("beat") not in anchor_beats, -n(b)))
        if not rec:
            break
        donors2 = sorted([b for b in pres if id(b) not in top and n(b) >= 2
                          and b.get("beat") not in anchor_beats],
                         key=lambda b: n(b))
        donors1 = [b for b in pres if id(b) not in top and n(b) == 1
                   and b.get("beat") not in protect]
        r = rec[0]
        if donors2:
            d = donors2[0]
            setn(d, n(d) - 1, "line moved to an anchor")
        elif donors1:
            d = donors1[len(donors1) // 2]
            old = n(d)
            d["lines"], d["footage"] = 0, True
            changes.append(f"{d['beat']}: {old} -> 0, held on footage "
                           f"(its line moved to {r['beat']})")
            _mark(d, "footage, line moved to an anchor")
        setn(r, n(r) + 1, "top-20% share")
    return changes


_PLAN_GATE = ("anchor(s) are below", "anchor(s) are not in the draft",
              "contour is FLAT", "beats in a row get exactly one line")


def validate_plan(plan: dict, project: str, pdir: Path, ab: dict) -> list:
    """Violations, [] = the plan can be written to."""
    from pipeline import craft_gates as CG
    from pipeline import pacing_gates as PG
    v = []
    beats = plan.get("beats") or []
    ids = [b.get("beat") for b in beats]
    want = [b for k in sorted(ab) for b in ab[k]]
    miss = [b for b in want if b not in ids]
    extra = [b for b in ids if b not in want]
    if miss:
        v.append(f"beats missing from the plan: {miss[:12]}")
    if extra:
        v.append(f"beats not in the beat map: {extra[:12]}")
    if len(set(ids)) != len(ids):
        v.append("a beat appears twice")
    bad = [b.get("beat") for b in beats
           if not 0 <= int(b.get("lines") or 0) <= LINES_MAX]
    if bad:
        v.append(f"lines outside 0-{LINES_MAX}: {bad[:8]}")
    # the contour gate, run on the plan's shape
    rep = PG.pacing_report(placeholder_draft(plan), pdir)
    for e in rep.get("errors") or []:
        if any(s in e for s in _PLAN_GATE):
            v.append(e.split(". ")[0])
    # coverage
    try:
        mand = json.loads((pdir / "coverage_policy.json").read_text(
            encoding="utf-8-sig")).get("mandatory") or []
    except (OSError, ValueError):
        mand = []
    n_by = {b.get("beat"): int(b.get("lines") or 0) for b in beats}
    unc = [m for m in mand if n_by.get(m, 0) < 1]
    if unc:
        v.append(f"mandatory beat(s) with no line: {unc[:12]}")
    # words in band
    lo, hi = word_band(project)
    tot = sum(int(a.get("word_budget") or 0) for a in plan.get("acts") or [])
    if lo and not lo <= tot <= hi:
        v.append(f"act word budgets total {tot}, outside the band {lo}-{hi}")
    acts = {int(a.get("act")) for a in plan.get("acts") or []
            if str(a.get("act")).isdigit()}
    if acts != set(ab):
        v.append(f"word budgets for acts {sorted(acts)}, expected {sorted(ab)}")
    # title + hook: craft_gates' own rules
    title = str(plan.get("title") or "").strip()
    if not title or title.lower() == project.lower():
        v.append("the title is empty or the project id")
    elif CG._TITLE_YEAR.search(title):
        v.append(f"title {title!r} is '<film> (<year>)'")
    elif not (CG._TITLE_VERB.search(title) or CG._TITLE_EDING.search(title)):
        v.append(f"title {title!r} has no verb - it names, it does not claim")
    hook = plan.get("hook") or {}
    s = CG._sentences(str(hook.get("narration") or ""))
    if not s:
        v.append("no hook narration")
    elif CG._wc(s[0]) > CG.BAR_HOOK_OPENER_WORDS:
        v.append(f"the hook opens with {CG._wc(s[0])} words "
                 f"({CG.BAR_HOOK_OPENER_WORDS} max): {s[0]!r}")
    if len(str(hook.get("hook_question") or "").strip()) < 10:
        v.append("the hook names no hook_question")
    # holds after reveals: every reveal's landing beat
    try:
        from pipeline.draft import parse_reveal_map, beat_times
        bt = beat_times(project).get("ordered") or []
        for r in parse_reveal_map(project):
            land = r.get("land_sec")
            if land in (None, float("inf")):
                continue
            hit = [b for b, t in bt if t <= land + 1.0]
            if hit:
                lb = hit[-1]
                rec = next((b for b in beats if b.get("beat") == lb), None)
                nxt = beats[beats.index(rec) + 1] if rec and \
                    beats.index(rec) + 1 < len(beats) else None
                if rec and not rec.get("hold_after") and not (
                        nxt and nxt.get("footage")):
                    v.append(f"no hold after reveal {r.get('id')} "
                             f"(lands on {lb})")
    except Exception:
        pass
    return v


def plan_for_act(plan: dict, beats: list, k: int) -> str:
    """The act writer's slice of the plan."""
    by = {b["beat"]: b for b in plan.get("beats") or []}
    budget = next((a["word_budget"] for a in plan.get("acts") or []
                   if int(a.get("act")) == k), None)
    rows = []
    for bid in beats:
        b = by.get(bid)
        if not b:
            continue
        n = int(b.get("lines") or 0)
        what = (f"{n} line(s)" if n else
                "HOLD on footage, no narration" if b.get("footage") else
                "DROP - no line")
        extra = []
        if b.get("hold_after"):
            extra.append("then a silent hold (narration_silence_seconds)")
        if b.get("film_speaks"):
            extra.append("film_speaks spot")
        rows.append(f"- {bid}: {what}"
                    + (" - " + "; ".join(extra) if extra else "")
                    + (f"  ({b.get('why')})" if b.get("why") else ""))
    return ("# THE PLAN FOR YOUR BEATS - follow it exactly\n\n"
            f"Word budget for this act: {budget} words.\n"
            "Line counts are NARRATED lines per beat; set `note` to the beat "
            "id. The hook and the title are already written - do not write a "
            "hook line.\n\n" + "\n".join(rows))


def check_plan_counts(lines: list, plan: dict, beats: list) -> list:
    """Narrated lines per beat in an act vs the plan: the mismatches."""
    from pipeline.pacing_gates import _beat_of
    got: dict = {}
    for ln in lines:
        if isinstance(ln, dict) and str(ln.get("narration") or "").strip():
            got[_beat_of(ln)] = got.get(_beat_of(ln), 0) + 1
    by = {b["beat"]: int(b.get("lines") or 0) for b in plan.get("beats") or []}
    out = []
    for bid in beats:
        want, have = by.get(bid, 0), got.get(bid, 0)
        if want != have:
            out.append(f"{bid}: the plan says {want} line(s), the act has "
                       f"{have}")
    return out


def hook_line(plan: dict) -> dict:
    h = plan.get("hook") or {}
    # the same shape as the shipped tokyodrift2006 hook line
    return {"id": 1, "note": "HOOK", "over_montage": True, "delivery": "hook",
            "payload": "loop",
            "narration": str(h.get("narration") or "").strip(),
            "hook_question": str(h.get("hook_question") or "").strip(),
            "claim": {"type": "narration", "subject": "the film",
                      "requires_visual": False}}


# --------------------------------------------------------------------------- #
# RESOLVE: the review findings, closed in the artifacts' own format
# --------------------------------------------------------------------------- #
ARTIFACTS = ("cold_read.md", "review.md", "ending_read.md")


def open_findings(pdir: Path, draft: dict) -> list:
    """[{key, artifact, kind, ids, text}] - every FINDING no later
    RESOLVED/ANSWERED closes (review_artifacts' rule), plus every open
    SAME-POINT pair (closed in review.md by an entry naming both ids)."""
    from pipeline import review_artifacts as RA
    from pipeline import samepoint_gates as SP
    minw = int(getattr(config, "REVIEW_ANSWER_MIN_WORDS", 8))
    out = []
    for name in ARTIFACTS:
        art = RA.parse_artifact(Path(pdir) / name)
        fs = art.get("findings") or []
        valid = [f for f in fs if f["status"] in ("RESOLVED", "ANSWERED")
                 and not (f["status"] == "ANSWERED"
                          and len(f["text"].split()) < minw)]
        for f in fs:
            if f["status"] != "FINDING":
                continue
            if any(RA._closes(f, r) for r in valid if r["at"] > f["at"]):
                continue
            out.append({"artifact": name, "kind": f["kind"],
                        "ids": list(f["ids"]), "text": f["text"]})
    try:
        st = SP.samepoint_report(draft, pdir).get("stats") or {}
        closed = set()
        art = RA.parse_artifact(Path(pdir) / "review.md")
        for f in art.get("findings") or []:
            if f["status"] in ("RESOLVED", "ANSWERED"):
                closed |= {frozenset(f["ids"])}
        for a, b in st.get("candidates") or []:
            ids = {str(a), str(b)}
            if not any(ids <= set(c) for c in closed):
                out.append({"artifact": "review.md", "kind": "same-point",
                            "ids": [str(a), str(b)], "samepoint": True,
                            "text": f"lines {a} and {b} may make the same "
                                    f"point in different words"})
    except Exception:
        pass
    for i, f in enumerate(out, 1):
        f["key"] = f"F{i}"
    return out


RESOLVE_SCHEMA = {
    "type": "object",
    "properties": {
        # typed from the draft line schema by write_api.resolve_schema()
        "lines": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "integer"}, "narration": {"type": "string"},
            "delivery": {"type": "string"}, "payload": {"type": "string"},
            "narration_silence_seconds": {"type": "number"}},
            "required": ["id", "narration"], "additionalProperties": False}},
        "responses": {"type": "array", "items": {"type": "object",
                                                  "properties": {
            "key": {"type": "string"},
            "status": {"type": "string", "enum": ["RESOLVED", "ANSWERED"]},
            "text": {"type": "string"}},
            "required": ["key", "status", "text"],
            "additionalProperties": False}},
    },
    "required": ["lines", "responses"],
    "additionalProperties": False,
}

# The resolve request's system prompt is tools/resolve_prompt.md.


def resolve_user(lines: list, findings: list) -> str:
    rows = "\n".join(f"[{l['id']}] ({l.get('note') or ''}) "
                     f"{str(l.get('narration') or '').strip()}"
                     for l in lines if str(l.get("narration") or "").strip())
    fs = "\n".join(f"{f['key']} | {f['artifact']} | {f['kind']} | lines "
                   f"{','.join(f['ids']) or '-'} | {f['text']}"
                   for f in findings)
    return f"# YOUR LINES\n\n{rows}\n\n# OPEN FINDINGS\n\n{fs}"


def apply_resolution(findings: list, reply: dict, draft_lines: dict) -> tuple:
    """(changes {id: new text}, entries {artifact: [entry lines]}, rejects).

    A change to a line no finding names is REJECTED. A RESOLVED whose lines
    did not change, and an ANSWERED under the word floor, are rejected - the
    finding stays open."""
    minw = int(getattr(config, "REVIEW_ANSWER_MIN_WORDS", 8))
    named = {i for f in findings for i in f["ids"]}
    changes, rejects = {}, []
    for ln in reply.get("lines") or []:
        lid = str(ln.get("id"))
        new = " ".join(str(ln.get("narration") or "").split())
        old = " ".join(str(draft_lines.get(lid, {}).get("narration") or "")
                       .split())
        if lid not in draft_lines:
            rejects.append(f"line {lid} does not exist")
        elif lid not in named:
            rejects.append(f"line {lid} changed but no finding names it - "
                           f"kept as it was")
        elif new and new != old:
            changes[lid] = new
    by_key = {f["key"]: f for f in findings}
    entries: dict = {}
    for r in reply.get("responses") or []:
        f = by_key.get(r.get("key"))
        if not f:
            continue
        st = r.get("status")
        txt = " ".join(str(r.get("text") or "").split()).replace("|", "/")
        if st == "ANSWERED" and len(txt.split()) < minw:
            rejects.append(f"{f['key']}: ANSWERED with {len(txt.split())} "
                           f"word(s) (< {minw}) - stays open")
            continue
        if st == "RESOLVED" and not any(i in changes for i in f["ids"]):
            rejects.append(f"{f['key']}: RESOLVED but none of lines "
                           f"{f['ids']} changed - stays open")
            continue
        ids = ",".join(f["ids"]) or "-"
        ent = []
        if f.get("samepoint"):
            ent.append(f"FINDING | {f['kind']} | {ids} | {f['text']}")
        ent.append(f"{st} | {f['kind']} | {ids} | {txt}")
        entries.setdefault(f["artifact"], []).extend(ent)
        f["closed"] = True
    for f in findings:
        if not f.get("closed") and not any(f["key"] in x for x in rejects):
            rejects.append(f"{f['key']}: no response - stays open")
    return changes, entries, rejects


_FIND = re.compile(r"(```review-findings[ \t]*\r?\n)(.*?)(```)", re.S)
_SIG = re.compile(r"(```review-signatures[ \t]*\r?\n)(.*?)(```)", re.S)


def write_artifact(path: Path, entries: list, resign: dict) -> None:
    """Append entries to the findings fence; replace the signature of each
    re-signed line ({id: sig}) that the artifact signs. Nothing else in the
    file changes. Verified by re-parsing."""
    from pipeline import review_artifacts as RA
    txt = Path(path).read_text(encoding="utf-8-sig")
    before = RA.parse_artifact(path)
    if entries:
        m = _FIND.search(txt)
        add = "".join(e + "\n" for e in entries)
        if m:
            body = m.group(2)
            if body and not body.endswith("\n"):
                body += "\n"
            txt = txt[:m.start(2)] + body + add + txt[m.end(2):]
        else:
            txt += "\n```review-findings\n" + add + "```\n"
    if resign:
        m = _SIG.search(txt)
        if m:
            rows = []
            for raw in m.group(2).splitlines():
                p = raw.split()
                if len(p) == 2 and RA._norm_id(p[0]) in resign:
                    raw = raw.replace(p[1], resign[RA._norm_id(p[0])])
                rows.append(raw)
            txt = txt[:m.start(2)] + "\n".join(rows) + "\n" + txt[m.end(2):]
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(txt, encoding="utf-8")
    after = RA.parse_artifact(tmp)
    if after["errors"] or len(after["findings"]) != (
            len(before["findings"]) + len(entries)):
        tmp.unlink()
        raise ValueError(f"{Path(path).name}: the edited artifact does not "
                         f"parse back ({after['errors'][:2]})")
    tmp.replace(path)


# --------------------------------------------------------------------------- #
# UNWATCHABLE-FOOTAGE: move the window mechanically first
# --------------------------------------------------------------------------- #
def _ts(sec: float) -> str:
    h, r = divmod(max(0.0, sec), 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def fix_unwatchable(project: str, lines: list, measure=None) -> list:
    """Move each bound window that lands on black / a text card, in place.

    Candidates, in order: the part before the bad span, the part after it,
    the same length shifted to end where the span begins, or to start where
    it ends. A candidate must stay inside the line's beat (beat start to next
    beat start), fit the narration (apply_film_speaks._fits - the render's
    capacity contract), not overlap another line's footage, not touch a
    censor-flagged shot, not cross a reveal's landing the old window did not
    cross, and measure clean itself. Returns [action strings]; a window with
    no clean candidate is left for the writer.

    `measure(a, b)` -> [(span_a, span_b, kinds)]; default: the gate's own
    footage.frame_stats + unwatchable_spans on source.mp4."""
    from apply_film_speaks import _fits, _others, _win
    from pipeline import footage as F
    from pipeline import censor as C
    from pipeline.draft import parse_reveal_map, beat_times
    from pipeline.pacing_gates import _beat_of
    pdir = config.project_dir(project)
    src = pdir / "source.mp4"
    min_sec = float(getattr(config, "UNWATCHABLE_MIN_SEC", 1.0))
    if measure is None:
        if not src.exists():
            return []

        def measure(a, b):
            return F.unwatchable_spans(F.frame_stats(src, a, b), min_sec)
    try:
        bt = beat_times(project).get("ordered") or []
    except Exception:
        bt = []
    lands = [r["land_sec"] for r in parse_reveal_map(project)
             if r.get("land_sec") not in (None, float("inf"))]
    try:
        flagged = [(f["a"], f["b"]) for f in C.flagged_shots(pdir)]
    except Exception:
        flagged = []
    beat_rng = {}
    for i, (bid, t) in enumerate(bt):
        beat_rng[bid] = (t, bt[i + 1][1] if i + 1 < len(bt) else t + 600)
    acts = []
    for ln in lines:
        w = _win(ln)
        if not w or ln.get("film_speaks_seconds") is not None:
            continue
        a, b = w
        bad = measure(a, b)
        if not bad:
            continue
        lo, hi = beat_rng.get(_beat_of(ln), (a, b))
        lo, hi = min(lo, a), max(hi, b)
        sa, sb = bad[0][0], bad[-1][1]
        L = b - a
        cands = [(a, sa), (sb, b), (sa - L, sa), (sb, sb + L)]
        occupied = _others(lines, {ln.get("id")})
        ok = None
        for ca, cb in cands:
            if cb - ca < 0.5 or ca < lo - 1e-6 or cb > hi + 1e-6:
                continue
            if any(min(cb, ob) - max(ca, oa) > 0.05 for oa, ob, _i in occupied):
                continue
            if any(min(cb, fb) - max(ca, fa) > 0 for fa, fb in flagged):
                continue
            # stay on the same side of every reveal's landing: a window that
            # ended before a land must still end before it, one that started
            # after it must still start after it
            if any((b <= t + 1e-6) != (cb <= t + 1e-6)
                   or (a >= t - 1e-6) != (ca >= t - 1e-6) for t in lands):
                continue
            if not _fits(ln, ca, cb):
                continue
            if measure(ca, cb):
                continue
            ok = (ca, cb)
            break
        if ok:
            ln["clip_start"], ln["clip_end"] = _ts(ok[0]), _ts(ok[1])
            acts.append(f"line {ln.get('id')}: {_ts(a)}-{_ts(b)} held "
                        f"{'/'.join(bad[0][2])} at {_ts(sa)}-{_ts(sb)}; "
                        f"moved to {_ts(ok[0])}-{_ts(ok[1])}")
        else:
            acts.append(f"line {ln.get('id')}: {_ts(a)}-{_ts(b)} holds "
                        f"{'/'.join(bad[0][2])} at {_ts(sa)}-{_ts(sb)}; no "
                        f"clean window inside its beat - left for the writer")
    return acts
