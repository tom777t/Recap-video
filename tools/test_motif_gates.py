"""Motif budget and verbal tics - with the overcorrected draft as the fixture.

THE DEFECT, and the numbers behind it
-------------------------------------
Told the draft was flat, the rewrite said everything it had to say and then
said it again. Measured on tools/fixtures/draft_tokyodrift_overcorrected.json
(111 narrated lines of 114) by pipeline/motif_gates.py:

    worst running bit                            5 lines   (budget 4)
    a running bit the draft never says            0 lines   (promised in angle.md)
    explicit "this is the thesis" statements      4         (budget 1)
    3-word phrases used in more than one line    20         (budget 1 line each)
    highest adjacent content-word overlap     0.222         (cap 0.50)

The same gate on the draft BEFORE that rewrite reports 6 repeated phrases, no
budget breach and no thesis statement, so the bars separate the two drafts
instead of failing everything.

Cases - EVERY gate is tested in BOTH directions, because a gate that only
fires, or only stays silent, is not tested at all:

  MOTIF-BUDGET-FIRES      6 lines on one bit is named, counted and located.
  MOTIF-BUDGET-SILENT     exactly 4 lines - the full 1+2+1 budget - is clean.
  MOTIF-BUDGET-ZERO       a bit the draft never says WARNS, never errors: the
                          fix may be to delete it from angle.md.
  MOTIF-BUDGET-UNPARSED   a RUNNING BITS entry the parser cannot read is an
                          error, because an unenforceable budget is the defect.
  MOTIF-THESIS            2 statements fire, 1 is clean, and a second one in
                          the outro is exempt - restating it is the outro's job.
  MOTIF-ADJACENT          a restated line fires, two different lines are clean,
                          and a pair too short to measure is SKIPPED and said so.
  TIC-REPETITION          a phrase in two lines fires, in one line is clean.
  TIC-NAMES-AND-QUOTES    the same phrase is exempt inside quoted speech and
                          exempt when it carries a name from names.json - and
                          fires again once the exemption is removed, so the
                          exemption is doing the work and not the wording.
  REAL-DRAFT-FAILS        the overcorrected fixture still reports its defects.
  OLD-DRAFT-SEPARATES     the pre-rewrite draft does NOT trip the two gates
                          aimed at overcorrection.
  NO-ANGLE-IS-A-NOTE      a project with no angle.md gets a note, no error.
  BARS-COME-FROM-CONFIG   moving the constant moves the verdict, so the gate
                          reads config rather than carrying its own literals.
  GATE-NEVER-RAISES       malformed drafts degrade to "nothing was measured"
                          and say so, instead of raising or passing silently.

Run:  python tools/test_motif_gates.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from pipeline import angle_spec  # noqa: E402
from pipeline import motif_gates as mg  # noqa: E402

PROJ = Path(config.project_dir("tokyodrift2006"))
FIX = Path(ROOT) / "tools" / "fixtures" / "draft_tokyodrift_overcorrected.json"
OLD = Path(ROOT) / "tools" / "fixtures" / "draft_tokyodrift_flat.json"

_TMP: list = []


# --------------------------------------------------------------------------- #
# Fixtures. ALL film-specific wording lives here and nowhere in the gate: the
# gate is handed its motifs by angle.md at run time and its thesis patterns are
# shapes, so these invented phrases are enough to exercise it. The real film's
# text appears only through the two on-disk fixtures.
# --------------------------------------------------------------------------- #
def _proj(running_bits: str | None = None, names: list | None = None) -> Path:
    """A throwaway project dir with only the sections under test.

    `angle_spec.load` is the SOFT variant - it reads whatever sections exist
    and requires none of them, raising only when angle.md itself is absent
    (angle_spec.py lines 48-53). `require` is the strict one and the motif
    gates deliberately do not call it, so an angle.md holding nothing but
    `## RUNNING BITS` is a valid fixture here and would not be for
    pacing_gates.
    """
    d = Path(tempfile.mkdtemp(prefix="motif_gate_"))
    _TMP.append(d)
    if running_bits is not None:
        (d / "angle.md").write_text(
            "# throwaway fixture\n\n## RUNNING BITS\n\n" + running_bits + "\n",
            encoding="utf-8")
    if names is not None:
        (d / "names.json").write_text(
            json.dumps({"names": [{"character": n} for n in names]}),
            encoding="utf-8")
    return d


def _draft(items) -> dict:
    """items: a list of strings, or of (text, delivery) pairs."""
    lines = []
    for i, it in enumerate(items, 1):
        text, delivery = (it, "normal") if isinstance(it, str) else it
        lines.append({"id": i, "note": f"B{i:02d}", "payload": "reasoning",
                      "narration": text, "delivery": delivery,
                      "clip_start": "00:0%d:00.000" % (i % 10),
                      "clip_end": "00:0%d:08.000" % (i % 10)})
    return {"lines": lines}


def _tagged(rep: dict, tag: str, key: str = "errors") -> list:
    return [m for m in rep[key] if m.startswith(f"[{tag}]")]


# The bit under test, and 10 unrelated lines to pad the draft out. The padding
# shares no vocabulary with anything, so a budget finding cannot be an
# adjacency or tic finding wearing a different hat.
_BIT = "left holding the bag"
_FILLER = [
    "The crew count the takings on a workbench nobody has cleaned in years.",
    "Rain arrives halfway through the second lap and settles the argument.",
    "Somebody's uncle owns the garage, which explains most of the politics.",
    "A phone call interrupts the celebration before anybody opens anything.",
    "The paperwork says one owner; the ashtray says otherwise.",
    "Downstairs, two mechanics argue about tyre pressure like theologians.",
]


def _bit_lines(n: int) -> list:
    """n lines that each contain the bit's exact wording, kept apart."""
    out = []
    frames = [
        "Once again he is {b} while somebody else drives away.",
        "His mother leaves and he is {b} in a kitchen that smells of bleach.",
        "The deal collapses and guess who is {b} for the shortfall.",
        "Everyone scatters; he stays {b} with a torch and no plan.",
        "Being {b} is apparently a condition rather than an accident.",
        "By now {b} is the only job description that has ever fitted him.",
    ]
    for i in range(n):
        out.append(frames[i % len(frames)].format(b=_BIT))
        if i < len(_FILLER):
            out.append(_FILLER[i])
    return out


