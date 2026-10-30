"""Dwell, persona and continuity gates for the draft.

THE COMPLAINT
-------------
"Technically solid, but the writing feels rushed outside 2-3 scenes and the
narrator lacks a personal voice."

Measured on the shipped Tokyo Drift draft:
    56 of ~80 beats get exactly ONE line
    every 10 film-minutes gets 1.0-1.6 narration-minutes (flat)
    14 of 109 lines carry narrator judgment
    longest run of one-line beats: 9
    share of lines in the top 20% of beats: 0.324
and the scenes viewers singled out - Han on the footbridge, the Neela beats -
are exactly the ones that happen to carry 3-4 lines.

So the defect is not "some lines are weak". It is that the draft has no
CONTOUR: it spends its attention evenly, which means it never arrives
anywhere. These gates make the contour a requirement, read the narrator's
voice from angle.md rather than hoping for it, and catch the continuity
mistakes a flat draft tends to hide.

Every bar is in config, every bar is derived in docs/stage2/
PACING_CALIBRATION.md, and the derivation says which measured statistics are
NOT usable as bars and why.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import config

# ---- persona detection --------------------------------------------------- #
# A "judgment" line says what something MEANS or how the narrator feels about
# it. These are deliberately surface patterns: the gate is a floor on voice
# presence, not a literary assessment, and a surface floor is honest about
# being one.
# A PERSONA MOVE: direct address, first person, a question to the viewer, or a
# stance adverb. Deliberately TIGHT.
#
# The first version of this also matched "only", "still", "never", "finally",
# "worth", "nobody" and any "you" - and scored the shipped draft at 42.5%
# judgment when the draft's own label says 13.2%. It PASSED a draft the viewer
# said had no voice. Those words appear throughout ordinary descriptive prose;
# matching them measures English, not stance.
_MOVE = re.compile(
    r"(?:\byou\b|\byour\b|\byou're\b|\bI\b|\bI'm\b|\bwe\b|\bus\b|\bour\b|"
    r"\bof course\b|\bnaturally\b|\bapparently\b|\bsomehow\b|"
    r"\bfair enough\b|\bturns out\b|\bso much for\b|\bno prizes\b|"
    r"\bobviously\b|\bunsurprisingly\b|\badmittedly\b|\bmind you\b|"
    r"\bfrankly\b|\bhonestly\b|\bwhich is why\b|\bthe point is\b|"
    r"\bso that went\b|\?)", re.I)
# Editing / camera jargon the persona card forbids.
_JARGON = re.compile(
    r"\b(?:cut to|cuts to|we see|we cut|the camera|camera (?:holds|pans|"
    r"pushes|cuts)|in (?:this|the) (?:shot|frame)|on screen|"
    r"the frame|smash cut|fade (?:in|out) to)\b", re.I)
# A line that only reports what is visible: no judgment, no stance, no
# question, and no quoted speech.
_VISUAL_VERB = re.compile(
    r"\b(?:walks|stands|sits|looks|turns|holds|opens|closes|drives|pulls|"
    r"steps|watches|waits|enters|leaves|crosses|lifts|points|nods|smiles)\b",
    re.I)


def _narr(ln: dict) -> str:
    return str(ln.get("narration") or "").strip()


def _is_move(t: str) -> bool:
    """Does this line carry an audible narrator move?"""
    return bool(_MOVE.search(t))


def _is_judgment(ln: dict) -> bool:
    """The draft's OWN label. See config.PERSONA_JUDGMENT_SHARE_MIN."""
    return str(ln.get("payload") or "").strip().lower() == "judgment"


def _is_frame_only(t: str) -> bool:
    """Only reports what is on screen: a visual verb, no move, no quote.

    Calibrated against the references, which run 7.1-13.1% by this same
    detector (median 8.8%); the shipped draft is 14.2%.
    """
    if not t:
        return False
    if _is_move(t):
        return False
    if '"' in t or "\u201c" in t:        # carries character words
        return False
    return bool(_VISUAL_VERB.search(t))


