# -*- coding: utf-8 -*-
"""The CLOSING WINDOW gates - with the shipped draft's own ending as a fixture.

THE DEFECT, and the lines it lived on
-------------------------------------
projects/tokyodrift2006/draft.json, copied unmodified to
tools/fixtures/draft_tokyodrift_ending_bad.json, carries three wrong callbacks
in its last four narrated lines (ids 111-114 of 105 narrated lines):

  line 113  "the question Sean asked Han in a garage and never got answered:
            he doesn't drift to win." The quoted words are HAN's thesis, not
            Sean's question, and the scene is beat B58, which the beat map
            puts ON A ROOFTOP. Two contradictions in one clause.
  line 112  "The last stranger who pulled alongside this kid with something
            to teach him cost him a car he could never pay for." The stranger
            is Han, and angle.md's ATTITUDE TO CHARACTERS says of Han: "the
            one the narrator openly loves and quietly mourns ... The narrator
            is protective of him". The closer blames the character the card
            defends - and never names him, so the blame cannot be checked
            against the card at all.
  line 111  misreads which character is speaking in the scene.

Measured by pipeline/ending_gates.py on that fixture against
projects/tokyodrift2006 (2026-10-31):

    window                      ids 110, 111, 112, 113, 114
    attributions found          1 (line 113)
    statements indexed          28
    CALLBACK-ATTRIBUTION        2 findings on line 113 (kind + place)
    ENDING-PERSONA              1 finding on line 112 (unnamed blame)
    ENDING-READ                 1 error (no ending_read.md)
    protected characters        6 of 7 on the card

WHAT THIS SUITE PROVES, AND WHAT IT CANNOT
------------------------------------------
Both directions of every check, because a gate that only fires, or only stays
silent, is not tested at all. Two LIMITS are pinned here rather than papered
over, and each is reported in its case's pass message:

  * The speaker half of CALLBACK-ATTRIBUTION does NOT fire on the live draft,
    and it is correct not to. The draft's only earlier appearance of "he
    doesn't drift to win" is INSIDE Sean's own question about it (line 56,
    "So Sean asks it straight: ..."), so the content-signature index
    corroborates Sean as the speaker. The signature matcher cannot tell a
    thesis from a question about that thesis - they share their content words
    exactly. What catches the real line is the KIND signal (a question-noun
    introducing a declarative sentence) and the PLACE signal. The speaker
    mismatch is tested on a synthetic draft where the draft's own text
    disagrees, which is the case the index CAN decide.
  * line 111's misread speaker is not caught by any check here and is not
    claimed to be. The draft never quotes that scene's dialogue, so nothing in
    its text contradicts the line. That is what ENDING-READ is for, and why it
    is an ERROR when the artifact is missing rather than a warning.

Run:  python tools/test_ending_gates.py
      python tools/test_ending_gates.py REAL-DRAFT-FAILS
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
from pipeline import ending_gates as eg  # noqa: E402
from pipeline import review_artifacts as ra  # noqa: E402

PROJ = Path(config.project_dir("tokyodrift2006"))
FIX = Path(ROOT) / "tools" / "fixtures" / "draft_tokyodrift_ending_bad.json"

# The statement the synthetic drafts call back to. Ordinary English with no
# relation to any film: the film-specific assertions live in the fixture cases
# (REAL-DRAFT-FAILS) and nowhere else, which is the rule
# pipeline/ending_gates.py is written to.
QUOTE = "You make choices and you never look back."
_TMP: list = []


# ---- fixture builders ---------------------------------------------------- #
def _proj(angle: str | None = None, beats: str | None = None) -> Path:
    d = Path(tempfile.mkdtemp(prefix="ending_"))
    _TMP.append(d)
    if angle is not None:
        (d / "angle.md").write_text(angle, encoding="utf-8")
    if beats is not None:
        (d / "beats_proposal.md").write_text(beats, encoding="utf-8")
    return d


def _draft(texts: list) -> dict:
    """A draft from a list of narration strings, one line each, ids from 1."""
    return {"lines": [{"id": i, "note": f"B{i:02d}", "payload": "stake",
                       "narration": t, "delivery": "normal"}
                      for i, t in enumerate(texts, 1)]}


# Four lines of ordinary filler between the setup and the closer, so that with
# ENDING_WINDOW_LINES = 5 the SETUP sits outside the window and the closer
# sits inside it. Deliberately carrying no attribution, no place noun and no
# blame idiom - a filler line that tripped a check would make every case below
# unreadable.
FILLER = ["Time passes and the city keeps moving.",
          "Nothing much is decided for a while.",
          "The crowd thins out and the lights come up.",
          "Everyone goes home to think about it."]


def _window_draft(setup: str, closer: str) -> dict:
    return _draft([setup] + FILLER + [closer])


def _hits(rep: dict, gate: str, bucket: str = "errors") -> list:
    return [x for x in rep[bucket] if x.startswith(f"[{gate}]")]


def _artifact(draft: dict, ids: list, findings: list) -> str:
    """An ending_read.md signing `ids` with the draft's CURRENT signatures."""
    by = {ln["id"]: ln for ln in draft["lines"]}
    rows = "\n".join(
        f"  {i} {ra.line_signature(by[i]['narration'])}" for i in ids)
    find = "\n".join(findings) if findings else "ANSWERED | none | - | " + (
        "nothing to report, the closing window reads cleanly front to back")
    return ("# ending read\n\nProse outside the fences is ignored.\n\n"
            "```review-signatures\n" + rows + "\n```\n\n"
            "```review-findings\n" + find + "\n```\n")