def _bits_entry(phrase: str = _BIT) -> str:
    return (f'1. **"{phrase}."** - the spine made into a phrase. '
            f'**Setup: B13** (the first time it happens) -> '
            f'**Payoff: B91/outro** - and the last.')


# --------------------------------------------------------------------------- #
# MOTIF-BUDGET
# --------------------------------------------------------------------------- #
def test_motif_budget_fires() -> tuple[bool, str]:
    """A running bit in more lines than its budget is named and located."""
    d = _proj(_bits_entry())
    rep = mg.motif_report(_draft(_bit_lines(6)), d)
    errs = _tagged(rep, "MOTIF-BUDGET")
    if not errs:
        return False, (f"6 lines on one running bit produced no "
                       f"[MOTIF-BUDGET] error; stats say "
                       f"{rep['stats'].get('motif_lines')}")
    msg = errs[0]
    if _BIT not in msg:
        return False, f"the error does not name the running bit: {msg[:160]}"
    if "6 narrated line" not in msg:
        return False, f"the error does not state the count of 6: {msg[:160]}"
    got = rep["stats"]["motif_lines"].get(_BIT)
    if got != 6:
        return False, f"stats counted {got} lines, not 6"
    ids = rep["stats"]["motif_line_ids"][_BIT]
    if not all(str(i) in msg for i in ids[:6]):
        return False, f"the error does not list the offending lines: {msg}"
    if "1 setup" not in msg or "payoff" not in msg:
        return False, ("the error does not break the budget down into "
                       "setup/callbacks/payoff, so the writer is not told "
                       "what to cut")
    return True, (f"6 lines on one bit: errors on the budget of "
                  f"{config.MOTIF_LINES_MAX}, names the bit, counts 6, lists "
                  f"lines {ids} and says to cut "
                  f"{6 - config.MOTIF_LINES_MAX}")


def test_motif_budget_silent() -> tuple[bool, str]:
    """The full budget - 1 setup + 2 callbacks + 1 payoff - must be clean."""
    d = _proj(_bits_entry())
    n = config.MOTIF_LINES_MAX
    rep = mg.motif_report(_draft(_bit_lines(n)), d)
    errs = _tagged(rep, "MOTIF-BUDGET")
    if errs:
        return False, (f"a bit used exactly {n} times - its whole budget - "
                       f"errors anyway: {errs[0][:200]}")
    if _tagged(rep, "MOTIF-BUDGET", "warns"):
        return False, ("a bit used its full budget and still warned: "
                       + rep["warns"][0][:160])
    if rep["stats"]["motif_lines"].get(_BIT) != n:
        return False, (f"the fixture does not actually use the bit {n} times: "
                       f"{rep['stats']['motif_lines']}")
    return True, (f"the same bit in exactly {n} lines (1 setup + "
                  f"{config.MOTIF_CALLBACKS_MAX} callbacks + 1 payoff) is "
                  f"clean - the bar is a budget, not a ban")


