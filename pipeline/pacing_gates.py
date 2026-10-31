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

ROOT_DOCS = Path(__file__).resolve().parent.parent / "docs" / "stage2"

# A peak is an anchor the angle itself calls a reveal, a death or a win.
# MODULE-LEVEL, because two gates ask the question: [PEAK-ORDER] here and
# [SHOT-LIST-AFTER-PEAK] in shotlist_gates. It was a local inside
# pacing_report, so the other gate had to keep its own copy, and two
# copies of a definition drift without anyone noticing.
PEAK_WORDS = ("reveal", "death", "dies", "peak", "win", "climax")


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


_QUOTE = re.compile(r'["\u201c][^"\u201d]*["\u201d]')
# Evaluation that uses no pronoun. The first classifier had none of this and
# missed real judgment outright - "There's the mistake", "That's the whole of
# his pride", "the loyalest person in this film" - scoring 3 of the writer's
# 14 labelled lines. With these it reaches 11 of 14.
_EVAL = re.compile(
    r"(?:"
    r"\b(?:there|that|this|here)(?:'s| is| was)\s+the\b"
    r"|\bthe (?:whole|only|best|worst|point|problem|mistake|trick|truth|"
    r"joke|cost|price|difference)\b"
    r"|\bworth\s+\w+ing\b"
    r"|\b\w{4,}est\b"
    r"|\b(?:most|least) \w+\b"
    r"|\b(?:nobody|no one|everyone|anyone|nothing|everything) \w+"
    r"|\b(?:ugly|loyal|odd|ridiculous|stupid|clever|brave|cruel|petty|"
    r"generous|cheap|borrowed|pointless|honest|dishonest|decent)\b"
    r"|\bwhich is (?:why|how|what|the)\b"
    r"|\band that(?:'s| is) \w+"
    r")", re.I)


def classify_judgment(text: str) -> tuple:
    """(is_judgment, why) - the INDEPENDENT classifier.

    Judges the NARRATOR's own words: quoted character speech is stripped
    first, because "Have you been racing, Sean" is dialogue, not stance. "US"
    is neutralised because \bus\b matched "US Navy" in the first version.

    This is not ground truth and is not treated as such. It disagrees with the
    writer's label in both directions - it still flags 41% of lines, mostly
    UNQUOTED reported speech that no text rule can separate from narration -
    which is exactly why the gate counts only the lines where the two AGREE.
    """
    t = _QUOTE.sub(" ", str(text or ""))
    t = re.sub(r"\bUS\b", "AMERICAN", t)
    for name, pat in (("stance", _MOVE), ("eval", _EVAL)):
        m = pat.search(t)
        if m:
            return True, f"{name}:{m.group(0).strip()[:20]}"
    return False, ""


def _is_move(t: str) -> bool:
    """Does this line carry an audible narrator move?"""
    return classify_judgment(t)[0]


def _is_judgment(ln: dict) -> bool:
    """The draft's OWN label. See config.PERSONA_JUDGMENT_SHARE_MIN."""
    return str(ln.get("payload") or "").strip().lower() == "judgment"