# ---- 1. the speaker -------------------------------------------------------- #
def test_callback_speaker() -> tuple[bool, str]:
    """A closing line may not hand one character's words to another.

    Fixture: synthetic, because this is the case the content-signature index
    CAN decide - the draft's own earlier line names a different speaker for
    the same words. The live draft's version of this fault is invisible to the
    index and is caught by the KIND signal instead; see the module docstring.
    """
    p = _proj()
    bad = _window_draft(
        f'Han said: "{QUOTE}"',
        f'And that is where it ends, on the line Sean gave him: "{QUOTE}"')
    rep = eg.ending_report(bad, p)
    hit = _hits(rep, "CALLBACK-ATTRIBUTION")
    if not hit:
        return False, ("a closing line crediting Sean with words line 1 "
                       "credits to Han was not reported at all")
    msg = hit[0]
    for probe in ("Sean", "Han", "line 6", "line 1"):
        if probe not in msg:
            return False, (f"the finding does not name {probe!r} - it has to "
                           f"report both speakers and both line ids: "
                           f"{msg[:200]}")
    good = _window_draft(
        f'Han said: "{QUOTE}"',
        f'And that is where it ends, on the line Han gave him: "{QUOTE}"')
    rep2 = eg.ending_report(good, p)
    quiet = _hits(rep2, "CALLBACK-ATTRIBUTION")
    if quiet:
        return False, (f"the SAME draft with the correct speaker still fails, "
                       f"so the gate is not reading the attribution: "
                       f"{quiet[0][:200]}")
    if _hits(rep2, "CALLBACK-ATTRIBUTION", "warns"):
        return False, ("the correct callback came back as uncheckable, so the "
                       "content index did not match its own setup line")
    n = rep["stats"]["callback_errors"]
    return True, (f"wrong speaker fires and names both (Sean vs Han, lines 6 "
                  f"and 1; {n} finding(s)); the same draft with the right "
                  f"speaker is clean and not merely unmatched")