def test_motif_budget_zero() -> tuple[bool, str]:
    """A promised bit the draft never says WARNS; it must not block."""
    d = _proj(_bits_entry())
    rep = mg.motif_report(_draft(_FILLER), d)
    if _tagged(rep, "MOTIF-BUDGET"):
        return False, ("an unused running bit BLOCKS the draft: "
                       + rep["errors"][0][:200])
    warns = _tagged(rep, "MOTIF-BUDGET", "warns")
    if not warns:
        return False, ("a running bit angle.md promises and the draft never "
                       "says produced no warning at all")
    if _BIT not in warns[0] or "0 narrated lines" not in warns[0]:
        return False, f"the warning does not name the unused bit: {warns[0]}"
    if "B13" not in warns[0]:
        return False, (f"the warning does not say where angle.md meant it to "
                       f"go: {warns[0]}")
    return True, ("a bit promised in angle.md and absent from the draft warns "
                  "(0 lines, setup B13) and does not block - deleting the bit "
                  "from angle.md is a legitimate fix and that is an editorial "
                  "decision")


def test_motif_budget_unparsed() -> tuple[bool, str]:
    """An entry the parser cannot read is an ERROR, not a silent skip."""
    bits = (_bits_entry() + "\n\n"
            + "2. A running bit written as prose, with no quoted phrase and "
              "no bolded label, so there is nothing to count in the draft.\n")
    d = _proj(bits)
    spec = angle_spec.load(d)
    unp = [m for m in spec["motifs"] if not m.get("name")]
    if len(unp) != 1:
        return False, (f"the fixture does not produce exactly one unparsed "
                       f"entry; angle_spec returned {spec['motifs']}")
    rep = mg.motif_report(_draft(_bit_lines(1)), d)
    errs = _tagged(rep, "MOTIF-BUDGET")
    if not errs:
        return False, ("an unparseable RUNNING BITS entry produced no error - "
                       "the budget on that bit is unenforceable and nothing "
                       "says so, which is how the defect happened")
    if "no quoted phrase" not in errs[0]:
        return False, (f"the error does not quote the text it could not "
                       f"parse, so the writer cannot find it: {errs[0][:200]}")
    if rep["stats"]["motifs_unparsed"] != 1:
        return False, f"stats report {rep['stats']['motifs_unparsed']} unparsed"
    if rep["stats"]["motifs_parsed"] != 1:
        return False, ("the parseable entry was lost along with the "
                       "unparseable one")
    return True, ("1 unparsed RUNNING BITS entry errors and quotes the text; "
                  "the 1 parseable entry alongside it is still counted")


# --------------------------------------------------------------------------- #
# MOTIF-THESIS
# --------------------------------------------------------------------------- #
_THESIS_A = ("You cannot keep moving every time it goes wrong. That's the "
             "whole film, said out loud, fifteen minutes in.")
_THESIS_B = ("There it is. The whole film in one sentence, from the one man "
             "least qualified to say it.")
_THESIS_C = "And this is what the film is about, if it is about anything."


def test_motif_thesis() -> tuple[bool, str]:
    """Two explicit thesis statements fire; one is clean; the outro is exempt."""
    d = _proj()          # no angle.md: this gate reads only the narration
    two = mg.motif_report(_draft([_THESIS_A, _FILLER[0], _THESIS_B]), d)
    e2 = _tagged(two, "MOTIF-THESIS")
    if not e2:
        return False, ("two lines naming the thesis as the thesis produced no "
                       "[MOTIF-THESIS] error")
    if "1" not in e2[0] or "3" not in e2[0]:
        return False, f"the error states neither the count nor the lines: {e2[0]}"
    if two["stats"]["thesis_lines"] != 2:
        return False, (f"counted {two['stats']['thesis_lines']} thesis lines, "
                       f"not 2: {two['stats']['thesis_line_ids']}")

    one = mg.motif_report(_draft([_THESIS_A, _FILLER[0], _FILLER[1]]), d)
    if _tagged(one, "MOTIF-THESIS"):
        return False, (f"a single thesis statement errors, though the budget "
                       f"is {config.MOTIF_THESIS_MAX}: "
                       + one["errors"][0][:200])
    if one["stats"]["thesis_lines"] != 1:
        return False, (f"the one-statement fixture measured "
                       f"{one['stats']['thesis_lines']}")

    outro = mg.motif_report(
        _draft([_THESIS_A, _FILLER[0], (_THESIS_B, "outro")]), d)
    if _tagged(outro, "MOTIF-THESIS"):
        return False, ("a thesis restated in the OUTRO was counted against "
                       "the budget; restating it is what an outro is for: "
                       + outro["errors"][0][:200])
    if outro["stats"]["thesis_lines_in_outro"] != 1:
        return False, ("the outro statement was not recognised at all, so the "
                       "silence above proves nothing about the exemption")

    third = mg.motif_report(
        _draft([_THESIS_A, _FILLER[0], _THESIS_C, _FILLER[1], _THESIS_B]), d)
    if third["stats"]["thesis_lines"] != 3:
        return False, (f'"what the film is about" is not detected: '
                       f'{third["stats"]["thesis_line_ids"]}')

    plain = mg.motif_report(
        _draft(["He spent the whole film telling the kid to stop driving "
                "angry, and the kid spent it not listening."]), d)
    if plain["stats"]["thesis_lines"]:
        return False, ("a plain description of what somebody does across the "
                       "runtime is being read as a thesis statement; that "
                       "fires the gate on ordinary summary")
    return True, (f"2 statements error (budget {config.MOTIF_THESIS_MAX}), 1 "
                  f"is clean, a 2nd in an `outro` line is exempt and counted "
                  f"separately, all three sentence shapes are detected, and "
                  f'"spent the whole film doing X" is not mistaken for one')