def _beat_of(ln: dict) -> str:
    """The beat id a line belongs to.

    Falls back to `note` as given, then to the line's own id, when there is no
    B-number. The first version returned "" there and beat_table() SKIPPED the
    line, so any line whose note was not a B-number vanished from the contour
    statistics entirely - a 62-line draft measured as 32 lines in 8 beats. A
    line with no beat is its own one-line beat, which is both the honest
    reading and the worst case for the contour.
    """
    b = str(ln.get("note") or "").strip()
    m = re.match(r"B(\d{1,3})", b)
    if m:
        return f"B{int(m.group(1)):02d}"
    return b if b else f"_line{ln.get('id')}"


def beat_table(draft: dict) -> list:
    """[{beat, lines, narrated, film_sec, narr_words}] in draft order."""
    from pipeline.draft import parse_ts
    order: list = []
    seen: dict = {}
    for ln in draft.get("lines") or []:
        b = _beat_of(ln)
        if b not in seen:
            seen[b] = {"beat": b, "lines": 0, "narrated": 0,
                       "film_sec": 0.0, "narr_words": 0}
            order.append(seen[b])
        rec = seen[b]
        rec["lines"] += 1
        t = _narr(ln)
        if t:
            rec["narrated"] += 1
            rec["narr_words"] += len(t.split())
        cs, ce = ln.get("clip_start"), ln.get("clip_end")
        if cs and ce:
            try:
                rec["film_sec"] += max(0.0, parse_ts(ce) - parse_ts(cs))
            except Exception:
                pass
    return order