# ---- 2. the place ---------------------------------------------------------- #
def test_callback_place() -> tuple[bool, str]:
    """A callback may not relocate its own setup scene.

    Fixture: synthetic (the place is in the draft's own setup line); the real
    one is line 113 against beat B58, where the location comes from the beat
    map - that path is covered by REAL-DRAFT-FAILS.
    """
    p = _proj()
    setup = f'On the rooftop, Han said: "{QUOTE}"'
    bad = _window_draft(
        setup,
        f'And that is where it ends, on the line Han gave him in a garage: '
        f'"{QUOTE}"')
    hit = _hits(eg.ending_report(bad, p), "CALLBACK-ATTRIBUTION")
    if not hit:
        return False, ("a closing line that moves a rooftop conversation into "
                       "a garage was not reported")
    if "garage" not in hit[0] or "roof" not in hit[0]:
        return False, (f"the finding does not name both places: {hit[0][:200]}")
    right = _window_draft(
        setup,
        f'And that is where it ends, on the line Han gave him on the rooftop: '
        f'"{QUOTE}"')
    q1 = _hits(eg.ending_report(right, p), "CALLBACK-ATTRIBUTION")
    if q1:
        return False, (f"naming the SAME place as the setup still fails: "
                       f"{q1[0][:200]}")
    none = _window_draft(
        setup,
        f'And that is where it ends, on the line Han gave him: "{QUOTE}"')
    q2 = _hits(eg.ending_report(none, p), "CALLBACK-ATTRIBUTION")
    if q2:
        return False, (f"a closing line naming NO place fails; a place the "
                       f"line does not claim cannot contradict anything: "
                       f"{q2[0][:200]}")
    # the containment case: a sub-location of the setup's location agrees
    sch = _window_draft(
        f'In the classroom, Han said: "{QUOTE}"',
        f'And that is where it ends, on the line Han gave him at the school: '
        f'"{QUOTE}"')
    q3 = _hits(eg.ending_report(sch, p), "CALLBACK-ATTRIBUTION")
    if q3:
        return False, (f"a classroom inside a school was reported as a place "
                       f"contradiction: {q3[0][:200]}")
    return True, ("garage-vs-rooftop fires and names both; the same place is "
                  "clean; no place at all is clean; a classroom inside a "
                  "school is not a contradiction")


# ---- 3. a callback nobody can check -------------------------------------- #
def test_uncheckable_callback() -> tuple[bool, str]:
    """No earlier statement at all is a WARNING - it may be footage.

    Fixture: synthetic. There is no live example, which is itself worth
    recording: every callback in the shipped closer matched something.
    """
    p = _proj()
    d = _window_draft(
        f'Han said: "{QUOTE}"',
        'And that is where it ends, on the line Sean gave him: "The harbour '
        'freight terminal shuts before anyone arrives."')
    rep = eg.ending_report(d, p)
    err = _hits(rep, "CALLBACK-ATTRIBUTION")
    warn = _hits(rep, "CALLBACK-ATTRIBUTION", "warns")
    if err:
        return False, (f"a callback to something no earlier line says was "
                       f"reported as an ERROR; it may be a callback to "
                       f"footage: {err[0][:200]}")
    if not warn:
        return False, ("a callback matching no earlier statement produced "
                       "neither an error nor a warning - it passed silently, "
                       "which is the one outcome that is not allowed")
    if "UNCHECKABLE" not in warn[0].upper():
        return False, f"the warning does not say it is uncheckable: {warn[0]}"
    if rep["stats"]["callback_errors"] != 0:
        return False, (f"stats report {rep['stats']['callback_errors']} "
                       f"callback error(s) on the uncheckable draft")
    if rep["stats"]["callback_warns"] < 1:
        return False, "stats do not count the warning"
    return True, (f"an unmatched callback is a warning "
                  f"({rep['stats']['callback_warns']}) and not an error "
                  f"({rep['stats']['callback_errors']}), and says so")


# ---- 4. the attitude card ------------------------------------------------- #
_ANGLE_PROT = """# synthetic angle

## ATTITUDE TO CHARACTERS

- **Han** - the one the narrator openly loves and quietly mourns. The narrator
  is protective of him and refuses to reduce him to the mentor slot.
- **Takashi** - wary, never hated. A man whose pride is the whole of him.

## ANGLE

Something about a city.
"""
_ANGLE_NO_SECTION = """# synthetic angle

## ANGLE

Something about a city.
"""


