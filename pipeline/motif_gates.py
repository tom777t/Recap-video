"""Motif-budget and verbal-tic gates for the draft.

THE DEFECT
----------
Told to stop being flat, the rewrite overcorrected: it said everything it had
to say, and then said it again. Measured by this gate on the overcorrected
draft held in tools/fixtures/ (111 narrated lines of 114):

    one running bit's wording                   5 lines (budget 4)
    another running bit                         0 lines (promised, never run)
    explicit "this is the thesis" statements    4 (budget 1 before the outro)
    3-word phrases used in more than one line  20
    highest adjacent content-word overlap   0.222 (cap 0.50)

The same gate on the draft BEFORE that rewrite reports 6 repeated phrases, no
budget breach and no thesis statement at all, which is the other half of the
evidence: these bars separate the two drafts rather than failing every draft.
Both figures are reproduced, with the fixture paths, by the REAL-DRAFT-FAILS
and OLD-DRAFT-SEPARATES cases in tools/test_motif_gates.py - the fixtures and
every piece of film-specific wording live there, never here.

A callback works by being rare. Said every third minute it stops being a
callback and becomes a tic, and a thesis stated four times is not a thesis, it
is a habit. angle.md has carried a `## RUNNING BITS` section since the angle
was written and NOTHING PARSED IT, so the budget for a callback was whatever
the writer felt like on the day - which is how one bit reached five lines
without anything going red.

WHAT THIS GATE DOES NOT CATCH, stated here because a gate that is trusted for
more than it measures is worse than no gate:

  * [MOTIF-ADJACENT] is LEXICAL. The overcorrected draft does contain adjacent
    pairs that make the same point twice - the highest pair measures 0.222
    overlap, well under the 0.50 cap, because the second line restates the
    first in different words. Paraphrase is invisible to content-word overlap.
    This gate catches the copy-paste case only; the semantic case stays a job
    for the cold read. The cap is NOT lowered to 0.222 to "catch" it: the
    distribution has no gap there - the top eight pairs measure 0.222, 0.214,
    0.200, 0.200, 0.200, 0.188, 0.182, 0.176 - so any bar that fails the worst
    pair fails a tenth of the draft's ordinary prose with it.
  * [TIC-REPETITION] counts n-grams of config.TIC_NGRAM_N words carrying at
    least config.TIC_MIN_CONTENT_WORDS content words. The two tics named in
    config's own comment - a two-word stance adverb in 5 lines and a two-word
    noun phrase in 5 lines - are SHORTER than that window and carry one
    content word each, so they are outside this instrument by construction.
    Lowering either constant to reach them floods the report with structural
    English, which is the failure the constants exist to prevent. They are
    reported in stats as near-misses so the number is on the record.

Every bar is in config, with its derivation in config's own comments: these
are DECISIONS, not measurements, because a motif is identified from angle.md's
RUNNING BITS and the reference channels do not publish their angle, so there
is nothing in references/ to count.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import config

# ---- the stopword set ----------------------------------------------------- #
# Deliberately SMALL and function-word only. It is used by two gates and must
# mean the same thing in both: a "content word" is a word that carries the
# point of the line.
#
# An earlier version also dropped the 100 commonest English words, which took
# out "film", "race", "father", "money" and "home" - the exact words a recap's
# content IS. Adjacent overlap then measured 0.0 on two lines that said the
# same thing in the same words, because every word they shared had been
# deleted before the comparison. A stopword list for this purpose must contain
# nothing a writer could be making a point with.
_STOP = frozenset("""
a an the and or but nor so yet if then than that this these those
of in on at to for from with without into onto over under about after before
between during through across against along among around behind below beneath
beside beyond near past since toward towards until upon within
is are was were be been being am do does did doing done have has had having
will would shall should can could may might must
not no never ever just only also too very much more most less least
it its he she they them their there here what which who whom whose
when where why how while because though although unless whether
you your yours we our ours us i me my mine him his her hers
one two three some any each both few other another same such own
out up down off back again still now even
""".split())

# A narrated line is one with text. Holds and film_speaks units have empty
# narration and are NOT text the narrator says, so they are skipped for every
# count here - including for adjacency, where a hold between two lines does
# not stop them being heard back to back.
# Matches pipeline/pacing_gates.py `_narr` so the two gates agree on what a
# narrated line is.


def _narr(ln) -> str:
    if not isinstance(ln, dict):
        return ""
    return str(ln.get("narration") or "").strip()


def _lid(ln, idx: int):
    """The line's id, or its position when it has none.

    Never returns None. A finding that cannot name the line it is about is a
    finding the writer cannot act on, and `id` is not guaranteed by the schema
    for hand-written fixtures.
    """
    if isinstance(ln, dict) and ln.get("id") is not None:
        return ln.get("id")
    return f"#{idx}"


# Curly punctuation is folded to straight before any matching. angle.md is
# hand-typed and uses curly apostrophes; the draft JSON is machine-written and
# uses straight ones, so a motif named with a possessive matched nothing at all
# until this was added. This is the "minimal punctuation normalisation" the
# keyword match is allowed and no more: no stemming, no plural folding.
_FOLD = {
    "\u2018": "'", "\u2019": "'", "\u201b": "'", "\u02bc": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2013": "-", "\u2014": "-", "\u2212": "-",
    "\u2026": "...", "\u00a0": " ",
}


def _fold(s: str) -> str:
    out = str(s or "")
    for k, v in _FOLD.items():
        if k in out:
            out = out.replace(k, v)
    return out


def _norm(s: str) -> str:
    """Casefolded, whitespace-normalised, straight-punctuation text."""
    return " ".join(_fold(s).casefold().split())


_EDGE = "\"'`.,;:!?()[]{}<>-_*…"


def _tokens(s: str) -> list:
    """Whitespace split with punctuation stripped from token EDGES only.

    Edges only, so "don't" and "father's" stay one token. Stripping internal
    punctuation would turn "don't" into "dont" and stop it matching anything a
    human would search for.
    """
    out = []
    for w in _norm(s).split():
        w = w.strip(_EDGE)
        if w:
            out.append(w)
    return out


def _content(s) -> set:
    """Content words: >=4 characters, casefolded, stopwords removed.

    4 characters rather than 3: at 3 the set fills with "got", "run", "men",
    "day" and the overlap statistic starts measuring how much plain English
    two lines share rather than how much of their POINT they share.
    """
    return {w for w in _tokens(s) if len(w) >= 4 and w not in _STOP}


def _n_content(toks) -> int:
    return sum(1 for w in toks if len(w) >= 4 and w not in _STOP)


# ---- explicit thesis statements ------------------------------------------- #
# FILM-AGNOSTIC BY CONSTRUCTION. These match the SHAPE of a sentence that
# declares its own subject to be the point of the film; they contain no title,
# no character, and no wording from any draft, and the gate is tested against
# fixtures that supply the film specifics.
#
# The shapes, and why each is here:
#   1. demonstrative + copula + whole/entire + film|movie|story, with an
#      optional noun in between ("that's the whole X of this film"), which is
#      the same assertion with a hedge word inserted.
#   2. "the whole film in one <word>" - the summary-in-a-sentence move.
#   3. "what the film is about", with or without a demonstrative in front.
#   4. "the <noun> the whole film hangs off" - naming a line or beat AS the
#      thesis. Requires a determiner before the noun, which is what keeps it
#      from matching a plain description of something that happens across the
#      runtime ("X spent the whole film doing Y"); that sentence makes no
#      claim about what the film IS and failing it would make the gate fire on
#      ordinary summary.
#   5. "which is the point of the film".
#
# REJECTED: a bare "the point" / "the whole thing" pattern. It matched a line
# saying a CHARACTER thinks winning is not the point, which is a statement
# about a person, not a statement about the film, and three such lines in the
# fixture are not thesis statements at all.
_THESIS_SHAPES = (
    r"\b(?:that|this|it|there|here)(?:'s|\s+is|\s+was)\s+(?:the\s+)?"
    r"(?:whole|entire)\s+(?:\w+\s+of\s+(?:this|the)\s+)?"
    r"(?:film|movie|story)\b",
    r"\bthe\s+(?:whole|entire)\s+(?:film|movie|story)\s+in\s+"
    r"(?:one|a|two|half)\b",
    r"\bwhat\s+(?:this|the)\s+(?:film|movie|story)\s+is\s+"
    r"(?:really\s+|actually\s+)?about\b",
    r"\bthe\s+\w+\s+(?:the|this)\s+(?:whole|entire)\s+"
    r"(?:film|movie|story)\s+(?:hangs|turns|rests|hinges|pivots|is)\b",
    r"\b(?:which|that)\s+is\s+(?:the\s+)?(?:whole\s+)?point\s+of\s+"
    r"(?:the|this)\s+(?:film|movie|story)\b",
)
_THESIS = re.compile("|".join(_THESIS_SHAPES), re.I)

# Quoted speech. Both straight and curly, and an unclosed opening quote eats to
# the end of the line rather than being ignored: a line with one quote mark is
# a typo, and the safe reading of a typo is "this might be a character talking".
_QUOTED = re.compile(r'"[^"]*(?:"|$)')


def _strip_quotes(text: str) -> str:
    """Quoted speech replaced by a break marker.

    A tic is something the NARRATOR does. A phrase repeated because two
    characters said the same words, or because one character's line is quoted
    twice, is not a narrator tic, and the brief for this gate says so.
    The marker breaks the n-gram window instead of closing the gap, so no
    n-gram is ever assembled from words either side of a quote.
    """
    return _QUOTED.sub(" \x00 ", _fold(text))


# Strong punctuation ends a phrase. An n-gram that straddles a full stop is
# three words that never occurred together as a phrase, and the first version
# of this reported several of them; commas are NOT a break, because a phrase
# can legitimately run through one.
_BREAK = re.compile(r"[.!?;:\x00\u2022]|\s-\s|\s--\s")


def _phrase_chunks(text: str) -> list:
    """Token runs that a phrase may be taken from, quotes removed."""
    out = []
    for chunk in _BREAK.split(_strip_quotes(text)):
        toks = _tokens(chunk)
        if toks:
            out.append(toks)
    return out


# ---- proper names --------------------------------------------------------- #
def _load_names(pdir: Path) -> tuple:
    """(set of casefolded name tokens, how they were obtained).

    DEVIATION FROM THE BRIEF, RECORDED: the brief says to treat every string
    value and key token in names.json as a name. The real names.json in this
    repo cannot be read that way. It carries its provenance in keys prefixed
    with "_" whose values are whole explanatory paragraphs, and taking every
    token from those paragraphs yielded 80 "names", of which 40 were not names
    at all: `cast`, `english`, `following`, `from`, `is`, `a`, `an` and - worst
    - a verb that is also part of the film's own subject matter, so every
    phrase about the thing the recap is ABOUT became exempt. Excluding that
    much ordinary English from the tic search drops the finding count on the
    overcorrected fixture from 20 to 9, and the gate would then pass by having
    nothing left to look at, which is the exact failure mode this whole series
    of gates is about.

    So: underscore-prefixed keys are skipped (the repo's own convention for
    annotations - see names.json's own `_why_this_matters`), and only
    Capitalised tokens are taken from what remains. On the real file that
    yields 40 tokens, all of them actually names.
    """
    p = Path(pdir) / "names.json"
    if not p.exists():
        return set(), "absent"
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:
        # A names.json that exists but will not parse is reported, never
        # silently treated as empty: an empty name set makes every character
        # name a candidate tic and buries the real findings.
        return set(), f"unreadable ({type(e).__name__})"
    out: set = set()

    def walk(o) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(k, str) and k.startswith("_"):
                    continue
                walk(k)
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            for t in re.findall(r"[A-Za-z][A-Za-z'\u2019-]*", o):
                if len(t) >= 2 and t[:1].isupper():
                    out.add(_norm(t).strip(_EDGE))
    walk(data)
    out.discard("")
    return out, f"names.json ({len(out)} tokens)"


_SENT = re.compile(r"(?<=[.!?])\s+")


def _midsentence_caps(texts) -> set:
    """Fallback name set: tokens Capitalised anywhere but at a sentence start.

    WEAKNESS, stated because it is the reason names.json is preferred: this
    misses any name that happens to always open its sentence, and it wrongly
    claims any mid-sentence capital - a place, a brand, a day of the week, a
    title - as a name. Both errors point the same way, which is why it is only
    a fallback: a name it misses can be reported as a tic (a false alarm the
    writer can dismiss) and a word it over-claims is dropped from the search
    (a miss the writer never sees). The second is the dangerous one, so when
    names.json exists it is used instead and this is not consulted.
    """
    out: set = set()
    for text in texts:
        for sent in _SENT.split(_fold(text)):
            words = [w for w in sent.split() if w.strip(_EDGE)]
            for w in words[1:]:
                t = w.strip(_EDGE)
                if len(t) >= 2 and t[:1].isupper() and not t.isupper():
                    out.add(t.casefold())
    out.discard("")
    return out


def motif_report(draft: dict, pdir: Path) -> dict:
    """[MOTIF-BUDGET], [MOTIF-THESIS], [MOTIF-ADJACENT] and [TIC-REPETITION].

    Never raises. Anything that cannot be measured is SAID, as a note when the
    gate legitimately does not apply and as an error when the input is present
    but broken - never as an absent finding, which reads as a pass.
    """
    try:
        return _report(draft, pdir)
    except Exception as e:          # noqa: BLE001 - see below
        # A LAST RESORT, and it reports an ERROR rather than swallowing.
        # The house rule is that a gate must not raise on malformed input,
        # because draft.py runs the gates in a list and one exception stops
        # every gate after it from running at all. The rule is NOT that a
        # broken gate is a passing gate, so this is loud and names the
        # exception so it can be fixed rather than lived with.
        import traceback
        return {"errors": [f"[MOTIF-BUDGET] the motif gates could not run on "
                           f"{Path(pdir).name}: {type(e).__name__}: {e}. "
                           f"Nothing was measured, so treat this as unchecked "
                           f"rather than clean, and fix the gate."],
                "warns": [], "notes": [traceback.format_exc(limit=4)],
                "stats": {}}


def _report(draft: dict, pdir: Path) -> dict:
    errors: list = []
    warns: list = []
    notes: list = []
    stats: dict = {}
    pdir = Path(pdir)

    lines_max = int(getattr(config, "MOTIF_LINES_MAX", 4))
    cb_max = int(getattr(config, "MOTIF_CALLBACKS_MAX", 2))
    thesis_max = int(getattr(config, "MOTIF_THESIS_MAX", 1))
    adj_max = float(getattr(config, "MOTIF_ADJACENT_OVERLAP_MAX", 0.50))
    adj_min_words = int(getattr(config, "MOTIF_ADJACENT_MIN_CONTENT_WORDS", 4))
    ngram_n = int(getattr(config, "TIC_NGRAM_N", 3))
    ngram_max = int(getattr(config, "TIC_NGRAM_MAX", 1))
    tic_min_content = int(getattr(config, "TIC_MIN_CONTENT_WORDS", 2))
    id_cap = int(getattr(config, "MOTIF_REPORT_ID_CAP", 8))
    phrase_cap = int(getattr(config, "TIC_REPORT_PHRASE_CAP", 8))

    # ---- the narrated lines ---------------------------------------------- #
    raw = draft.get("lines") if isinstance(draft, dict) else None
    if not isinstance(raw, list):
        return {"errors": [], "warns": [],
                "notes": [f"[MOTIF-BUDGET] the draft for {pdir.name} has no "
                          f"`lines` list, so no narration text could be read "
                          f"and NOTHING was measured. This is not a pass."],
                "stats": {"narrated_lines": 0}}
    lines = []
    for i, ln in enumerate(raw):
        t = _narr(ln)
        if t:
            lines.append((_lid(ln, i), t, str((ln.get("delivery") or ""))
                          .strip().lower() if isinstance(ln, dict) else ""))
    stats["narrated_lines"] = len(lines)
    stats["draft_lines"] = len(raw)
    if not lines:
        notes.append(f"[MOTIF-BUDGET] {pdir.name}: 0 of {len(raw)} line(s) "
                     f"carry narration, so there is no text to measure. "
                     f"Nothing was checked.")

    # ---- the angle ------------------------------------------------------- #
    # NO angle.md AT ALL is a NOTE, never an error. draft.py runs every gate
    # over the same report list, and a new gate that errors on a small fixture
    # with no angle stops the OLD gates from ever running on it - which is
    # exactly what happened to gate_selftest's one-line TARGET-LOCK fixture
    # when the pacing gates were added. Same reasoning, same shape: see
    # pipeline/pacing_gates.pacing_report.
    if not (pdir / "angle.md").exists():
        notes.append(
            f"[MOTIF-BUDGET] no angle.md in {pdir.name} - the running bits "
            f"are declared in its `## RUNNING BITS` section, so the motif "
            f"budget could not be measured and did not run. The text-only "
            f"checks below still ran.")
        spec = None
    else:
        from pipeline import angle_spec
        try:
            spec = angle_spec.load(pdir)
        except Exception as e:      # noqa: BLE001
            # The file EXISTS and cannot be read. That is a different thing
            # from the project not having reached the angle stage, and it is
            # an error: an unreadable angle means the budget is unenforced on
            # a project that has one.
            errors.append(
                f"[MOTIF-BUDGET] angle.md in {pdir.name} exists but could not "
                f"be parsed ({type(e).__name__}: {e}), so the running-bit "
                f"budget was not checked on a project that declares one. Fix "
                f"the file; an unenforceable budget is how this defect "
                f"happened.")
            spec = None

    # ---- [MOTIF-BUDGET] -------------------------------------------------- #
    per_motif: dict = {}
    per_motif_ids: dict = {}
    if spec is not None:
        motifs = spec.get("motifs")
        if not isinstance(motifs, list):
            motifs = []
        stats["motifs"] = len(motifs)
        parsed = [m for m in motifs
                  if isinstance(m, dict) and str(m.get("name") or "")]
        unparsed = [m for m in motifs
                    if isinstance(m, dict) and not str(m.get("name") or "")]
        stats["motifs_parsed"] = len(parsed)
        stats["motifs_unparsed"] = len(unparsed)

        if unparsed:
            # AN UNENFORCEABLE BUDGET IS HOW THE DEFECT HAPPENED. The first
            # version of the angle parser required a quoted catchphrase and
            # silently dropped the entries that used a bolded label instead -
            # and the bit that broke its budget was one of the dropped ones.
            # A parser that skips what it cannot match hands the writer a
            # green gate on an unchecked bit, so an entry that will not parse
            # is an ERROR naming the text, not a warning.
            errors.append(
                f"[MOTIF-BUDGET] {len(unparsed)} RUNNING BITS entry/entries "
                f"in angle.md could not be parsed, so their budget cannot be "
                f"enforced at all: "
                + "; ".join(f'"{str(m.get("unparsed") or "")[:90]}"'
                            for m in unparsed[:6])
                + f". Give each one either a \"quoted phrase\" or a "
                  f"**bolded label** - whatever the narration actually says - "
                  f"so the gate can count it. An unenforced bit is how one "
                  f"bit reached {lines_max + 1}+ lines unnoticed.")

        if not motifs:
            notes.append(
                f"[MOTIF-BUDGET] angle.md in {pdir.name} declares no running "
                f"bits (`## RUNNING BITS` is empty or absent), so there was "
                f"no budget to check. If the recap has callbacks, they are "
                f"currently unbudgeted.")

        for m in parsed:
            name = str(m.get("name") or "")
            kws = m.get("keywords")
            if not isinstance(kws, list) or not kws:
                kws = [name]
            kws = [str(k) for k in kws if str(k).strip()]
            # Per-keyword hits are tracked separately so the message can say
            # WHICH surface form is overused: a bit written as two forms
            # ("X -> Y") is one budget, but the writer needs to know which of
            # the two to cut.
            by_kw: dict = {}
            hit_ids: list = []
            for lid, text, _dl in lines:
                nt = _norm(text)
                hit = [k for k in kws if _norm(k) and _norm(k) in nt]
                if hit:
                    hit_ids.append(lid)
                    for k in hit:
                        by_kw.setdefault(k, []).append(lid)
            per_motif[name] = len(hit_ids)
            per_motif_ids[name] = hit_ids
            if len(hit_ids) > lines_max:
                over = len(hit_ids) - lines_max
                shown = ", ".join(str(x) for x in hit_ids[:id_cap])
                more = ("" if len(hit_ids) <= id_cap
                        else f" (+{len(hit_ids) - id_cap} more)")
                worst = sorted(by_kw.items(), key=lambda kv: -len(kv[1]))
                breakdown = "; ".join(f'"{k}" x{len(v)}' for k, v in worst[:4])
                errors.append(
                    f"[MOTIF-BUDGET] the running bit \"{name}\" touches "
                    f"{len(hit_ids)} narrated line(s), over the budget of "
                    f"{lines_max} (= 1 setup + {cb_max} callback(s) + 1 "
                    f"payoff): lines {shown}{more} [{breakdown}]. Cut {over} "
                    f"of them: keep the line that sets it up, at most "
                    f"{cb_max} that call back, and the one that pays it off. "
                    f"The surplus lines are the same joke told again, which "
                    f"is what turns a callback into a tic.")
            elif not hit_ids:
                # WARN, NOT ERROR. The angle promised a running bit and the
                # draft never ran it, which is a real defect - but the fix may
                # legitimately be to delete the bit from angle.md, and an
                # error here would block a draft for a decision that belongs
                # to the editorial document.
                setup = "/".join(m.get("setup_beats") or []) or "?"
                pay = "/".join(m.get("payoff_beats") or []) or (
                    "outro" if m.get("payoff_outro") else "?")
                warns.append(
                    f"[MOTIF-BUDGET] the running bit \"{name}\" appears in 0 "
                    f"narrated lines, though angle.md sets it up at {setup} "
                    f"and pays it off at {pay}. Either run it - one setup, up "
                    f"to {cb_max} callbacks, one payoff - or strike it from "
                    f"angle.md. A promised bit the draft never says is a "
                    f"promise to the writer, not to the viewer.")
    stats["motif_lines"] = per_motif
    stats["motif_line_ids"] = per_motif_ids

    # ---- [MOTIF-THESIS] -------------------------------------------------- #
    # The outro is EXEMPT. Restating the thesis is what an outro is for, and
    # counting it made the gate fire on a draft whose only repetition was its
    # closing line - the one place the repetition is the point.
    thesis_ids = []
    outro_ids = []
    for lid, text, delivery in lines:
        m = _THESIS.search(_norm(text))
        if not m:
            continue
        if delivery == "outro":
            outro_ids.append(lid)
            continue
        thesis_ids.append(lid)
    stats["thesis_lines"] = len(thesis_ids)
    stats["thesis_line_ids"] = thesis_ids
    stats["thesis_lines_in_outro"] = len(outro_ids)
    if len(thesis_ids) > thesis_max:
        errors.append(
            f"[MOTIF-THESIS] {len(thesis_ids)} line(s) state the thesis AS "
            f"the thesis before the outro, over the budget of {thesis_max}: "
            f"lines {', '.join(str(x) for x in thesis_ids[:id_cap])}"
            + ("" if len(thesis_ids) <= id_cap
               else f" (+{len(thesis_ids) - id_cap} more)")
            + f". Keep the earliest one and cut the rest, or rewrite them to "
              f"SHOW the thesis instead of naming it"
            + (f" ({len(outro_ids)} further statement(s) in the outro are "
               f"exempt and were not counted)." if outro_ids else ".")
            + " Said more than once it is not a thesis, it is a habit, and "
              "every restatement tells the viewer what to think about a scene "
              "they are watching.")

    # ---- [MOTIF-ADJACENT] ------------------------------------------------- #
    # Overlap is |A n B| / min(|A|,|B|), NOT over the union.
    #
    # The defect is a short line whose content is entirely inside its
    # neighbour: a six-word restatement after a thirty-word line. With the
    # union in the denominator that pair scores 6/30 = 0.20 and passes, while
    # min scores 6/6 = 1.00 and fails - the union measures how similar two
    # lines are IN SIZE as much as in content, and the containment case is
    # precisely the one being gated. The cost is that min is harsher on
    # unequal pairs generally, which is what the minimum-content-word floor
    # below is for.
    worst = 0.0
    worst_pair = None
    skipped = 0
    adj_bad = []
    for (a_id, a_t, _a), (b_id, b_t, _b) in zip(lines, lines[1:]):
        A, B = _content(a_t), _content(b_t)
        if len(A) < adj_min_words or len(B) < adj_min_words:
            # A three-content-word line shares two words with its neighbour
            # and scores 0.67 without saying anything twice. Short lines are
            # also where a deliberate one-beat punchline lives, so the floor
            # is a floor on MEASURABILITY, not an exemption.
            skipped += 1
            continue
        ov = len(A & B) / float(min(len(A), len(B)))
        if ov > worst:
            worst, worst_pair = ov, (a_id, b_id)
        if ov > adj_max:
            adj_bad.append((a_id, b_id, ov))
    stats["max_adjacent_overlap"] = round(worst, 3)
    stats["max_adjacent_pair"] = list(worst_pair) if worst_pair else []
    stats["adjacent_pairs_measured"] = max(0, len(lines) - 1) - skipped
    stats["adjacent_pairs_skipped"] = skipped
    if adj_bad:
        errors.append(
            f"[MOTIF-ADJACENT] {len(adj_bad)} adjacent line pair(s) share "
            f"more than {adj_max:.0%} of their content words, i.e. the second "
            f"line is the first one written again: "
            + "; ".join(f"lines {a}+{b} ({o:.0%})"
                        for a, b, o in adj_bad[:id_cap])
            + ("" if len(adj_bad) <= id_cap
               else f" (+{len(adj_bad) - id_cap} more)")
            + ". Merge each pair into one line, or cut the second. Two "
              "consecutive lines making the same point is the overcorrection "
              "this gate exists for: the viewer hears the point, then hears "
              "it explained.")
    if skipped:
        notes.append(
            f"[MOTIF-ADJACENT] {skipped} of {max(0, len(lines) - 1)} adjacent "
            f"pair(s) were NOT measured because one line carries fewer than "
            f"{adj_min_words} content words; overlap is not meaningful on a "
            f"line that short. Those pairs are unchecked, not clean.")

    # ---- [TIC-REPETITION] ------------------------------------------------- #
    names, names_src = _load_names(pdir)
    if not names:
        # The fallback, and its weakness, are documented on
        # _midsentence_caps. It is used only when there is no roster to read.
        names = _midsentence_caps(t for _i, t, _d in lines)
        names_src = (f"mid-sentence capitals in the draft itself "
                     f"({len(names)} token(s)) - names.json {names_src}, so "
                     f"this fallback over-claims any capitalised place or "
                     f"brand and misses a name that always opens a sentence")
    stats["name_tokens"] = len(names)
    stats["name_source"] = names_src

    counts: Counter = Counter()
    where: dict = {}
    near: Counter = Counter()      # n-grams held back by the content floor
    for lid, text, _dl in lines:
        seen_here = set()
        for toks in _phrase_chunks(text):
            for i in range(0, max(0, len(toks) - ngram_n + 1)):
                g = toks[i:i + ngram_n]
                if any(w in names for w in g):
                    continue
                phrase = " ".join(g)
                if _n_content(g) < tic_min_content:
                    near[phrase] += 1
                    continue
                if phrase in seen_here:
                    # Counted ONCE PER LINE. A phrase repeated inside a single
                    # line is nearly always deliberate parallelism in one
                    # sentence - a figure, not a tic - and counting both
                    # occurrences reported one such line as a repeat offender
                    # against itself. A tic is a habit ACROSS the draft.
                    continue
                seen_here.add(phrase)
                counts[phrase] += 1
                where.setdefault(phrase, []).append(lid)
    rep = [(p, n) for p, n in counts.most_common() if n > ngram_max]
    stats["repeated_ngrams"] = len(rep)
    stats["top_repeated"] = [[p, n, where.get(p, [])[:id_cap]]
                             for p, n in rep[:phrase_cap]]
    # Recorded, not enforced: see the module docstring. These are the phrases
    # the content-word floor deliberately lets through, kept in stats so that
    # a reader can see what the instrument is blind to instead of inferring
    # that the draft is clean of short tics.
    stats["near_miss_repeated"] = [[p, n] for p, n in near.most_common(6)
                                   if n > ngram_max]
    if rep:
        shown = []
        for p, n in rep[:phrase_cap]:
            ids = ", ".join(str(x) for x in where.get(p, [])[:6])
            shown.append(f'"{p}" x{n} (lines {ids})')
        errors.append(
            f"[TIC-REPETITION] {len(rep)} {ngram_n}-word phrase(s) are used "
            f"in more than {ngram_max} line(s) outside quoted speech and "
            f"character names"
            + (f", worst {phrase_cap}" if len(rep) > phrase_cap else "")
            + ": " + "; ".join(shown)
            + ". Rewrite all but one occurrence of each. The fix is to VARY "
              "the move, not to drop it: a persona move repeated verbatim "
              "stops being a voice and becomes a verbal tic, and the viewer "
              "hears the writer rather than the narrator.")

    return {"errors": errors, "warns": warns, "notes": notes, "stats": stats}
