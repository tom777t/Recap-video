# -*- coding: utf-8 -*-
"""The cold-read and reviewer gates - both directions on every rule.

THE DEFECT THESE GATES EXIST FOR
--------------------------------
A human reviewer found three things on a finished draft that every automated
gate had passed: a line referring to a confrontation whose beat had been cut
from the draft; two pronouns with more than one possible antecedent, one of
which read as a death that had not happened; and a narrator claim about what a
character repeatedly said, which appears in no transcript line and no beat.
None is findable by a text rule. All three need a fresh reader. So the review
is a required ARTIFACT, and these tests check the gate that enforces it.

A gate is only worth having if it fails the bad case AND passes the good one,
so every rule below is tested in both directions. The ones that matter most
are the boundary (COVERAGE-BOUNDARY: exactly at the bar passes, one line below
fails) and NEVER-RAISES, because a gate that throws hands its caller an empty
report and every caller in this repo reads an empty report as a pass.

Cases
-----
  MISSING-ARTIFACT      no cold_read.md -> error naming the path and who writes it
  CLEAN-PASSES          present, signed, closed -> no error and a visible NOTE
  UNSIGNED-IS-STALE     a file with no signature block -> error saying "stale"
  STALE-AFTER-EDIT      edit one signed line -> error naming that id, coverage drops
  COVERAGE-BOUNDARY     19/20 passes at 0.95, 18/20 fails - the bar itself
  FINDING-UNRESOLVED    an open FINDING -> error; FINDING+RESOLVED -> clean
  ANSWERED-NEEDS-REASON 10 words closes it, 3 words does not
  MALFORMED-REFUSED     3 fields / bad status / prose in the fence -> named error
  SIGNATURE-SEMANTICS   whitespace- and case-insensitive, one-word-edit sensitive
  NEVER-RAISES          malformed drafts and artifacts still produce a report
  CONFIG-DRIVEN         moving the coverage bar moves the verdict at call time

Run:  python tools/test_review_artifacts.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config                                           # noqa: E402
from pipeline import review_artifacts as ra             # noqa: E402

# Film-specific wording lives HERE and only here: the two modules under test
# carry no film title and no character name, so they cannot be tuned to one
# film by accident. These sentences are invented for the fixtures.
NARRATION = [
    "A kid who only knows how to crash gets shipped to the one city where "
    "the whole game is a control he has not got.",
    "He owes a stranger a car before he has learned to turn a corner.",
    "The uncle calls it a loan and means it as a leash.",
    "Nobody in this garage believes he will last a week.",
    "The first run ends with the bumper in a planter box.",
    "His teacher is the man he borrowed the car from, which is the joke.",
    "They practise in a car park at four in the morning.",
    "He stops fighting the wheel and starts listening to it.",
    "The rival wins every race and loses every room he walks into.",
    "A girl who has seen this before tells him the truth for free.",
    "The debt comes due in front of everyone who matters.",
    "He hands over the keys and keeps the lesson.",
    "The second run is slower and it is the first one that counts.",
    "An old man watches from a doorway and says nothing at all.",
    "The garage splits down the middle over a car nobody owns.",
    "He learns the city by losing to it twice.",
    "The last race is decided on a mountain in the dark.",
    "He does not drift to win; he drifts because he finally can.",
    "The man he owed is the one who signs off on him.",
    "The city keeps going and he is in it now, which is the whole prize.",
]


# ---- fixture builders ---------------------------------------------------- #

def _draft(n: int = 20) -> dict:
    """A synthetic draft: n narrated lines, ids 1..n, plus one film-audio unit.

    The silent unit is deliberate. It must NOT be in the coverage denominator -
    a reader cannot review text that does not exist - and the first version of
    the gate counted it, which capped coverage at 20/21 = 0.952 and put every
    draft carrying film audio permanently within one edit of the bar.
    """
    lines = [{"id": i + 1, "note": f"B{i:02d}", "delivery": "normal",
              "payload": "stake", "narration": NARRATION[i % len(NARRATION)]}
             for i in range(n)]
    lines.append({"id": n + 1, "note": "B99", "delivery": "normal",
                  "narration": ""})
    return {"title": "Fixture Film (2006)", "target_minutes": 8,
            "lines": lines}


def _proj() -> Path:
    return Path(tempfile.mkdtemp(prefix="revart_"))


def _sig_block(draft: dict, skip: set = frozenset()) -> str:
    rows = [f"  {lid} {sig}"
            for lid, sig in ra.draft_signatures(draft).items()
            if lid not in {str(s) for s in skip}]
    return "```review-signatures\n" + "\n".join(rows) + "\n```"


def _write(pdir: Path, name: str, draft: dict, findings: str = "",
           skip: set = frozenset(), sig: bool = True) -> Path:
    body = ["Cold read of the draft. Read once, top to bottom.", ""]
    if sig:
        body += [_sig_block(draft, skip), ""]
    body += ["```review-findings", findings.strip(), "```", ""]
    p = pdir / name
    p.write_text("\n".join(body), encoding="utf-8")
    return p


def _full(pdir: Path, draft: dict, findings: str = "", skip: set = frozenset(),
          sig: bool = True) -> None:
    """Both artifacts, so a test about one of them is not failed by the other."""
    _write(pdir, "cold_read.md", draft, findings, skip, sig)
    _write(pdir, "review.md", draft, findings, skip, sig)


def _errs(rep: dict, gate: str = "") -> list:
    return [e for e in rep["errors"] if gate in e]


# ---- 1. missing ---------------------------------------------------------- #

def test_missing_artifact() -> tuple[bool, str]:
    d = _draft()
    p = _proj()
    try:
        rep = ra.review_report(d, p)
        cold = _errs(rep, "[COLD-READ]")
        rev = _errs(rep, "[REVIEWER]")
        if not cold or not rev:
            return False, (f"a project with no artifacts produced "
                           f"{len(cold)} COLD-READ and {len(rev)} REVIEWER "
                           f"error(s); both must be required")
        blob = " ".join(cold)
        if "cold_read.md" not in blob:
            return False, "the error does not name the file"
        if "did not write the draft" not in blob:
            return False, ("the error does not say WHO must write it, so the "
                           "remedy is not in the message")
        if str(p) not in blob and p.name not in blob:
            return False, "the error does not name the path"
        return True, (f"no artifacts -> {len(cold)} COLD-READ + {len(rev)} "
                      f"REVIEWER error(s), naming the path and the writer")
    finally:
        shutil.rmtree(p, ignore_errors=True)


# ---- 2. the good case passes, and says so -------------------------------- #

def test_clean_passes() -> tuple[bool, str]:
    d = _draft()
    p = _proj()
    try:
        _full(p, d,
              "FINDING  | dangling-ref | 3 | the leash is never set up\n"
              "RESOLVED | dangling-ref | 3 | line 3 was rewritten to "
              "introduce it")
        rep = ra.review_report(d, p)
        if rep["errors"]:
            return False, ("a signed, current, closed review still errored: "
                           + rep["errors"][0][:160])
        notes = " ".join(rep["notes"])
        if "[COLD-READ]" not in notes or "[REVIEWER]" not in notes:
            return False, (f"a passing review produced no NOTE for both "
                           f"artifacts, so it is silent: {rep['notes']}")
        if "100%" not in notes:
            return False, f"the NOTE does not state the coverage: {notes[:120]}"
        st = rep["stats"]["cold_read"]
        if st["coverage"] != 1.0 or st["resolved"] != 1 or st["findings"] != 1:
            return False, (f"stats wrong: coverage={st['coverage']}, "
                           f"findings={st['findings']}, "
                           f"resolved={st['resolved']}")
        return True, (f"signed 20/20 (coverage {st['coverage']:.0%}), 1 "
                      f"finding, 1 resolved -> 0 errors and "
                      f"{len(rep['notes'])} visible NOTE(s)")
    finally:
        shutil.rmtree(p, ignore_errors=True)


# ---- 3. unsigned is treated as stale ------------------------------------- #

def test_unsigned_is_stale() -> tuple[bool, str]:
    d = _draft()
    p = _proj()
    try:
        _full(p, d, sig=False)
        rep = ra.review_report(d, p)
        cold = _errs(rep, "[COLD-READ]")
        if not cold:
            return False, ("an artifact with no review-signatures block "
                           "passed; an unsigned review is unfalsifiable")
        blob = " ".join(cold).lower()
        if "stale" not in blob:
            return False, (f"the error does not say the file is treated as "
                           f"STALE rather than missing: {cold[0][:140]}")
        if "review-signatures" not in blob:
            return False, "the error does not name the missing block"
        st = rep["stats"]["cold_read"]
        if st["signed"] or st["signed_lines"]:
            return False, f"stats claim it is signed: {st}"
        # an EMPTY block must read the same way as no block at all
        (p / "cold_read.md").write_text(
            "prose\n\n```review-signatures\n```\n", encoding="utf-8")
        rep2 = ra.review_report(d, p)
        if "stale" not in " ".join(_errs(rep2, "[COLD-READ]")).lower():
            return False, "an EMPTY signature block was accepted"
        return True, ("no block and an empty block both error as STALE, not "
                      "as missing; stats report signed=False, 0 line(s)")
    finally:
        shutil.rmtree(p, ignore_errors=True)


# ---- 4. stale after an edit ---------------------------------------------- #

def test_stale_after_edit() -> tuple[bool, str]:
    """Sign the draft, then change one line's words. Same ids, same count.

    TEN narrated lines, not twenty, and the reason is the arithmetic: at a 0.95
    bar, ONE changed line out of twenty is coverage 0.9500 - exactly AT the bar
    and therefore a PASS. The first version of this test used a 20-line draft,
    edited one line, and failed; the gate was right and the test was wrong. The
    standing consequence is worth knowing: on a draft of 20 or more narrated
    lines a single edited line does not, on its own, trip staleness. That is
    what a 95% bar means, and COVERAGE-BOUNDARY is the test that pins it.
    """
    d = _draft(10)
    p = _proj()
    try:
        _full(p, d)
        before = ra.review_report(d, p)
        if before["errors"]:
            return False, ("the baseline was not clean: "
                           + before["errors"][0][:120])
        import copy
        e = copy.deepcopy(d)
        e["lines"][6]["narration"] = ("They practise in an empty lot at four "
                                      "in the morning.")
        rep = ra.review_report(e, p)
        cold = _errs(rep, "[COLD-READ]")
        if not cold:
            return False, ("editing a signed line did not trip staleness - "
                           "the artifact now describes text that is gone")
        blob = " ".join(cold)
        if " 7" not in blob and "7," not in blob and "7." not in blob:
            return False, f"the error does not name line 7: {blob[:160]}"
        if "EDITED" not in blob:
            return False, "the error does not say the line was edited"
        if "re-run" not in blob.lower():
            return False, "the error does not say to re-run the review"
        st = rep["stats"]["cold_read"]
        if st["changed_ids"] != ["7"]:
            return False, f"changed_ids is {st['changed_ids']}, want ['7']"
        bar = config.REVIEW_SIGNATURE_MIN_COVERAGE
        if not st["coverage"] < bar:
            return False, (f"coverage {st['coverage']:.3f} did not drop below "
                           f"the bar {bar}, so the error came from somewhere "
                           f"else")
        return True, (f"one word changed in line 7: coverage "
                      f"{before['stats']['cold_read']['coverage']:.2f} -> "
                      f"{st['coverage']:.2f} (bar {bar}), changed_ids="
                      f"{st['changed_ids']}, id named in the message")
    finally:
        shutil.rmtree(p, ignore_errors=True)


def test_fixing_findings_is_not_staleness() -> tuple[bool, str]:
    """A thorough review must not make itself stale by being acted on.

    Found by using the gate: a cold read produced 128 findings, fixing them
    edited 20 of 105 lines, and coverage fell to 81% against a 95% bar. The
    gate punished exactly the behaviour it exists to produce - review
    carefully, then fix nothing, was the only way to pass. A line the review
    NAMED and whose fix it RECORDS is still described by that review.

    The other direction is the same fixture with the resolutions removed, so
    this cannot pass by simply ignoring changed lines.
    """
    import copy
    n = 20
    d = _draft(n)
    p = _proj()
    try:
        _full(p, d)
        e = copy.deepcopy(d)
        hit = [3, 5, 7, 9, 11, 13]          # 6 of 20 = 70% raw coverage
        for i in hit:
            e["lines"][i - 1]["narration"] = f"Rewritten line number {i} here."

        # (a) resolutions present -> clean
        ids = ",".join(str(i) for i in hit)
        _full(p, d, findings=(
            f"FINDING | confusing | {ids} | these lines did not read clearly\n"
            f"RESOLVED | confusing | {ids} | each one rewritten to name its "
            f"subject plainly"))
        rep = ra.review_report(e, p)
        st = rep["stats"]["cold_read"]
        if _errs(rep, "[COLD-READ]"):
            return False, ("fixing what the review found was treated as "
                           "staleness: "
                           + _errs(rep, "[COLD-READ]")[0][:150])
        if st["coverage"] < config.REVIEW_SIGNATURE_MIN_COVERAGE:
            return False, (f"coverage {st['coverage']:.2f} still below the "
                           f"bar after accounting")
        if sorted(st.get("accounted_changed_ids") or []) != sorted(
                str(i) for i in hit):
            return False, (f"accounted_changed_ids is "
                           f"{st.get('accounted_changed_ids')}")

        # (b) same edits, resolutions removed -> must fail
        _full(p, d)
        rep2 = ra.review_report(e, p)
        st2 = rep2["stats"]["cold_read"]
        if not _errs(rep2, "[COLD-READ]"):
            return False, ("the same 6 edits with NO resolutions passed - the "
                           "exemption is unconditional, which defeats it")
        if st2["coverage"] >= config.REVIEW_SIGNATURE_MIN_COVERAGE:
            return False, (f"unaccounted coverage {st2['coverage']:.2f} did "
                           f"not drop below the bar")
        return True, (f"6 of {n} lines rewritten: with the fixes recorded as "
                      f"resolved, coverage is {st['coverage']:.0%} and clean; "
                      f"with the resolutions removed it is "
                      f"{st2['coverage']:.0%} and fails")
    finally:
        shutil.rmtree(p, ignore_errors=True)


def test_silent_edit_beats_the_percentage() -> tuple[bool, str]:
    """An edit nobody reviewed fails even when coverage is comfortably high.

    The percentage bar alone cannot catch this and the arithmetic says so: on
    a 40-line draft a single rewritten line is 97.5% coverage, which clears a
    95% bar. But an edit made IN RESPONSE to a finding is legitimate, and
    re-reviewing after every such edit would never terminate - so the rule is
    not "no edits", it is "no edits nobody accounted for". Both halves are
    checked here, because a rule that only ever fires is as useless as one
    that never does.
    """
    import copy
    d = _draft(40)
    p = _proj()
    try:
        _full(p, d)
        if ra.review_report(d, p)["errors"]:
            return False, "the baseline was not clean"

        e = copy.deepcopy(d)
        e["lines"][11]["narration"] = "He signs the paper without reading it."
        rep = ra.review_report(e, p)
        st = rep["stats"]["cold_read"]
        cov = st["coverage"]
        if cov < config.REVIEW_SIGNATURE_MIN_COVERAGE:
            return False, (f"coverage {cov:.3f} fell below the bar, so this "
                           f"case is not testing what it claims to")
        cold = _errs(rep, "[COLD-READ]")
        if not cold:
            return False, (f"a line was rewritten after the review and "
                           f"nothing fired - coverage {cov:.1%} cleared the "
                           f"bar and the edit went unnoticed")
        if "12" not in " ".join(cold):
            return False, f"the error does not name line 12: {cold[0][:150]}"

        # ...and the same edit, recorded as a finding that was resolved, is
        # accounted for and must NOT fire.
        _full(p, d, findings=(
            "FINDING | ambiguous-pronoun | 12 | two possible antecedents\n"
            "RESOLVED | ambiguous-pronoun | 12 | rewritten to name him"))
        rep2 = ra.review_report(e, p)
        if _errs(rep2, "[COLD-READ]"):
            return False, ("an edit named in a resolved finding still fired: "
                           + _errs(rep2, "[COLD-READ]")[0][:140])
        return True, (f"1 of 40 lines rewritten = {cov:.1%} coverage, which "
                      f"clears the {config.REVIEW_SIGNATURE_MIN_COVERAGE:.0%} "
                      f"bar, and the silent edit is still caught and named; "
                      f"the same edit recorded as a resolved finding is clean")
    finally:
        shutil.rmtree(p, ignore_errors=True)


# ---- 5. the boundary ----------------------------------------------------- #

def test_coverage_boundary() -> tuple[bool, str]:
    """19/20 = 0.95 passes, 18/20 = 0.90 fails. The bar is the bar."""
    d = _draft(20)
    bar = config.REVIEW_SIGNATURE_MIN_COVERAGE
    if abs(bar - 0.95) > 1e-9:
        return False, (f"this test is written for a 0.95 bar; config says "
                       f"{bar}, so the boundary arithmetic below is wrong")
    p = _proj()
    try:
        _full(p, d, skip={20})
        at = ra.review_report(d, p)
        at_cov = at["stats"]["cold_read"]["coverage"]
        if _errs(at, "[COLD-READ]"):
            return False, (f"coverage {at_cov:.4f} EXACTLY at the bar {bar} "
                           f"failed; the bar is unreachable by one line: "
                           + _errs(at, "[COLD-READ]")[0][:120])
        _full(p, d, skip={19, 20})
        below = ra.review_report(d, p)
        lo = below["stats"]["cold_read"]["coverage"]
        if not _errs(below, "[COLD-READ]"):
            return False, (f"coverage {lo:.4f}, below the bar {bar}, still "
                           f"passed")
        blob = " ".join(_errs(below, "[COLD-READ]"))
        if "never" not in blob or "signed" not in blob:
            return False, (f"the sub-bar error does not distinguish unsigned "
                           f"lines from edited ones: {blob[:140]}")
        return True, (f"19/20 = {at_cov:.4f} passes at the bar {bar}; "
                      f"18/20 = {lo:.4f} fails and names the unsigned ids")
    finally:
        shutil.rmtree(p, ignore_errors=True)


# ---- 6. findings must be closed ------------------------------------------ #

def test_finding_unresolved() -> tuple[bool, str]:
    d = _draft()
    p = _proj()
    try:
        open_only = ("FINDING | ambiguous-pronoun | 18 | \"he\" could be "
                     "either man named in line 17")
        _full(p, d, open_only)
        rep = ra.review_report(d, p)
        cold = _errs(rep, "[COLD-READ]")
        if not cold:
            return False, "an open FINDING passed the gate"
        blob = " ".join(cold)
        if "UNRESOLVED" not in blob:
            return False, f"the error does not say UNRESOLVED: {blob[:120]}"
        if "ambiguous-pronoun" not in blob or "18" not in blob:
            return False, (f"the error names neither the kind nor the line "
                           f"id: {blob[:140]}")
        if rep["stats"]["cold_read"]["unresolved"] != 1:
            return False, f"stats: {rep['stats']['cold_read']}"

        # the other direction: a later RESOLVED with the same kind and an
        # overlapping id closes it
        _full(p, d, open_only + "\nRESOLVED | ambiguous-pronoun | 17,18 | "
                                "line 18 now names him")
        ok = ra.review_report(d, p)
        if ok["errors"]:
            return False, ("FINDING + a matching RESOLVED still errored: "
                           + ok["errors"][0][:150])

        # and the ORDER matters: a RESOLVED written BEFORE its finding closes
        # nothing. Without this the gate could be satisfied by a boilerplate
        # "RESOLVED | * " block pasted at the top of the file.
        _full(p, d, "RESOLVED | ambiguous-pronoun | 18 | fixed\n" + open_only)
        rev = ra.review_report(d, p)
        if not _errs(rev, "[COLD-READ]"):
            return False, ("a RESOLVED placed ABOVE its finding closed it; "
                           "resolution order is not enforced")

        # a resolution for a DIFFERENT kind must not close it either
        _full(p, d, open_only + "\nRESOLVED | dangling-ref | 18 | unrelated")
        wrong = ra.review_report(d, p)
        if not _errs(wrong, "[COLD-READ]"):
            return False, ("a RESOLVED of a different kind closed the "
                           "finding; the kind is not being matched")
        return True, ("open FINDING -> UNRESOLVED error naming kind and id; "
                      "a later same-kind RESOLVED with an overlapping id "
                      "clears it; one placed earlier, or of another kind, "
                      "does not")
    finally:
        shutil.rmtree(p, ignore_errors=True)


def test_answered_needs_reason() -> tuple[bool, str]:
    d = _draft()
    p = _proj()
    try:
        f = ("FINDING | invented-claim | 9 | the line asserts a repetition "
             "nothing supports")
        long = ("ANSWERED | invented-claim | 9 | the rival does lose a room "
                "in three separate scenes, so the claim holds")      # 15 words
        _full(p, d, f + "\n" + long)
        ok = ra.review_report(d, p)
        if ok["errors"]:
            return False, (f"a {len(long.split('|')[3].split())}-word "
                           f"ANSWERED was refused: " + ok["errors"][0][:150])
        short = "ANSWERED | invented-claim | 9 | it is fine"          # 3 words
        _full(p, d, f + "\n" + short)
        bad = ra.review_report(d, p)
        cold = _errs(bad, "[COLD-READ]")
        if not cold:
            return False, ("a 3-word ANSWERED closed the finding; 'answered' "
                           "with no argument is being accepted")
        blob = " ".join(cold)
        mw = getattr(config, "REVIEW_ANSWER_MIN_WORDS", 8)
        if str(mw) not in blob:
            return False, (f"the error does not state the {mw}-word minimum: "
                           f"{blob[:140]}")
        if "UNRESOLVED" not in blob:
            return False, ("the reasonless ANSWERED was rejected but the "
                           "finding was still counted as closed")
        return True, (f"a 15-word ANSWERED closes the finding; a 3-word one "
                      f"errors, states the {mw}-word minimum, and leaves the "
                      f"finding UNRESOLVED")
    finally:
        shutil.rmtree(p, ignore_errors=True)


# ---- 7. malformed entries are refused, not skipped ----------------------- #

def test_malformed_refused() -> tuple[bool, str]:
    d = _draft()
    p = _proj()
    cases = {
        "3 fields": "FINDING | dangling-ref | 3",
        "bad status": "MAYBE | dangling-ref | 3 | not sure about this one",
        "prose in the fence":
            "I read the whole thing twice and it seemed clear enough.",
    }
    try:
        got = {}
        for label, entry in cases.items():
            _full(p, d, entry)
            rep = ra.review_report(d, p)
            cold = _errs(rep, "[COLD-READ]")
            if not cold:
                return False, (f"{label}: a malformed entry was SKIPPED, not "
                               f"refused - the gate reported zero findings on "
                               f"a file it could not read")
            blob = " ".join(cold)
            if "malformed" not in blob.lower():
                return False, f"{label}: the error does not say malformed"
            if "line " not in blob:
                return False, (f"{label}: the error does not name the line in "
                               f"the artifact: {blob[:140]}")
            got[label] = rep["stats"]["cold_read"]["malformed"]
        # a malformed SIGNATURE entry is refused the same way
        (p / "cold_read.md").write_text(
            "```review-signatures\n  3 nothex!!\n```\n", encoding="utf-8")
        rep = ra.review_report(d, p)
        if "hex" not in " ".join(_errs(rep, "[COLD-READ]")):
            return False, "a non-hex signature was accepted"
        return True, ("3 fields, bad status and prose inside the fence each "
                      "error with the artifact line number ("
                      + ", ".join(f"{k}: {v}" for k, v in got.items())
                      + "); a non-hex signature is refused too")
    finally:
        shutil.rmtree(p, ignore_errors=True)


# ---- 8. what the signature is, and is not, sensitive to ------------------ #

def test_signature_semantics() -> tuple[bool, str]:
    a = "He owes a stranger a car before he has learned to turn a corner."
    b = "  he owes a STRANGER a car   before he has\nlearned to turn a corner. "
    c = "He owes a stranger a van before he has learned to turn a corner."
    sa, sb, sc = (ra.line_signature(x) for x in (a, b, c))
    if sa != sb:
        return False, (f"reflowed and recapitalised text got a different "
                       f"signature ({sa} vs {sb}); a review would go stale on "
                       f"a whitespace fix nobody read differently")
    if sa == sc:
        return False, (f"a one-word edit (car -> van) kept the signature "
                       f"{sa}; a stale review would read as current")
    if len(sa) != 8 or any(ch not in "0123456789abcdef" for ch in sa):
        return False, f"the signature is not 8 hex characters: {sa!r}"
    if ra.line_signature("") != ra.line_signature("   \n  "):
        return False, "empty and whitespace-only text disagree"
    # the draft-level view: only narrated lines, keyed by id, in draft order
    d = _draft(3)
    sig = ra.draft_signatures(d)
    if list(sig) != ["1", "2", "3"]:
        return False, (f"draft_signatures returned {list(sig)}; the silent "
                       f"4th unit must not be in the denominator and the "
                       f"order must be draft order")
    if sig["2"] != sa:
        return False, "draft_signatures disagrees with line_signature"
    return True, (f"whitespace+case insensitive ({sa}), one-word-edit "
                  f"sensitive ({sa} != {sc}), 8 hex chars; "
                  f"draft_signatures covers 3 narrated of 4 units, in order")


# ---- 9. the gate never raises -------------------------------------------- #

def test_never_raises() -> tuple[bool, str]:
    """Malformed everything. A report comes back, and it is never a pass."""
    p = _proj()
    try:
        good = _draft(4)
        _full(p, good)
        drafts = {
            "None": None,
            "not a dict": ["lines"],
            "no lines key": {"title": "x"},
            "lines not a list": {"lines": "nope"},
            "empty lines": {"lines": []},
            "line is not a dict": {"lines": ["a string", 7, None]},
            "line has no id": {"lines": [{"narration": "text with no id"}]},
            "narration is a dict": {"lines": [{"id": 1, "narration": {"a": 1}}]},
            "id is a dict": {"lines": [{"id": {"x": 1}, "narration": "t"}]},
        }
        for label, d in drafts.items():
            rep = ra.review_report(d, p)
            for k in ("errors", "warns", "notes", "stats"):
                if k not in rep:
                    return False, f"{label}: the report has no {k!r} key"
            if not isinstance(rep["errors"], list):
                return False, f"{label}: errors is not a list"

        # a draft with no narrated lines must say "cannot measure", not pass
        rep = ra.review_report({"lines": [{"id": 1, "narration": ""}]}, p)
        if "CANNOT BE MEASURED" not in " ".join(rep["notes"] + rep["errors"]):
            return False, ("a draft with nothing to review produced neither "
                           "an error nor a stated 'cannot measure'; that is a "
                           "silent pass")

        # and malformed ARTIFACTS, against a good draft
        arts = {
            "empty file": b"",
            "binary junk": bytes(range(0, 48)) + b"\xff\xfe\x00\x01junk",
            "fence never closed": b"```review-signatures\n  1 aaaaaaaa\n",
            "no fences at all": "just prose, no blocks".encode("utf-8"),
            "nested fence": b"```review-findings\n```review-findings\n```\n",
        }
        for label, blob in arts.items():
            (p / "cold_read.md").write_bytes(blob)
            rep = ra.review_report(good, p)
            if not isinstance(rep.get("errors"), list):
                return False, f"artifact {label}: no usable report"
            if not _errs(rep, "[COLD-READ]"):
                return False, (f"artifact {label}: produced NO error - an "
                               f"unreadable artifact passed as a review")

        # a directory where a file should be: the one that actually raises
        (p / "cold_read.md").unlink()
        (p / "cold_read.md").mkdir()
        rep = ra.review_report(good, p)
        if not _errs(rep, "[COLD-READ]"):
            return False, ("a DIRECTORY named cold_read.md passed as a review "
                           "artifact")
        return True, (f"{len(drafts)} malformed draft(s), {len(arts)} "
                      f"malformed artifact(s) and a directory-as-file all "
                      f"returned a report; none of them passed, and an "
                      f"unmeasurable draft says so")
    finally:
        shutil.rmtree(p, ignore_errors=True)


# ---- 10. the bar is read at call time ------------------------------------ #

def test_config_driven() -> tuple[bool, str]:
    """Move the bar, move the verdict - without touching the artifacts."""
    d = _draft(20)
    p = _proj()
    keep_cov = config.REVIEW_SIGNATURE_MIN_COVERAGE
    keep_cold = config.REVIEW_REQUIRE_COLD_READ
    try:
        _full(p, d, skip={17, 18, 19, 20})          # coverage 0.80
        config.REVIEW_SIGNATURE_MIN_COVERAGE = 0.95
        strict = ra.review_report(d, p)
        cov = strict["stats"]["cold_read"]["coverage"]
        if not _errs(strict, "[COLD-READ]"):
            return False, f"coverage {cov:.2f} passed a 0.95 bar"
        config.REVIEW_SIGNATURE_MIN_COVERAGE = 0.75
        loose = ra.review_report(d, p)
        if _errs(loose, "[COLD-READ]"):
            return False, (f"coverage {cov:.2f} still failed after the bar "
                           f"moved to 0.75, so the threshold is baked in at "
                           f"import: " + _errs(loose, "[COLD-READ]")[0][:120])
        # and the requirement flag is read at call time too
        config.REVIEW_SIGNATURE_MIN_COVERAGE = 0.95
        config.REVIEW_REQUIRE_COLD_READ = False
        off = ra.review_report(d, p)
        if _errs(off, "[COLD-READ]"):
            return False, "REVIEW_REQUIRE_COLD_READ=False did not disable it"
        if "was NOT checked" not in " ".join(off["notes"]):
            return False, ("switching the gate off was SILENT; a disabled "
                           "review must still be visible in the report")
        return True, (f"coverage {cov:.2f}: fails at bar 0.95, passes at "
                      f"0.75, and REVIEW_REQUIRE_COLD_READ=False disables it "
                      f"with a NOTE saying nothing was verified")
    finally:
        config.REVIEW_SIGNATURE_MIN_COVERAGE = keep_cov
        config.REVIEW_REQUIRE_COLD_READ = keep_cold
        shutil.rmtree(p, ignore_errors=True)


TESTS = {
    "MISSING-ARTIFACT":      test_missing_artifact,
    "CLEAN-PASSES":          test_clean_passes,
    "UNSIGNED-IS-STALE":     test_unsigned_is_stale,
    "STALE-AFTER-EDIT":      test_stale_after_edit,
    "FIXING-IS-NOT-STALE":   test_fixing_findings_is_not_staleness,
    "SILENT-EDIT":           test_silent_edit_beats_the_percentage,
    "COVERAGE-BOUNDARY":     test_coverage_boundary,
    "FINDING-UNRESOLVED":    test_finding_unresolved,
    "ANSWERED-NEEDS-REASON": test_answered_needs_reason,
    "MALFORMED-REFUSED":     test_malformed_refused,
    "SIGNATURE-SEMANTICS":   test_signature_semantics,
    "NEVER-RAISES":          test_never_raises,
    "CONFIG-DRIVEN":         test_config_driven,
}


def main() -> int:
    want = sys.argv[1:] or list(TESTS)
    bad = 0
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
    print("-" * 60)
    print("test_review_artifacts: all pass" if not bad else
          f"test_review_artifacts: {bad} FAILURE(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