def test_ending_persona() -> tuple[bool, str]:
    """A closing line may not blame a character the card defends.

    Fixture: synthetic for the NAMED case; the live one is line 112, which
    blames the protected character WITHOUT naming him and is caught by the
    unnamed-blame half (see REAL-DRAFT-FAILS).
    """
    p = _proj(angle=_ANGLE_PROT)
    bad = _window_draft(
        "A quiet night in the city.",
        "And that is where it ends: Han cost him a car he could never pay "
        "for.")
    hit = _hits(eg.ending_report(bad, p), "ENDING-PERSONA")
    if not hit:
        return False, ("blaming the character the card calls itself "
                       "protective of was not reported")
    msg = hit[0]
    if "protective of him" not in msg:
        return False, (f"the finding does not QUOTE the attitude line from "
                       f"angle.md, so the writer is told a contradiction "
                       f"exists instead of being shown it: {msg[:240]}")
    if "cost him a car he could never pay for" not in msg:
        return False, f"the finding does not quote the offending clause: {msg}"
    if "line 6" not in msg:
        return False, f"the finding does not name the line: {msg[:200]}"

    ok = _window_draft(
        "A quiet night in the city.",
        "And that is where it ends: Takashi cost him a car he could never pay "
        "for.")
    quiet = _hits(eg.ending_report(ok, p), "ENDING-PERSONA")
    if quiet:
        return False, (f"the same sentence about the character the card is "
                       f"WARY of also fires, so the gate is not reading the "
                       f"attitude: {quiet[0][:220]}")

    p2 = _proj(angle=_ANGLE_NO_SECTION)
    rep = eg.ending_report(bad, p2)
    if _hits(rep, "ENDING-PERSONA"):
        return False, ("an angle.md with no ATTITUDE TO CHARACTERS section "
                       "produced an ENDING-PERSONA error; it cannot be an "
                       "error, there is nothing to contradict")
    notes = _hits(rep, "ENDING-PERSONA", "notes")
    if not notes:
        return False, ("a missing ATTITUDE TO CHARACTERS section passed "
                       "SILENTLY - no error and no note. The check did not "
                       "run and nothing said so")
    if "DID NOT RUN" not in notes[0].upper():
        return False, f"the note does not say the check did not run: {notes[0]}"
    st = eg.ending_report(bad, p)["stats"]
    return True, (f"blaming the protected character fires and quotes both the "
                  f"card line and the clause; the same line about the wary "
                  f"one is clean (protected: "
                  f"{st['protected_characters']} of "
                  f"{len(st['attitude_characters'])} on the card); no "
                  f"section is a NOTE, not a pass")