# --------------------------------------------------------------------------- #
# MOTIF-ADJACENT
# --------------------------------------------------------------------------- #
_SAME_A = "The borrowed engine finally matters because the kid never owned anything."
_SAME_B = "The borrowed engine matters, because the kid never owned anything at all."
_DIFF_B = "Upstairs a tired policeman fills in a form about a stolen scooter."


def test_motif_adjacent() -> tuple[bool, str]:
    """Adjacent restatement fires; different lines are clean; shorts are skipped."""
    d = _proj()
    dup = mg.motif_report(_draft([_SAME_A, _SAME_B]), d)
    errs = _tagged(dup, "MOTIF-ADJACENT")
    if not errs:
        return False, (f"two adjacent lines restating each other measured "
                       f"{dup['stats']['max_adjacent_overlap']} overlap and "
                       f"did not fire")
    if "1+2" not in errs[0]:
        return False, f"the error does not name the pair: {errs[0][:200]}"
    ov = dup["stats"]["max_adjacent_overlap"]
    if ov <= config.MOTIF_ADJACENT_OVERLAP_MAX:
        return False, f"the fixture pair only measures {ov}"

    ok = mg.motif_report(_draft([_SAME_A, _DIFF_B]), d)
    if _tagged(ok, "MOTIF-ADJACENT"):
        return False, ("two lines about different things were reported as the "
                       "same line twice: " + ok["errors"][0][:200])
    ov2 = ok["stats"]["max_adjacent_overlap"]

    # A hold between two lines must not hide the adjacency: the viewer hears
    # them back to back regardless.
    held = {"lines": [
        {"id": 1, "narration": _SAME_A, "delivery": "normal"},
        {"id": 2, "narration": "", "narration_silence_seconds": 3.0},
        {"id": 3, "narration": _SAME_B, "delivery": "normal"}]}
    if not _tagged(mg.motif_report(held, d), "MOTIF-ADJACENT"):
        return False, ("a silent hold between two restated lines hid the "
                       "adjacency; holds are not narration and must not break "
                       "the pair")

    short = mg.motif_report(_draft(["He loses.", "He loses."]), d)
    if _tagged(short, "MOTIF-ADJACENT"):
        return False, ("a pair with one content word each was scored anyway; "
                       "overlap on a three-word line measures nothing")
    if short["stats"]["adjacent_pairs_skipped"] != 1:
        return False, "the too-short pair was not recorded as skipped"
    if not _tagged(short, "MOTIF-ADJACENT", "notes"):
        return False, ("the too-short pair was skipped SILENTLY - unchecked "
                       "has to be said out loud, or it reads as clean")
    floor = getattr(config, "MOTIF_ADJACENT_MIN_CONTENT_WORDS", 4)
    return True, (f"a restated pair measures {ov:.2f} and errors (cap "
                  f"{config.MOTIF_ADJACENT_OVERLAP_MAX:.2f}), two unrelated "
                  f"lines measure {ov2:.2f} and are clean, a hold between the "
                  f"pair does not hide it, and a pair under {floor} content "
                  f"words is skipped WITH a note")