def pacing_report(draft: dict, pdir: Path) -> dict:
    """PACING-CONTOUR, HOOK-PAYOFF and the persona gates."""
    errors: list = []
    warns: list = []
    notes: list = []
    from pipeline import angle_spec
    # NO angle.md AT ALL is not a failure here: the project has not reached the
    # angle stage, and a new gate that kills a small fixture stops the OLD
    # gates from ever running - exactly what draft.py's own comment warns
    # about, and what this did to gate_selftest's TARGET-LOCK fixture (a
    # one-line draft with no angle). An angle that EXISTS but is missing the
    # sections these gates read is a different matter and is an error.
    if not (Path(pdir) / "angle.md").exists():
        return {"errors": [], "warns": [],
                "notes": [f"[PACING-CONTOUR] no angle.md in {Path(pdir).name} "
                          f"- contour and persona gates need its ANCHORS and "
                          f"NARRATOR PERSONA sections, so they did not run."],
                "stats": {}}
    try:
        spec = angle_spec.require(Path(pdir))
    except angle_spec.AngleSpecError as e:
        return {"errors": [f"[ANGLE-SPEC] {e}"], "warns": [], "notes": [],
                "stats": {}}

    table = beat_table(draft)
    if len(table) < 12:
        notes.append(f"[PACING-CONTOUR] only {len(table)} beat(s); statistics "
                     f"are not meaningful below 12 and are reported only.")
    anchors = spec["anchors"]
    anchor_beats = {b for a in anchors for b in a["beats"]}
    by_beat = {r["beat"]: r for r in table}

    # ---- anchor count ---------------------------------------------------- #
    if not (config.PACING_ANCHORS_MIN <= len(anchors)
            <= config.PACING_ANCHORS_MAX):
        errors.append(
            f"[PACING-CONTOUR] angle.md names {len(anchors)} anchor(s); the "
            f"contract is {config.PACING_ANCHORS_MIN}-"
            f"{config.PACING_ANCHORS_MAX}. Too few and the recap has no "
            f"shape; too many and nothing is an anchor.")

    # ---- every anchor must DWELL ----------------------------------------- #
    thin = []
    missing = []
    for a in anchors:
        got = sum(by_beat.get(b, {}).get("narrated", 0) for b in a["beats"])
        present = [b for b in a["beats"] if b in by_beat]
        if not present:
            missing.append("/".join(a["beats"]))
            continue
        if got < config.PACING_ANCHOR_MIN_LINES:
            thin.append(f"{'/'.join(a['beats'])} ({a['kind']}) has {got} "
                        f"line(s)")
    if missing:
        errors.append(
            f"[PACING-CONTOUR] {len(missing)} anchor(s) are not in the draft "
            f"at all: {', '.join(missing)}. An anchor the recap never reaches "
            f"is not an anchor.")
    if thin:
        errors.append(
            f"[PACING-CONTOUR] {len(thin)} anchor(s) are below "
            f"{config.PACING_ANCHOR_MIN_LINES} narration lines: "
            + "; ".join(thin)
            + ". An anchor is where the recap arrives: character words, the "
              "action, and a narrator reaction. One line is the defect this "
              "gate exists for.")

    # ---- the contour must not be flat ------------------------------------ #
    narrated = [r for r in table if r["narrated"] > 0]
    stats: dict = {"beats": len(table), "narrated_beats": len(narrated)}
    if narrated:
        counts = sorted((r["narrated"] for r in narrated), reverse=True)
        k = max(1, round(len(table) * 0.20))
        top = sorted(table, key=lambda r: -r["narrated"])[:k]
        tot = sum(r["narrated"] for r in table) or 1
        share = sum(r["narrated"] for r in top) / tot
        stats["top20_line_share"] = round(share, 3)
        stats["one_line_beats"] = sum(1 for r in table
                                      if r["narrated"] == 1)
        if share < config.PACING_TOP20_LINE_SHARE_MIN:
            errors.append(
                f"[PACING-CONTOUR] the contour is FLAT: the top 20% of beats "
                f"carry {share:.1%} of the narration lines, under the "
                f"{config.PACING_TOP20_LINE_SHARE_MIN:.0%} floor. The "
                f"reference channels concentrate 43-51% on their own basis "
                f"(see docs/stage2/PACING_CALIBRATION.md). Dwell on the "
                f"anchors and compress or drop the connective beats.")

        # longest run of one-line beats; a SILENT beat breaks the run
        run = best = 0
        worst_at = ""
        for r in table:
            if r["narrated"] == 1:
                run += 1
                if run > best:
                    best, worst_at = run, r["beat"]
            else:
                run = 0
        stats["longest_one_line_run"] = best
        if best > config.PACING_ONE_LINE_RUN_MAX:
            errors.append(
                f"[PACING-CONTOUR] {best} beats in a row get exactly one line "
                f"(ending at {worst_at}); the calibrated maximum is "
                f"{config.PACING_ONE_LINE_RUN_MAX}. That is the monotony the "
                f"viewer hears as rushed. Merge them, or drop some to footage "
                f"- a silent beat is a change of rhythm and breaks the run.")

        # anchors must be slower than the draft's own average
        def comp(r):
            return (r["film_sec"] / max(1.0, r["narr_words"]))
        mean_comp = (sum(comp(r) for r in narrated) / len(narrated))
        stats["mean_compression_sec_per_word"] = round(mean_comp, 3)
        fast = []
        for a in anchors:
            rs = [by_beat[b] for b in a["beats"]
                  if b in by_beat and by_beat[b]["narrated"] > 0]
            if not rs:
                continue
            c = sum(r["film_sec"] for r in rs) / max(
                1.0, sum(r["narr_words"] for r in rs))
            if c > mean_comp * (1.0 / config.PACING_ANCHOR_MAX_COMPRESSION_RATIO):
                fast.append(f"{'/'.join(a['beats'])} {c:.2f}s/word vs mean "
                            f"{mean_comp:.2f}")
        if fast:
            warns.append(
                f"[PACING-CONTOUR] {len(fast)} anchor(s) cover MORE film per "
                f"word than the draft average, i.e. they are compressed "
                f"harder than the connective tissue: " + "; ".join(fast))

    # ---- HOOK-PAYOFF ----------------------------------------------------- #
    for pr in spec["promises"]:
        if not pr["beats"]:
            errors.append(
                f"[HOOK-PAYOFF] the promise \"{pr['clause']}\" names no beat "
                f"to pay it off.")
            continue
        land = [b for b in pr["beats"] if b in anchor_beats]
        if not land:
            errors.append(
                f"[HOOK-PAYOFF] \"{pr['clause']}\" is paid off at "
                f"{'/'.join(pr['beats'])}, none of which is an ANCHOR. A "
                f"promise cashed in a compressed bridge beat is the "
                f"\"long story short\" defect.")
            continue
        got = sum(by_beat.get(b, {}).get("narrated", 0) for b in land)
        if got < config.PACING_ANCHOR_MIN_LINES:
            errors.append(
                f"[HOOK-PAYOFF] \"{pr['clause']}\" lands on "
                f"{'/'.join(land)} with only {got} narration line(s).")

    # ---- PERSONA --------------------------------------------------------- #
    lines = [ln for ln in (draft.get("lines") or []) if _narr(ln)]
    if lines:
        jud = [ln for ln in lines if _is_judgment(ln)]
        share = len(jud) / len(lines)
        stats["judgment_share"] = round(share, 3)
        if share < config.PERSONA_JUDGMENT_SHARE_MIN:
            errors.append(
                f"[PERSONA] {len(jud)} of {len(lines)} lines "
                f"({share:.1%}) carry any narrator judgment or stance, under "
                f"the {config.PERSONA_JUDGMENT_SHARE_MIN:.0%} floor. The "
                f"shipped draft scored 12.8% and read as a shot list with a "
                f"voice-over.")

        frame = [ln for ln in lines if _is_frame_only(_narr(ln))]
        fshare = len(frame) / len(lines)
        stats["frame_only_share"] = round(fshare, 3)
        if fshare > config.PERSONA_FRAME_ONLY_SHARE_MAX:
            errors.append(
                f"[PERSONA] {len(frame)} of {len(lines)} lines "
                f"({fshare:.1%}) only report what is already on screen, over "
                f"the {config.PERSONA_FRAME_ONLY_SHARE_MAX:.0%} cap. If the "
                f"picture says it, the narrator says what it MEANS or says "
                f"nothing. Worst: "
                + "; ".join(f"line {ln.get('id')}" for ln in frame[:6]))

        jar = [(ln.get("id"), _JARGON.search(_narr(ln)).group(0))
               for ln in lines if _JARGON.search(_narr(ln))]
        if jar:
            errors.append(
                f"[PERSONA] editing/camera jargon in {len(jar)} line(s), "
                f"which the persona card forbids: "
                + ", ".join(f"line {i} \"{w}\"" for i, w in jar[:6]))

        # the persona must be audible ACROSS the runtime, not clustered
        voiced = [ln for ln in lines
                  if _is_judgment(ln) or _is_move(_narr(ln))]
        stats["voiced_share"] = round(len(voiced) / len(lines), 3)
        gaps = _persona_gaps(draft, voiced)
        if gaps:
            errors.append(
                f"[PERSONA] {len(gaps)} window(s) of "
                f"{config.PERSONA_WINDOW_SEC/60:.0f} minutes carry no "
                f"narrator presence at all: "
                + ", ".join(f"{a/60:.1f}-{b/60:.1f} min" for a, b in gaps[:6])
                + ". A voice that appears in the first and last minute is not "
                  "a persona, it is bookends.")

    # ---- the anchor must END on a reaction -------------------------------- #
    bad_end = []
    for a in anchors:
        grp = [ln for ln in (draft.get("lines") or [])
               if _beat_of(ln) in a["beats"] and _narr(ln)]
        if not grp:
            continue
        if not (_is_judgment(grp[-1]) or _is_move(_narr(grp[-1]))):
            bad_end.append(f"{'/'.join(a['beats'])} (line {grp[-1].get('id')})")
    if bad_end:
        errors.append(
            f"[PERSONA] {len(bad_end)} anchor(s) end on description rather "
            f"than on a narrator reaction: " + ", ".join(bad_end[:6])
            + ". The last thing the viewer hears at an anchor is what the "
              "narrator makes of it.")

    return {"errors": errors, "warns": warns, "notes": notes, "stats": stats}


def _persona_gaps(draft: dict, jud: list) -> list:
    """Windows of PERSONA_WINDOW_SEC with no judgment line in them."""
    from pipeline.draft import parse_ts
    pos = []
    for ln in draft.get("lines") or []:
        cs = ln.get("clip_start")
        if not cs or not _narr(ln):
            continue
        try:
            pos.append((parse_ts(cs), ln in jud))
        except Exception:
            continue
    if len(pos) < 8:
        return []
    pos.sort()
    lo, hi = pos[0][0], pos[-1][0]
    w = float(config.PERSONA_WINDOW_SEC)
    out = []
    t = lo
    while t < hi:
        b = t + w
        inside = [p for p in pos if t <= p[0] < b]
        if len(inside) >= 3 and not any(p[1] for p in inside):
            out.append((t - lo, b - lo))
        t = b
    return out