# ---- 5. the required read ------------------------------------------------- #
def test_ending_read() -> tuple[bool, str]:
    """ending_read.md must exist, sign EVERY closing line, and be closed."""
    p = _proj()
    d = _window_draft("A quiet night in the city.",
                      "And that is where it ends, with the lights still on.")
    ids = [ln["id"] for ln in d["lines"]][-config.ENDING_WINDOW_LINES:]

    rep = eg.ending_report(d, p)
    miss = _hits(rep, "ENDING-READ")
    if not miss:
        return False, "a missing ending_read.md was not an error"
    if "ending_read.md" not in miss[0] or "DID NOT write the draft" not in \
            miss[0]:
        return False, (f"the missing-artifact error does not name the path and "
                       f"say who must write it: {miss[0][:240]}")

    # fully signed, findings closed -> clean, and SAYS so
    (p / "ending_read.md").write_text(_artifact(d, ids, []), encoding="utf-8")
    rep2 = eg.ending_report(d, p)
    if _hits(rep2, "ENDING-READ"):
        return False, (f"a complete, current, closed read still fails: "
                       f"{_hits(rep2, 'ENDING-READ')[0][:240]}")
    note = _hits(rep2, "ENDING-READ", "notes")
    if not note or "present and current" not in note[0]:
        return False, ("a passing read is invisible - there is no note saying "
                       "the closing window was read")

    # 4 of 5 -> error. The bar is 100%, not a percentage: 80% would pass any
    # coverage bar in this repo (REVIEW_SIGNATURE_MIN_COVERAGE is 0.95, and on
    # a 5-line window 4/5 = 80%).
    (p / "ending_read.md").write_text(_artifact(d, ids[:-1], []),
                                      encoding="utf-8")
    rep3 = eg.ending_report(d, p)
    part = _hits(rep3, "ENDING-READ")
    if not part:
        return False, (f"a read signing {len(ids) - 1} of {len(ids)} closing "
                       f"lines PASSED - that is 80%, which clears every "
                       f"percentage bar in this repo and leaves the closer "
                       f"itself unread")
    if "100%" not in part[0]:
        return False, f"the error does not state the 100% bar: {part[0][:240]}"
    if str(ids[-1]) not in part[0]:
        return False, (f"the error does not name the unsigned line "
                       f"{ids[-1]}: {part[0][:240]}")

    # a stale signature is as bad as a missing one
    (p / "ending_read.md").write_text(_artifact(d, ids, []), encoding="utf-8")
    d2 = json.loads(json.dumps(d))
    d2["lines"][-1]["narration"] = "And that is where it ends, in the dark."
    st = _hits(eg.ending_report(d2, p), "ENDING-READ")
    if not st or "EDITED" not in st[0]:
        return False, ("editing the last line after the read was signed did "
                       "not make the read stale")

    # an open FINDING -> error
    (p / "ending_read.md").write_text(
        _artifact(d, ids, ["FINDING | wrong-speaker | " + str(ids[-1])
                           + " | the closer credits the line to the wrong "
                             "man"]), encoding="utf-8")
    rep4 = eg.ending_report(d, p)
    op = _hits(rep4, "ENDING-READ")
    if not op or "UNRESOLVED" not in op[0]:
        return False, (f"an open FINDING in the read did not fail: "
                       f"{(op or ['<nothing>'])[0][:240]}")

    # ...and a thin ANSWERED closes nothing
    minw = int(getattr(config, "REVIEW_ANSWER_MIN_WORDS", 8))
    (p / "ending_read.md").write_text(
        _artifact(d, ids, [
            "FINDING | wrong-speaker | " + str(ids[-1])
            + " | the closer credits the line to the wrong man",
            "ANSWERED | wrong-speaker | " + str(ids[-1]) + " | no it does not",
        ]), encoding="utf-8")
    thin = _hits(eg.ending_report(d, p), "ENDING-READ")
    if not thin or not any(str(minw) in t for t in thin):
        return False, (f"a {minw}-word-floor ANSWERED of four words closed a "
                       f"finding: {(thin or ['<nothing>'])[0][:240]}")
    return True, (f"missing fires and names the path and the writer; complete "
                  f"and closed is clean with a note; {len(ids) - 1} of "
                  f"{len(ids)} signed fires and states the 100% bar; an edited "
                  f"line goes stale; an open FINDING and a sub-{minw}-word "
                  f"ANSWERED both fire")