def _is_frame_only(t: str) -> bool:
    """Only reports what is on screen: a visual verb, no move, no quote.

    Calibrated against the references, which run 7.1-13.1% by this same
    detector (median 8.8%); the shipped draft is 14.2%.

    WIDENED 2026-10-31 to include the SHOT LIST - a sentence that is a run of
    comma-separated visible nouns with no verb of consequence. The `_VISUAL_
    VERB` test above is a POSITIVE match on a closed verb list, so a sentence
    with no finite verb at all had nothing for it to match and scored as not
    frame-only, even though it reports strictly LESS than a line that at least
    says someone walked somewhere. See pipeline/shotlist_gates.py's docstring
    for the full diagnosis and for what the sentence-level measure catches
    that this line-level one cannot.
    """
    if not t:
        return False
    if _is_move(t):
        return False
    if '"' in t or "\u201c" in t:        # carries character words
        return False
    if _VISUAL_VERB.search(t):
        return True
    # FUNCTION-LOCAL IMPORT, and it has to be. shotlist_gates imports
    # classify_judgment from THIS module (it must, or the two detectors could
    # disagree about what counts as meaning) and this function imports
    # shotlist_gates, so a module-level import either way is a cycle that
    # neither module can finish. Both directions are deferred to call time, so
    # neither module cares which is imported first. The cost is one
    # sys.modules lookup per line, and has_shotlist_sentence stops at the
    # first hit, so this stays cheap enough for a per-line call.
    from pipeline.shotlist_gates import has_shotlist_sentence
    return has_shotlist_sentence(t)


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

    # ---- ANCHOR-EVIDENCE: check the angle against the BEAT MAP ----------- #
    # Runs before anything else reads the anchors, because every gate below
    # takes the anchor list on trust and one entry was wrong: "before he has
    # learned to turn" mapped to B47/B52/B53, where B47 is Kamata's cut and
    # B52 is handing over a car, while B60 - the only beat where Sean is
    # actually taught to drift - was filed as footage-only texture.
    from pipeline import beats_spec as _bs
    _beatmap = _bs.load_beats(Path(pdir))
    if not _beatmap:
        notes.append("[ANCHOR-EVIDENCE] no beat map found, so the anchor and "
                     "promise claims could not be checked against the beats.")
    else:
        for a in spec["anchors"]:
            ok, why = _bs.quote_supported(a.get("evidence", ""), a["beats"],
                                          _beatmap)
            if not ok:
                errors.append(
                    f"[ANCHOR-EVIDENCE] anchor {'/'.join(a['beats'])} "
                    f"({a['kind']}): {why}")
                continue
            # No lexical delivers() check on anchors either. The claim is a
            # kind | why sentence and the evidence is the beat's own prose;
            # overlap ran 0-14% on eight correct anchors, so the warning fired
            # on all of them and said nothing. Same reason it was dropped for
            # promises: the semantic judgement is the audit's job.
        for pr in spec["promises"]:
            ok, why = _bs.quote_supported(pr.get("evidence", ""),
                                          pr["beats"], _beatmap)
            if not ok:
                errors.append(
                    f"[ANCHOR-EVIDENCE] the promise \"{pr['clause']}\": {why}")
                continue
            # NO lexical delivers() check on a promise clause. A first
            # version required 34% content-word overlap between the clause and
            # the evidence and reported 0% for all four promises - "before he
            # has learned to turn" shares no literal words with "told to drift
            # by feeling". A poetic four-word clause cannot be matched
            # lexically against prose, and failing a correct mapping is worse
            # than not checking it here. The semantic judgement is a required
            # ARTIFACT instead: see the audit coverage check below.

    # ---- the independent audit must exist and cover every mapping ------- #
    # This is what makes "an independent check confirms the quote supports the
    # claim" a requirement rather than an intention. The audit is written by an
    # auditor given only the beat map, and it must name every promise clause
    # and every anchor beat - a mapping nobody audited is a mapping on trust,
    # which is how B47 survived.
    _audit = Path(ROOT_DOCS) / "ANGLE_EVIDENCE_AUDIT.md"
    if not _audit.exists():
        errors.append(
            f"[ANCHOR-EVIDENCE] no independent audit at "
            f"docs/stage2/{_audit.name}. Every anchor and promise mapping "
            f"must be derived from the beat map by an auditor that did not "
            f"write the angle, and the derivation recorded.")
    else:
        _at = _audit.read_text(encoding="utf-8", errors="replace").lower()
        _unaudited = [p["clause"] for p in spec["promises"]
                      if p["clause"].lower() not in _at]
        _ub = sorted({b for a in spec["anchors"] for b in a["beats"]
                      if b.lower() not in _at})
        if _unaudited:
            errors.append(
                f"[ANCHOR-EVIDENCE] {len(_unaudited)} promise(s) are not in "
                f"the independent audit: "
                + "; ".join(f'"{c}"' for c in _unaudited[:4]))
        if _ub:
            errors.append(
                f"[ANCHOR-EVIDENCE] anchor beat(s) {', '.join(_ub[:8])} are "
                f"not mentioned in the independent audit.")

    # a beat cannot be load-bearing AND demoted to texture
    _dem = spec.get("demoted") or {}
    _clash = []
    for a in spec["anchors"]:
        for b in a["beats"]:
            if b in _dem:
                _clash.append(f"{b} is an anchor ({a['kind']}) and is listed "
                              f"as secondary/footage-only")
    for pr in spec["promises"]:
        for b in pr["beats"]:
            if b in _dem:
                _clash.append(f"{b} pays off \"{pr['clause']}\" and is listed "
                              f"as secondary/footage-only")
    if _clash:
        errors.append(
            f"[ANCHOR-EVIDENCE] {len(_clash)} beat(s) are both load-bearing "
            f"and demoted to texture: " + "; ".join(_clash[:6])
            + ". Decide which it is - a beat the recap arrives at cannot also "
              "be a beat it holds on footage.")

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
        # LABEL AND CLASSIFIER MUST AGREE.
        #
        # The share used to read the writer's `payload` label alone, which the
        # writer can simply assert. The independent classifier is no better on
        # its own - it over-fires on unquoted reported speech. So the gate
        # counts the INTERSECTION, which is conservative because the two
        # signals are wrong in opposite directions, and separately checks the
        # agreement RATE, which is what collapses if the label is inflated.
        labelled = [ln for ln in lines if _is_judgment(ln)]
        agreed = [ln for ln in labelled
                  if classify_judgment(_narr(ln))[0]]
        classed = [ln for ln in lines if classify_judgment(_narr(ln))[0]]
        share = len(agreed) / len(lines)
        rate = len(agreed) / max(1, len(labelled))
        stats["judgment_labelled"] = len(labelled)
        stats["judgment_classified"] = len(classed)
        stats["judgment_agreed"] = len(agreed)
        stats["judgment_share"] = round(share, 3)
        stats["judgment_agreement_rate"] = round(rate, 3)
        if share < config.PERSONA_JUDGMENT_SHARE_MIN:
            errors.append(
                f"[PERSONA] only {len(agreed)} of {len(lines)} lines "
                f"({share:.1%}) are judgment BY BOTH the writer's label and "
                f"the independent classifier, under the "
                f"{config.PERSONA_JUDGMENT_SHARE_MIN:.0%} floor. "
                f"(label {len(labelled)}, classifier {len(classed)}, agreed "
                f"{len(agreed)}.) The shipped draft agreed on 11 of 106.")
        if labelled and rate < config.PERSONA_JUDGMENT_AGREEMENT_MIN:
            errors.append(
                f"[PERSONA] the writer labelled {len(labelled)} line(s) "
                f"judgment but the independent classifier confirms only "
                f"{len(agreed)} ({rate:.0%}, floor "
                f"{config.PERSONA_JUDGMENT_AGREEMENT_MIN:.0%}). That gap is "
                f"what label inflation looks like: "
                + ", ".join(f"line {ln.get('id')}" for ln in labelled
                            if not classify_judgment(_narr(ln))[0])[:160])

        # ---- the CEILING the floor never had ----------------------------- #
        # Told only to clear a floor, the rewrite came back at 52% judgment:
        # the narrator talks over the film and every beat arrives
        # pre-digested. A floor with no ceiling is half a bar.
        _jmax = float(getattr(config, "PERSONA_JUDGMENT_SHARE_MAX", 0.35))
        if share > _jmax:
            errors.append(
                f"[PERSONA-CEILING] {len(agreed)} of {len(lines)} lines "
                f"({share:.1%}) are judgment, over the {_jmax:.0%} ceiling. "
                f"The narrator is talking over the film. Cut commentary "
                f"lines, not the moments: a line that only tells the viewer "
                f"what to think about a beat they are watching is the first "
                f"to go.")

        # ---- no long RUN of judgment ------------------------------------- #
        # The reference-calibrated half of this gate: four of the five
        # English references never run more than two judgment sentences back
        # to back. A run is measured over the draft's lines IN ORDER; a hold
        # or a film-speaks unit breaks it, because a silence or the film's own
        # voice is exactly the interruption being asked for.
        #
        # BUG, found 2026-10-30 by tools/test_pacing.py PERSONA-RUN-HOLD-BREAKS
        # and FIXED here rather than documented around. This loop iterated
        # `lines`, which is filtered to NARRATED lines only (see the top of
        # this block) - and both of the things the comment above promises
        # would break a run carry EMPTY narration: a hold is
        # `narration_silence_seconds` with no text, a film-speaks unit is
        # `film_speaks_seconds` with no text (draft.py:622). Both were
        # therefore invisible to the run detector, and "judgment, judgment,
        # hold, judgment" reported a run of 3.
        #
        # That made the gate's own instruction unfollowable: the error text
        # tells the writer to "break them with ... a hold", and doing exactly
        # that did not clear the error. Iterating the raw line list fixes it;
        # the change is strictly LOOSENING (a non-narrated line can only end
        # a run, never start one), so nothing that passed before fails now.
        _rmax = int(getattr(config, "PERSONA_JUDGMENT_RUN_MAX", 2))
        _runs: list = []
        _cur: list = []
        for ln in (draft.get("lines") or []):
            if (isinstance(ln, dict) and _narr(ln)
                    and classify_judgment(_narr(ln))[0] and _is_judgment(ln)):
                _cur.append(ln.get("id"))
            else:
                if len(_cur) > _rmax:
                    _runs.append(list(_cur))
                _cur = []
        if len(_cur) > _rmax:
            _runs.append(list(_cur))
        stats["longest_judgment_run"] = max(
            [len(r) for r in _runs] + [0]) if _runs else 0
        if _runs:
            errors.append(
                f"[PERSONA-RUN] {len(_runs)} place(s) run more than {_rmax} "
                f"judgment lines back to back (longest "
                f"{max(len(r) for r in _runs)}). Break them with the thing "
                f"being judged - an action line, a quotation, or a hold: "
                + "; ".join("lines " + ",".join(str(i) for i in r)
                            for r in _runs[:4]))

        # ---- a peak lands FIRST, and is reacted to ONCE ------------------- #
        # At a death, a win or a reveal the moment has to arrive before the
        # opinion of it. Measured on the anchors the angle already names as
        # peaks, in draft order: the first line bound to the peak's beats
        # must not be commentary, and at most PERSONA_PEAK_REACTION_MAX of
        # the lines on it may be.
        #
        # Why the anchors and not a keyword hunt for "dies"/"wins": the angle
        # already declares which beats are the peaks, and a text rule looking
        # for death words would both miss a quiet reveal and fire on a line
        # that merely mentions one.
        _pmax = int(getattr(config, "PERSONA_PEAK_REACTION_MAX", 1))
        _peak_words = PEAK_WORDS
        for a in anchors:
            if not any(w in f"{a.get('kind','')} {a.get('why','')}".lower()
                       for w in _peak_words):
                continue
            onb = [ln for ln in lines if _beat_of(ln) in set(a["beats"])]
            if not onb:
                continue
            _is_cmt = [bool(classify_judgment(_narr(l))[0]) for l in onb]
            if _is_cmt and _is_cmt[0]:
                errors.append(
                    f"[PEAK-ORDER] the first line on peak "
                    f"{'/'.join(a['beats'])} (line {onb[0].get('id')}) is "
                    f"commentary. The moment has to land before the opinion "
                    f"of it: open on the action, the quotation or a hold, "
                    f"then react.")
            if sum(_is_cmt) > _pmax:
                errors.append(
                    f"[PEAK-ORDER] peak {'/'.join(a['beats'])} carries "
                    f"{sum(_is_cmt)} reaction lines (max {_pmax}): "
                    + ",".join(str(l.get('id')) for l, c in zip(onb, _is_cmt)
                               if c)
                    + ". Keep the sharpest one and give the rest back to the "
                      "moment.")

        # ---- every anchor keeps a line with NO commentary ----------------- #
        # Dwell was bought to make room for the moment. Spending all of it on
        # the narrator's opinion removes the thing being dwelt on.
        _cmin = int(getattr(config, "PERSONA_ANCHOR_CLEAN_LINES_MIN", 1))
        _dirty = []
        for a in anchors:
            onb = [ln for ln in lines if _beat_of(ln) in set(a["beats"])]
            if not onb:
                continue
            clean = [l for l in onb if not classify_judgment(_narr(l))[0]]
            if len(clean) < _cmin:
                _dirty.append(f"{'/'.join(a['beats'])} ({len(onb)} lines, "
                              f"{len(clean)} without commentary)")
        if _dirty:
            errors.append(
                f"[ANCHOR-CLEAN] {len(_dirty)} anchor(s) have fewer than "
                f"{_cmin} line(s) that are purely the moment: "
                + "; ".join(_dirty[:6])
                + ". Give the beat at least one line that just shows it.")

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