# --------------------------------------------------------------------------- #
# TIC-REPETITION
# --------------------------------------------------------------------------- #
_TIC = "borrowed engine wins"
_TIC_1 = "A borrowed engine wins the final, which nobody saw coming."
_TIC_2 = "Years later a borrowed engine wins again, in a wreck his father found."
_TIC_2_OK = "Years later he takes the mountain in a wreck his father found."


def test_tic_repetition() -> tuple[bool, str]:
    """A phrase in two lines fires; the same phrase in one line is clean."""
    d = _proj()
    rep = mg.motif_report(_draft([_TIC_1, _FILLER[0], _TIC_2]), d)
    errs = _tagged(rep, "TIC-REPETITION")
    if not errs:
        return False, (f'"{_TIC}" used in two lines produced no error; '
                       f'repeated: {rep["stats"]["top_repeated"]}')
    if _TIC not in errs[0]:
        return False, f"the error does not quote the phrase: {errs[0][:200]}"
    if "lines 1, 3" not in errs[0]:
        return False, f"the error does not locate the phrase: {errs[0][:200]}"
    top = {p for p, _n, _ids in rep["stats"]["top_repeated"]}
    if _TIC not in top:
        return False, f"stats do not report the phrase: {top}"

    once = mg.motif_report(_draft([_TIC_1, _FILLER[0], _TIC_2_OK]), d)
    if _tagged(once, "TIC-REPETITION"):
        return False, ("a phrase used ONCE was reported as a tic: "
                       + once["errors"][0][:220])
    if once["stats"]["repeated_ngrams"]:
        return False, (f"the single-use draft reports "
                       f"{once['stats']['repeated_ngrams']} repeats: "
                       f"{once['stats']['top_repeated']}")

    # Structural English must not be flagged, or the report is unreadable and
    # gets ignored wholesale - which is how a real finding gets buried.
    struct = mg.motif_report(
        _draft(["He had to go back to the one place he had been sent from.",
                _FILLER[0],
                "She had to go back to the one job she had walked out of."]),
        d)
    if _tagged(struct, "TIC-REPETITION"):
        return False, ("structural English was reported as a tic: "
                       + struct["errors"][0][:220])

    # ...and the same words twice INSIDE one line are deliberate parallelism,
    # not a habit across the draft.
    inside = mg.motif_report(
        _draft(["He is thrown into the street, gets up, goes back in, and is "
                "thrown into the street again."]), d)
    if _tagged(inside, "TIC-REPETITION"):
        return False, ("a phrase repeated inside a single sentence was called "
                       "a tic: " + inside["errors"][0][:220])
    return True, (f'"{_TIC}" in 2 lines errors and names lines 1 and 3; the '
                  f"same phrase in 1 line, two sentences of structural "
                  f"English, and a deliberate repetition inside one line are "
                  f"all clean")


def test_tic_names_and_quotes() -> tuple[bool, str]:
    """Quoted speech and character names are exempt - and the exemption works."""
    q1 = f'He shrugs: "a {_TIC} the same as any other, kid."'
    q2 = f'Much later, someone repeats it: "a {_TIC} the same as any other."'
    quoted = mg.motif_report(_draft([q1, _FILLER[0], q2]), _proj())
    if _tagged(quoted, "TIC-REPETITION"):
        return False, ("a phrase repeated inside quoted character speech was "
                       "charged to the narrator: "
                       + quoted["errors"][0][:220])
    # The same words unquoted MUST fire, or the silence above only proves the
    # phrase is unfindable.
    bare = mg.motif_report(
        _draft([q1.replace('"', ""), _FILLER[0], q2.replace('"', "")]),
        _proj())
    if not _tagged(bare, "TIC-REPETITION"):
        return False, ("with the quotation marks removed the same repetition "
                       "is still not reported, so the quote exemption is not "
                       "what silenced it")

    # NAMES from names.json. "Brightwell" is invented: the roster is read from
    # the project, so no real name belongs in this file.
    n1 = "Brightwell borrowed engine, and the kid drove off with it."
    n2 = "Brightwell borrowed engine mattered more than the title ever did."
    named = mg.motif_report(_draft([n1, _FILLER[0], n2]),
                            _proj(names=["Brightwell"]))
    if _tagged(named, "TIC-REPETITION"):
        return False, ("a repeated phrase carrying a character name was "
                       "reported as a tic: " + named["errors"][0][:220])
    if named["stats"]["name_source"].startswith("mid-sentence"):
        return False, "names.json was not read; the fallback ran instead"

    # ...and with no roster on disk the mid-sentence fallback must be SAID to
    # be a fallback, and must still catch a name used mid-sentence. A name
    # that always opens its sentence is the fallback's documented blind spot,
    # and this asserts that blind spot exists rather than pretending it does
    # not: the same draft fires without names.json.
    nofile = mg.motif_report(_draft([n1, _FILLER[0], n2]), _proj())
    if not nofile["stats"]["name_source"].startswith("mid-sentence"):
        return False, "the fallback was not used when names.json is absent"
    if not _tagged(nofile, "TIC-REPETITION"):
        return False, ("the fallback silently matched a sentence-initial "
                       "name, so its documented weakness is no longer real "
                       "and the comment is wrong")
    mid = mg.motif_report(
        _draft(["The kid watched Brightwell borrowed engine disappear.",
                _FILLER[0],
                "Nobody told Brightwell borrowed engine was already sold."]),
        _proj())
    if _tagged(mid, "TIC-REPETITION"):
        return False, ("the fallback failed to exempt a name used "
                       "mid-sentence, which is the one case it is for: "
                       + mid["errors"][0][:220])
    return True, ("a repeat inside quoted speech is exempt and the same words "
                  "unquoted still fire; a repeat carrying a names.json name "
                  "is exempt; with no names.json the mid-sentence fallback is "
                  "declared in stats, exempts a mid-sentence name and misses "
                  "a sentence-initial one exactly as documented")