# ---- 6. the real draft ---------------------------------------------------- #
def test_real_draft_fails() -> tuple[bool, str]:
    """THE DEFECT ITSELF, on a FROZEN copy of the draft that carried it.

    tools/fixtures/draft_tokyodrift_ending_bad.json was taken from
    projects/tokyodrift2006/draft.json while it still carried all three
    faults. If this case goes green, the gates stopped measuring - the
    fixture did not stop offending.

    The first version of this case asserted the fixture was byte-identical to
    the LIVE draft, to prove provenance. That assertion had to go: the live
    draft was then fixed, and the test failed for the one reason that is not
    a defect - the defect being repaired. A regression fixture pins the text
    it was written about and must NOT track the file being corrected; the
    same mistake once made two clip-duration cases measure new line ids
    against old audio. Provenance is pinned instead by asserting the fixture
    still contains the three offending closing lines.
    """
    if not FIX.exists():
        return False, f"the fixture {FIX.name} is missing"
    d = json.loads(FIX.read_text(encoding="utf-8-sig"))
    _by = {l.get("id"): str(l.get("narration") or "")
           for l in d.get("lines") or []}
    for _lid, _needle in ((113, "in a garage"),
                          (112, "cost him a car"),
                          (111, "in on it from the start")):
        if _needle not in _by.get(_lid, ""):
            return False, (f"the fixture no longer carries the defect it was "
                           f"frozen for: line {_lid} does not contain "
                           f"{_needle!r}. Do not re-point this fixture at a "
                           f"corrected draft - take a new one and keep this.")
    rep = eg.ending_report(d, PROJ)
    cb = _hits(rep, "CALLBACK-ATTRIBUTION")
    pers = _hits(rep, "ENDING-PERSONA")
    if not cb:
        return False, ("CALLBACK-ATTRIBUTION does not fire on the shipped "
                       "ending; line 113's callback is the defect")
    if not pers:
        return False, ("ENDING-PERSONA does not fire on the shipped ending; "
                       "line 112 blames the character the card defends")
    want_cb = {
        "line 113": "the offending line id",
        "garage": "the place the closer claims",
        "roof": "the place the setup actually is",
        "beat B58": "where the location was read from",
        "STATEMENT, not a question": "the kind mismatch",
    }
    bad = [f"{k} ({v})" for k, v in want_cb.items() if k not in cb[0]]
    if bad:
        return False, f"the CALLBACK finding does not report: {bad}"
    for probe in ("line 112", "cost him", "never names"):
        if probe not in pers[0]:
            return False, (f"the ENDING-PERSONA finding does not report "
                           f"{probe!r}: {pers[0][:240]}")
    s = rep["stats"]
    if s["window_ids"] != [110, 111, 112, 113, 114]:
        return False, (f"the closing window is {s['window_ids']}, not the "
                       f"final four lines plus the outro that the defect "
                       f"lives on")
    # NO ENDING-READ ASSERTION HERE, deliberately.
    #
    # This case is about the frozen draft's TEXT. Whether the live project
    # happens to have an ending_read.md on disk is a fact about the project's
    # workflow state, not about the fixture, and asserting it made this case
    # fail the moment the review was actually produced - the second time a
    # stale assertion in this file broke for the one reason that is not a
    # defect. ENDING-READ's own case covers both directions, against temp
    # projects it controls.
    _ = _hits(rep, "ENDING-READ")
    # The LIMIT, measured and reported rather than asserted: the speaker half
    # is silent here, and the module docstring says why.
    # "attributes the same words to" is the speaker finding's own wording; the
    # gate's closing instruction also contains the phrase "names the wrong
    # speaker", and matching THAT counted the advice as a finding.
    spk = [x for x in cb if "attributes the same words to" in x]
    return True, (f"{len(rep['errors'])} error(s) on the unmodified shipped "
                  f"draft: CALLBACK-ATTRIBUTION {s['callback_errors']} on line "
                  f"113 (kind + place: garage vs the rooftop of beat B58), "
                  f"ENDING-PERSONA {s['persona_errors']} on line 112 "
                  f"(unnamed blame, {len(s['protected_characters'])} of "
                  f"{len(s['attitude_characters'])} characters protected), "
                  f"ENDING-READ {s['ending_read_errors']}; "
                  f"{s['statements_indexed']} statements indexed, "
                  f"{len(s['attributions'])} attribution(s) in the window. "
                  f"The speaker signal is silent "
                  f"({len(spk)} finding(s)) and correctly so - line 56 quotes "
                  f"those words inside Sean's own question")


# ---- 7. the gate never raises --------------------------------------------- #
def test_gate_never_raises() -> tuple[bool, str]:
    """Malformed input degrades to a stated failure, never to a silent pass."""
    p = _proj()
    cases = [
        ("empty draft", {"lines": []}),
        ("no lines key", {}),
        ("lines is not a list", {"lines": "nope"}),
        ("non-dict line records", {"lines": [1, "two", None]}),
        ("lines with no keys", {"lines": [{}, {}]}),
        ("narration is not a string", {"lines": [{"id": 1, "narration": 42}]}),
        ("draft is not a dict", "not a draft"),
        ("draft is None", None),
        ("one line, all defects", _draft(
            ["And that is where it ends, on the question Sean asked Han in a "
             "garage: he doesn't drift to win."])),
    ]
    out = []
    for name, draft in cases:
        try:
            rep = eg.ending_report(draft, p)
        except Exception as e:
            return False, (f"{name} RAISED {type(e).__name__}: {e} - a gate "
                           f"that dies hands the caller an empty report, and "
                           f"an empty report is read as a pass")
        for k in ("errors", "warns", "notes", "stats"):
            if k not in rep:
                return False, f"{name}: the report has no {k!r}"
        if not (rep["errors"] or rep["warns"] or rep["notes"]):
            return False, (f"{name} produced a COMPLETELY EMPTY report, which "
                           f"every caller in this repo reads as a pass")
        out.append(f"{name}={len(rep['errors'])}E/{len(rep['notes'])}N")

    # a missing project directory entirely
    gone = Path(tempfile.mkdtemp(prefix="ending_gone_")) / "nope"
    rep = eg.ending_report(_draft(["A line."]), gone)
    if not rep["errors"]:
        return False, ("a project directory that does not exist produced no "
                       "errors at all")
    # an unreadable angle.md and a junk artifact
    p2 = _proj(angle="\x00\xff not a document at all")
    (p2 / "ending_read.md").write_bytes(b"\x00\x01\x02 garbage \xff\xfe")
    rep2 = eg.ending_report(_draft(["A line."]), p2)
    if not _hits(rep2, "ENDING-READ"):
        return False, "a binary ending_read.md was accepted as a read"
    return True, ("9 malformed drafts, a missing project dir, a junk angle.md "
                  "and a binary artifact all come back as reports: "
                  + ", ".join(out[:5]) + f" (+{len(out) - 5} more)")


# ---- 8. the bars are read from config ------------------------------------- #
def test_bars_from_config() -> tuple[bool, str]:
    """Move a constant and the verdict on the SAME draft must move with it."""
    p = _proj(angle=_ANGLE_PROT)
    d = _draft([f'Han said: "{QUOTE}"'] + FILLER
               + [f'And that is where it ends, on the line Sean gave him: '
                  f'"{QUOTE}"',
                  "A last quiet line over the credits."])
    base = _hits(eg.ending_report(d, p), "CALLBACK-ATTRIBUTION")
    if not base:
        return False, "the baseline draft does not fire at all"

    # ENDING_WINDOW_LINES: shrink the window past the offending line and the
    # finding must disappear - proof the window is the window.
    old = config.ENDING_WINDOW_LINES
    try:
        config.ENDING_WINDOW_LINES = 1
        shrunk = eg.ending_report(d, p)
    finally:
        config.ENDING_WINDOW_LINES = old
    if _hits(shrunk, "CALLBACK-ATTRIBUTION"):
        return False, ("setting config.ENDING_WINDOW_LINES = 1 left the "
                       "finding on the second-to-last line in place - the "
                       "window is not read from config at call time")
    if shrunk["stats"]["window_ids"] != [d["lines"][-1]["id"]]:
        return False, (f"the window did not shrink: "
                       f"{shrunk['stats']['window_ids']}")
    if not _hits(eg.ending_report(d, p), "CALLBACK-ATTRIBUTION"):
        return False, "restoring the constant did not restore the verdict"

    # ENDING_CALLBACK_MATCH_MIN: raise it above 1.0 and no callback can match,
    # so the speaker finding becomes an uncheckable WARNING.
    oldm = config.ENDING_CALLBACK_MATCH_MIN
    try:
        config.ENDING_CALLBACK_MATCH_MIN = 1.01
        strict = eg.ending_report(d, p)
    finally:
        config.ENDING_CALLBACK_MATCH_MIN = oldm
    if _hits(strict, "CALLBACK-ATTRIBUTION"):
        return False, ("an unreachable match floor still produced a speaker "
                       "contradiction, so the overlap bar is not read from "
                       "config")
    if not _hits(strict, "CALLBACK-ATTRIBUTION", "warns"):
        return False, ("with no match possible the callback passed silently "
                       "instead of becoming uncheckable")

    # ENDING_BLAME_WINDOW_WORDS: the live defect sits 16 words from its
    # marker, which is why the proximity rule is not what catches it. Prove
    # the window is real on a synthetic line.
    far = _draft(FILLER + [
        "Han walked away from all of it, and nobody in that whole crowd of "
        "borrowed cars and borrowed money ever said a word, which cost him a "
        "car he could never pay for."])
    oldb = config.ENDING_BLAME_WINDOW_WORDS
    try:
        config.ENDING_BLAME_WINDOW_WORDS = 40
        wide = _hits(eg.ending_report(far, p), "ENDING-PERSONA")
        config.ENDING_BLAME_WINDOW_WORDS = 3
        tight = _hits(eg.ending_report(far, p), "ENDING-PERSONA")
    finally:
        config.ENDING_BLAME_WINDOW_WORDS = oldb
    if not wide:
        return False, ("a 40-word blame window did not reach a name 25 words "
                       "from its marker")
    if not any("blames Han" in w for w in wide):
        return False, f"the wide-window finding does not name Han: {wide[0]}"
    if tight and any("blames Han" in t for t in tight):
        return False, ("a 3-word blame window still paired a name 25 words "
                       "away with the marker")
    return True, ("ENDING_WINDOW_LINES, ENDING_CALLBACK_MATCH_MIN and "
                  "ENDING_BLAME_WINDOW_WORDS each move the verdict on the "
                  "same draft when moved, and restore it when restored")