# --------------------------------------------------------------------------- #
# the real drafts
# --------------------------------------------------------------------------- #
def test_real_draft_fails() -> tuple[bool, str]:
    """The overcorrected draft IS the defect and must stay caught."""
    if not FIX.exists():
        return False, f"the fixture {FIX.name} is missing"
    d = json.loads(FIX.read_text(encoding="utf-8-sig"))
    rep = mg.motif_report(d, PROJ)
    s = rep["stats"]
    for tag in ("MOTIF-BUDGET", "MOTIF-THESIS", "TIC-REPETITION"):
        if not _tagged(rep, tag):
            return False, (f"the overcorrected draft is NOT failed by [{tag}]; "
                           f"stats: {s.get('motif_lines')}, thesis "
                           f"{s.get('thesis_lines')}, repeats "
                           f"{s.get('repeated_ngrams')}")
    worst = max(s["motif_lines"].values()) if s["motif_lines"] else 0
    if worst <= config.MOTIF_LINES_MAX:
        return False, (f"the worst running bit touches {worst} lines, within "
                       f"the budget of {config.MOTIF_LINES_MAX} - the fixture "
                       f"no longer demonstrates the defect")
    if s["thesis_lines"] <= config.MOTIF_THESIS_MAX:
        return False, (f"{s['thesis_lines']} thesis statement(s) measured, "
                       f"within the budget of {config.MOTIF_THESIS_MAX}")
    if s["repeated_ngrams"] < 10:
        return False, (f"only {s['repeated_ngrams']} repeated phrase(s); the "
                       f"fixture was measured at 20")
    unused = [k for k, v in s["motif_lines"].items() if v == 0]
    if not unused:
        return False, ("no running bit is unused, so the zero-use warning is "
                       "not exercised by the real fixture")
    # MOTIF-ADJACENT does NOT fire here, and that is recorded rather than
    # worked around: the restatements in this draft are PARAPHRASE, and
    # content-word overlap cannot see paraphrase. Asserted so that the day
    # somebody lowers the cap to "catch" it, this test says what it costs.
    if _tagged(rep, "MOTIF-ADJACENT"):
        return False, (f"[MOTIF-ADJACENT] now fires on the overcorrected "
                       f"draft at {s['max_adjacent_overlap']} overlap; the "
                       f"module docstring says it cannot and must be updated")
    if s["max_adjacent_overlap"] > config.MOTIF_ADJACENT_OVERLAP_MAX:
        return False, "the adjacency stat contradicts the empty finding list"
    return True, (f"{len(rep['errors'])} error(s), {len(rep['warns'])} "
                  f"warning(s): worst bit {worst} lines (budget "
                  f"{config.MOTIF_LINES_MAX}), {len(unused)} bit(s) unused, "
                  f"{s['thesis_lines']} thesis statements (budget "
                  f"{config.MOTIF_THESIS_MAX}) at lines "
                  f"{s['thesis_line_ids']}, {s['repeated_ngrams']} repeated "
                  f"{config.TIC_NGRAM_N}-grams; adjacency peaks at "
                  f"{s['max_adjacent_overlap']} and does NOT fire - that "
                  f"paraphrase is outside this instrument")