# ---- 9. nothing else was broken ------------------------------------------- #
def test_module_is_film_agnostic() -> tuple[bool, str]:
    """The gate must carry no knowledge of the film it was written for.

    NOT a regex over the module's own source - that would pass by renaming a
    string. The claim is tested by BEHAVIOUR: the same synthetic defect is
    detected in a project whose characters, places and quotations have nothing
    to do with the live one, with no angle.md section names changed.
    """
    angle = """# another film

## ATTITUDE TO CHARACTERS

- **Marguerite** - the narrator is openly protective of her and will not have
  her treated as a fool.
- **Ortega** - wary. A man who counts other people's money.

## ANGLE

A different film entirely.
"""
    beats = ("B01 | 00:01:00 | On the harbour pier Marguerite tells the boy "
             "that a debt is a promise with a date on it | Marguerite, the "
             "boy | dialogue\n")
    p = _proj(angle=angle, beats=beats)
    d = {"lines": [
        {"id": 1, "note": "B01", "narration":
            'Marguerite said: "A debt is a promise with a date on it."'}]
        + [{"id": i + 2, "note": f"B{i + 2:02d}", "narration": t}
           for i, t in enumerate(FILLER)]
        + [{"id": 6, "note": "B06", "narration":
            'And that is where it ends, on the question Ortega asked her in a '
            'casino: "A debt is a promise with a date on it."'},
           {"id": 7, "note": "B07", "narration":
            "Marguerite ruined every one of them in the end."}]}
    rep = eg.ending_report(d, p)
    cb = _hits(rep, "CALLBACK-ATTRIBUTION")
    pe = _hits(rep, "ENDING-PERSONA")
    if not cb:
        return False, "the same defect in a different film is not detected"
    for probe in ("Ortega", "Marguerite", "casino", "pier"):
        if probe not in cb[0]:
            return False, (f"the finding does not name {probe!r} in the other "
                           f"film: {cb[0][:260]}")
    if not pe or "protective of her" not in pe[0]:
        return False, (f"the attitude contradiction in the other film is not "
                       f"reported with its own card line: "
                       f"{(pe or ['<nothing>'])[0][:240]}")
    return True, ("a different film's wrong speaker (Ortega vs Marguerite), "
                  "wrong place (casino vs the pier from its own beat map) and "
                  "blamed protected character are all caught with no change "
                  "to the module")


TESTS = {
    "CALLBACK-SPEAKER":      test_callback_speaker,
    "CALLBACK-PLACE":        test_callback_place,
    "UNCHECKABLE-CALLBACK":  test_uncheckable_callback,
    "ENDING-PERSONA":        test_ending_persona,
    "ENDING-READ":           test_ending_read,
    "REAL-DRAFT-FAILS":      test_real_draft_fails,
    "GATE-NEVER-RAISES":     test_gate_never_raises,
    "BARS-FROM-CONFIG":      test_bars_from_config,
    "FILM-AGNOSTIC":         test_module_is_film_agnostic,
}


def main(argv: list | None = None) -> int:
    want = list(argv or sys.argv[1:]) or list(TESTS)
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
            print(f'{"PASS" if ok else "FAIL"}  {name:<22} {msg}')
            bad += (not ok)
    finally:
        for d in _TMP:
            shutil.rmtree(d, ignore_errors=True)
    print("-" * 60)
    print("test_ending_gates: all pass" if not bad else
          f"test_ending_gates: {bad} FAILURE(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