def test_old_draft_separates() -> tuple[bool, str]:
    """The bars must distinguish overcorrection from the draft it replaced."""
    if not OLD.exists():
        return False, f"the fixture {OLD.name} is missing"
    old = mg.motif_report(json.loads(OLD.read_text(encoding="utf-8-sig")),
                          PROJ)
    new = mg.motif_report(json.loads(FIX.read_text(encoding="utf-8-sig")),
                          PROJ)
    if _tagged(old, "MOTIF-BUDGET"):
        return False, ("the pre-rewrite draft trips the motif budget, so the "
                       "budget is not measuring the overcorrection: "
                       + old["errors"][0][:200])
    if _tagged(old, "MOTIF-THESIS"):
        return False, ("the pre-rewrite draft trips the thesis gate: "
                       + old["errors"][0][:200])
    o, n = old["stats"]["repeated_ngrams"], new["stats"]["repeated_ngrams"]
    if not o < n:
        return False, (f"the pre-rewrite draft repeats {o} phrases and the "
                       f"overcorrected one {n}; the tic gate does not "
                       f"separate them")
    if o == 0:
        return False, ("the pre-rewrite draft repeats nothing at all, which "
                       "makes the comparison a comparison with zero rather "
                       "than evidence that the bar discriminates")
    return True, (f"pre-rewrite: 0 budget breaches, 0 thesis statements, {o} "
                  f"repeated phrases; overcorrected: {n} repeated phrases - "
                  f"the two gates aimed at overcorrection fire only on the "
                  f"overcorrected draft")


# --------------------------------------------------------------------------- #
# degradation
# --------------------------------------------------------------------------- #
def test_no_angle_is_a_note() -> tuple[bool, str]:
    """No angle.md is a NOTE. A new gate must not stop the old ones."""
    d = _proj()          # no angle.md written
    rep = mg.motif_report(_draft(_FILLER), d)
    if rep["errors"]:
        return False, (f"a project with no angle.md produced "
                       f"{len(rep['errors'])} error(s), which would stop "
                       f"every other gate in draft.py's list from running: "
                       + rep["errors"][0][:200])
    notes = _tagged(rep, "MOTIF-BUDGET", "notes")
    if not notes:
        return False, ("no angle.md produced no note either - the gate passed "
                       "silently, which is indistinguishable from a clean "
                       "draft")
    if "did not run" not in notes[0] and "not be measured" not in notes[0]:
        return False, f"the note does not say the gate did not run: {notes[0]}"
    # An angle.md that EXISTS with an empty section is a different thing and
    # must also be said, not assumed clean.
    empty = mg.motif_report(_draft(_FILLER), _proj(""))
    if empty["errors"]:
        return False, ("an empty RUNNING BITS section errors: "
                       + empty["errors"][0][:200])
    if not _tagged(empty, "MOTIF-BUDGET", "notes"):
        return False, "an empty RUNNING BITS section says nothing at all"
    if empty["stats"].get("motifs") != 0:
        return False, "the empty section was not measured as zero motifs"
    return True, ("no angle.md: 0 errors and a note saying the budget did not "
                  "run; an angle.md with an empty RUNNING BITS section: 0 "
                  "errors and a note saying the callbacks are unbudgeted")


def test_bars_come_from_config() -> tuple[bool, str]:
    """Move the constant and the verdict moves - no literals in the gate."""
    d = _proj(_bits_entry())
    draft = _draft(_bit_lines(6))
    base = mg.motif_report(draft, d)
    if not _tagged(base, "MOTIF-BUDGET"):
        return False, "the 6-line fixture does not fire at the shipped bar"
    saved = config.MOTIF_LINES_MAX
    try:
        config.MOTIF_LINES_MAX = 6
        loosened = mg.motif_report(draft, d)
    finally:
        config.MOTIF_LINES_MAX = saved
    if _tagged(loosened, "MOTIF-BUDGET"):
        return False, ("raising config.MOTIF_LINES_MAX to 6 did not clear the "
                       "6-line finding, so the gate carries its own literal "
                       "and config is decoration")

    th = _draft([_THESIS_A, _FILLER[0], _THESIS_B])
    saved_t = config.MOTIF_THESIS_MAX
    try:
        config.MOTIF_THESIS_MAX = 2
        loose_t = mg.motif_report(th, _proj())
    finally:
        config.MOTIF_THESIS_MAX = saved_t
    if _tagged(loose_t, "MOTIF-THESIS"):
        return False, "config.MOTIF_THESIS_MAX is not what the thesis gate reads"

    saved_n = config.TIC_NGRAM_MAX
    try:
        config.TIC_NGRAM_MAX = 2
        loose_n = mg.motif_report(_draft([_TIC_1, _FILLER[0], _TIC_2]),
                                  _proj())
    finally:
        config.TIC_NGRAM_MAX = saved_n
    if _tagged(loose_n, "TIC-REPETITION"):
        return False, "config.TIC_NGRAM_MAX is not what the tic gate reads"
    return True, ("MOTIF_LINES_MAX, MOTIF_THESIS_MAX and TIC_NGRAM_MAX each "
                  "change the verdict when moved, so all three bars are read "
                  "from config at call time")


def test_gate_never_raises() -> tuple[bool, str]:
    """Malformed input degrades to 'nothing was measured' and says so."""
    d = _proj(_bits_entry())
    cases = {
        "empty dict": {},
        "lines is None": {"lines": None},
        "lines is a dict": {"lines": {"1": "x"}},
        "no narration key": {"lines": [{"id": 1, "note": "B01"}]},
        "None in lines": {"lines": [None, {"id": 1, "narration": "a b c d"}]},
        "non-dict in lines": {"lines": [7, "x", {"narration": _THESIS_A}]},
        "no id": {"lines": [{"narration": _SAME_A}, {"narration": _SAME_B}]},
        "narration is None": {"lines": [{"id": 1, "narration": None}]},
    }
    for label, draft in cases.items():
        try:
            rep = mg.motif_report(draft, d)
        except Exception as e:
            return False, (f"{label} raised {type(e).__name__}: {e} - one "
                           f"exception stops every gate after this one")
        for k in ("errors", "warns", "notes", "stats"):
            if k not in rep:
                return False, f"{label} returned a report with no {k!r}"
        if any("could not run" in m for m in rep["errors"]):
            return False, (f"{label} fell through to the catch-all guard: "
                           + rep["errors"][0][:200])

    # the "no narration at all" case must SAY it measured nothing
    silent = mg.motif_report({"lines": [{"id": 1, "note": "B01"}]}, d)
    if not any("Nothing was checked" in n or "NOTHING was measured" in n
               for n in silent["notes"]):
        return False, ("a draft with no narration at all reports nothing and "
                       "says nothing, which reads as a clean draft")
    # ...and a draft with no `lines` key must not claim to have measured
    none = mg.motif_report({}, d)
    if none["errors"] or none["stats"].get("narrated_lines"):
        return False, "a draft with no lines list claims to have measured one"
    # an unreadable anchor for the id: lines without `id` still get located
    noid = mg.motif_report(
        {"lines": [{"narration": _SAME_A}, {"narration": _SAME_B}]}, _proj())
    errs = _tagged(noid, "MOTIF-ADJACENT")
    if not errs or "#0" not in errs[0]:
        return False, (f"lines with no `id` are reported without any way to "
                       f"find them: {errs}")
    return True, (f"{len(cases)} malformed drafts return a report instead of "
                  f"raising, a draft with no narration says so in a note, and "
                  f"findings on lines with no `id` are located by position")


TESTS = {
    "MOTIF-BUDGET-FIRES":     test_motif_budget_fires,
    "MOTIF-BUDGET-SILENT":    test_motif_budget_silent,
    "MOTIF-BUDGET-ZERO":      test_motif_budget_zero,
    "MOTIF-BUDGET-UNPARSED":  test_motif_budget_unparsed,
    "MOTIF-THESIS":           test_motif_thesis,
    "MOTIF-ADJACENT":         test_motif_adjacent,
    "TIC-REPETITION":         test_tic_repetition,
    "TIC-NAMES-AND-QUOTES":   test_tic_names_and_quotes,
    "REAL-DRAFT-FAILS":       test_real_draft_fails,
    "OLD-DRAFT-SEPARATES":    test_old_draft_separates,
    "NO-ANGLE-IS-A-NOTE":     test_no_angle_is_a_note,
    "BARS-COME-FROM-CONFIG":  test_bars_come_from_config,
    "GATE-NEVER-RAISES":      test_gate_never_raises,
}


def main() -> int:
    want = sys.argv[1:] or list(TESTS)
    bad = 0
    try:
        for name in want:
            fn = TESTS.get(name)
            if fn is None:
                print(f"?? no such test: {name}")
                continue
            try:
                ok, msg = fn()
            except Exception as e:
                import traceback
                traceback.print_exc()
                ok, msg = False, f"{type(e).__name__}: {e}"
            print(f'{"PASS" if ok else "FAIL"}  {name:<24} {msg}')
            bad += (not ok)
    finally:
        for d in _TMP:
            shutil.rmtree(d, ignore_errors=True)
    print("-" * 60)
    stem = Path(__file__).stem
    print(f"{stem}: all pass" if not bad else f"{stem}: {bad} FAILURE(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
