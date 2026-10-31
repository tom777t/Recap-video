"""[CLAIM-SUPPORT] and [NAME-AT-REVEAL] - both directions, both gates.

THE TWO DEFECTS, and the numbers behind them
--------------------------------------------
CLAIM-SUPPORT. A shipped line asserted a character had "spent the whole film
telling him" something he never says in any transcript line or any beat. A
claim about a PATTERN is harder to verify than a claim about an incident, not
easier, and it is very cheap to invent. CALLBACK-CITE already demands a
citation for a link to one earlier event; this is the same requirement with a
wider surface, and the citation must name a beat that EXISTS - "B99" on a
90-beat film is not a citation, it is a shape.

Measured 2026-10-30 by pipeline/continuity_gates.habitual_claims:

    tools/fixtures/draft_tokyodrift_overcorrected.json   12 lines, all
                                                         "cites no beat"
    projects/tokyodrift2006/draft_prerewrite.json         4 lines

NAME-AT-REVEAL. A reveal's spoiler hold stopped the narrator naming a
character, and the narration then went on calling him by his appearance at the
very moment the film introduces him by name. A hold applies BEFORE a reveal's
landing time, not AT it: after it lands, withholding the name protects
nothing, and the payoff line loses the word that makes it land.

    the overcorrected fixture: 1 reveal - "Dominic" at 01:36:38 - lands and is
    never named in any line bound at or after that time.

Cases - EVERY path is tested in BOTH directions, because a gate that only
fires, or only stays silent, is not tested at all:

  CLAIM-CITATION        no `callback_beat` fires; a VALID one is clean; one
                        naming a beat that does not exist fires and SAYS SO;
                        a line with no habitual phrase is clean.
  CLAIM-PHRASES         each documented phrase family fires on its own, and
                        an ordinary past-tense sentence does not - so the
                        detector is reading the pattern claim, not English.
  CLAIM-UNVERIFIABLE    with no readable beat map, a cited line degrades to
                        "unverifiable" and says so rather than disappearing.
  CLAIM-REAL-DRAFT      12 findings on the overcorrected fixture, 4 on the
                        pre-rewrite draft, and the report text names them.
  NAME-AT-REVEAL-BOTH   named after the landing time is clean; never named
                        fires; named ONLY BEFORE the landing time still fires,
                        which is the entire point of the gate.
  NAME-AT-REVEAL-SCOPE  a reveal whose `fact` names nobody in names.json is
                        ignored; the LONGEST matching name wins, so a
                        two-word name is not shadowed by a one-word one.
  NAME-AT-REVEAL-REAL   the overcorrected fixture still reports Dominic at
                        01:36:38, and naming him once afterwards clears it.
  GATE-NEVER-RAISES     missing reveals.json / names.json / beat map,
                        malformed line records and non-dict lines all return a
                        report instead of raising - and the one path that CAN
                        say "cannot verify" does say it.

Run:  python tools/test_continuity_new.py
"""
from __future__ import annotations

import copy
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
from pipeline import continuity_gates as cg  # noqa: E402

PROJ = Path(config.project_dir("tokyodrift2006"))
OVER = Path(ROOT) / "tools" / "fixtures" / "draft_tokyodrift_overcorrected.json"
PRE = PROJ / "draft_prerewrite.json"

_TMP: list = []


def _tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="recap_cont_"))
    _TMP.append(d)
    return d


def _cleanup() -> None:
    for d in _TMP:
        shutil.rmtree(d, ignore_errors=True)
    _TMP.clear()


_BEATS = ("style: linear\ndepth_target: recap\nTarget: 9-13 min\n\n"
          "B01 | 00:01:00 | he is put on a plane | Sean | setup\n"
          "B02 | 00:05:00 | the father says it once | Sean | dialogue\n"
          "B03 | 00:09:00 | the car goes into the wall | Sean | action\n")


def _project(*, beats: bool = True, reveals=None, names=None) -> Path:
    """A throwaway project dir carrying only what the gate under test reads."""
    d = _tmp()
    if beats:
        (d / "beats_proposal.md").write_text(_BEATS, encoding="utf-8")
    if reveals is not None:
        (d / "reveals.json").write_text(
            reveals if isinstance(reveals, str)
            else json.dumps(reveals, ensure_ascii=False), encoding="utf-8")
    if names is not None:
        (d / "names.json").write_text(
            names if isinstance(names, str)
            else json.dumps(names, ensure_ascii=False), encoding="utf-8")
    return d


def _line(i, text, **kw):
    ln = {"id": i, "narration": text, "delivery": "normal",
          "clip_start": "00:00:10.000", "clip_end": "00:00:18.000"}
    ln.update(kw)
    return ln


# --------------------------------------------------------------------------- #
# [CLAIM-SUPPORT]
# --------------------------------------------------------------------------- #

_HAB = "His father kept telling him the same thing."


def test_claim_citation() -> tuple[bool, str]:
    """No cite fires; a valid cite is clean; a cite that names nothing fires.

    Fixture: synthetic, against a 3-beat throwaway beat map. The real one is
    tools/fixtures/draft_tokyodrift_overcorrected.json (12 lines).
    """
    p = _project()
    bare = cg.habitual_claims({"lines": [_line(1, _HAB)]}, p)
    if len(bare) != 1:
        return False, (f"a habitual claim with no callback_beat produced "
                       f"{len(bare)} finding(s), expected 1: {bare}")
    if bare[0]["why"] != "cites no beat":
        return False, f"the finding does not say why: {bare[0]}"
    if bare[0]["phrase"].lower() != "kept telling":
        return False, (f"the finding does not quote the phrase it matched: "
                       f"{bare[0]}")

    good = cg.habitual_claims(
        {"lines": [_line(1, _HAB, callback_beat="B02")]}, p)
    if good:
        return False, (f"a claim citing B02 - a beat that EXISTS in the map - "
                       f"was still reported: {good}")

    ghost = cg.habitual_claims(
        {"lines": [_line(1, _HAB, callback_beat="B99")]}, p)
    if len(ghost) != 1:
        return False, (f"a claim citing B99, which is not in a 3-beat map, "
                       f"produced {len(ghost)} finding(s): {ghost}")
    if "not in the beat map" not in ghost[0]["why"]:
        return False, (f"citing a non-existent beat is not distinguished from "
                       f"citing nothing: {ghost[0]['why']!r}. The older "
                       f"version of this rule only checked the field was "
                       f"non-empty, which 'B99' satisfies.")
    if "B99" not in ghost[0]["why"]:
        return False, f"the finding does not name the bad cite: {ghost[0]}"

    plain = cg.habitual_claims(
        {"lines": [_line(1, "His father said it once, at the airport.")]}, p)
    if plain:
        return False, (f"a line making no pattern claim was reported: {plain}")
    return True, ("no cite -> 'cites no beat'; a valid B02 cite is clean; "
                  "'B99' is caught as a beat that is not in the map and says "
                  "so; a line with no habitual phrase is clean")


def test_claim_phrases() -> tuple[bool, str]:
    """Each documented phrase family fires; ordinary past tense does not."""
    p = _project()
    want = {
        "spent the whole film ...ing":
            "He had spent the whole film telling the boy to stop running.",
        "kept ...ing":
            "She kept asking him where the money came from.",
        "always said":
            "His father always said the same four words.",
        "every time he":
            "Every time he loses, the car gets cheaper.",
        "had been ...ing":
            "He had been skimming from the operation for months.",
    }
    missed = [k for k, t in want.items()
              if not cg.habitual_claims({"lines": [_line(1, t)]}, p)]
    if missed:
        return False, (f"{len(missed)} documented phrase families do not "
                       f"fire: {missed}")
    quiet = {
        "one past-tense event": "He told the boy to stop running.",
        "a single question":    "She asked him where the money came from.",
        "a plain description":  "The car goes into the wall at the hairpin.",
    }
    noisy = [k for k, t in quiet.items()
             if cg.habitual_claims({"lines": [_line(1, t)]}, p)]
    if noisy:
        return False, (f"{len(noisy)} ordinary sentences were reported as "
                       f"pattern claims: {noisy}. A rule that fires on "
                       f"English rather than on the claim is noise, and noise "
                       f"reads as zero.")
    return True, (f"all {len(want)} documented phrase families fire "
                  f"({', '.join(sorted(want))}); {len(quiet)} ordinary "
                  f"sentences making the same claim ONCE stay clean")


def test_claim_unverifiable() -> tuple[bool, str]:
    """With no readable beat map the finding DEGRADES; it does not vanish."""
    p = _project(beats=False)
    r = cg.habitual_claims(
        {"lines": [_line(1, _HAB, callback_beat="B02")]}, p)
    if not r:
        return False, ("with no beat map, a cited habitual claim disappeared "
                       "entirely - a gate that silently stops measuring is "
                       "indistinguishable from one that passes")
    if "unverifiable" not in r[0]["why"]:
        return False, f"the degraded finding does not say so: {r[0]['why']!r}"
    if "B02" not in r[0]["why"]:
        return False, f"the degraded finding drops the cite: {r[0]}"
    # ...and the SAME draft against a project that HAS the map is clean, so
    # the degradation is about the map and not about the line.
    if cg.habitual_claims({"lines": [_line(1, _HAB, callback_beat="B02")]},
                          _project()):
        return False, ("the same line is still reported when the beat map IS "
                       "readable, so 'unverifiable' was not the reason")
    return True, ("no beat map -> 'cites B02, unverifiable - the beat map "
                  "could not be read'; the same line against a readable map "
                  "is clean")


def test_claim_real_draft() -> tuple[bool, str]:
    """The real drafts, and the report text that carries the finding.

    Measured 2026-10-30: 12 findings on the overcorrected fixture, 4 on the
    pre-rewrite draft. Both are real defects; the gate is not an
    overcorrection gate and is expected to fire on both.
    """
    if not OVER.exists():
        return False, f"the fixture {OVER.name} is missing"
    over = json.loads(OVER.read_text(encoding="utf-8-sig"))
    pre = json.loads(PRE.read_text(encoding="utf-8-sig"))
    ho = cg.habitual_claims(over, PROJ)
    hp = cg.habitual_claims(pre, PROJ)
    if len(ho) != 12:
        return False, (f"the overcorrected fixture reports {len(ho)} habitual "
                       f"claim(s), not the 12 measured: "
                       + "; ".join(f"{r['line_id']} {r['phrase']!r}"
                                   for r in ho[:6]))
    if len(hp) != 4:
        return False, (f"the pre-rewrite draft reports {len(hp)} habitual "
                       f"claim(s), not the 4 measured")
    if any(r["why"] != "cites no beat" for r in ho):
        return False, (f"not every finding on the fixture is an uncited "
                       f"claim: {[r['why'] for r in ho]}")
    blob = " ".join(cg.continuity_report(over, PROJ)["errors"])
    if "[CLAIM-SUPPORT]" not in blob:
        return False, ("habitual_claims reports findings but "
                       "continuity_report does not carry them - the gate is "
                       "not wired into the report the draft stage reads")
    if "callback_beat" not in blob:
        return False, "the error does not tell the writer what to add"
    # ...and citing them all clears the gate, so the fix is reachable.
    fixed = copy.deepcopy(over)
    ids = {r["line_id"] for r in ho}
    for ln in fixed["lines"]:
        if ln.get("id") in ids:
            ln["callback_beat"] = "B60"
    left = cg.habitual_claims(fixed, PROJ)
    if left:
        return False, (f"citing a real beat on all {len(ids)} lines left "
                       f"{len(left)} finding(s) - the fix the error asks for "
                       f"does not clear it")
    return True, (f"overcorrected fixture {len(ho)} claim(s) (lines "
                  + ", ".join(str(r["line_id"]) for r in ho[:6])
                  + f" ...), pre-rewrite {len(hp)}; all 'cites no beat'; the "
                    f"report carries [CLAIM-SUPPORT] and citing a real beat "
                    f"clears all {len(ids)}")


# --------------------------------------------------------------------------- #
# [NAME-AT-REVEAL]
# --------------------------------------------------------------------------- #

_REV = {"reveals": [{"land": "00:10:00", "type": "A",
                     "fact": "Marlowe is the one who set the fire",
                     "hold": ["set the fire"]}]}
_NAMES = {"names": [{"character": "Marlowe", "actor": "A"},
                    {"character": "Sean", "actor": "B"}]}


def test_name_at_reveal_both() -> tuple[bool, str]:
    """Named after the landing time is clean; never, or only before, fires.

    Fixture: synthetic (tempfile.mkdtemp); the real one is the overcorrected
    fixture's R4, "Dominic" at 01:36:38.
    """
    p = _project(reveals=_REV, names=_NAMES)

    after = {"lines": [
        _line(1, "He walks into the garage.", clip_start="00:05:00",
              clip_end="00:05:08"),
        _line(2, "Marlowe is the one who struck the match.",
              clip_start="00:12:00", clip_end="00:12:08")]}
    if cg.unnamed_reveals(after, p):
        return False, ("a reveal whose character IS named after the landing "
                       "time was reported")

    never = {"lines": [
        _line(1, "He walks into the garage.", clip_start="00:05:00",
              clip_end="00:05:08"),
        _line(2, "The quiet one is the one who struck the match.",
              clip_start="00:12:00", clip_end="00:12:08")]}
    r = cg.unnamed_reveals(never, p)
    if len(r) != 1:
        return False, (f"a reveal that is never named produced {len(r)} "
                       f"finding(s): {r}")
    if r[0]["name"] != "Marlowe" or r[0]["land"] != "00:10:00":
        return False, f"the finding does not identify the reveal: {r[0]}"

    # THE POINT OF THE GATE. The hold applies BEFORE the landing time; naming
    # the character only before it and then going vague is the exact defect.
    before_only = {"lines": [
        _line(1, "Marlowe parks on the hill and waits.",
              clip_start="00:05:00", clip_end="00:05:08"),
        _line(2, "The quiet one is the one who struck the match.",
              clip_start="00:12:00", clip_end="00:12:08")]}
    rb = cg.unnamed_reveals(before_only, p)
    if not rb:
        return False, ("naming the character only BEFORE the landing time "
                       "satisfied the gate. That is precisely the defect: the "
                       "payoff line is the one that needs the name, and a "
                       "mention an hour earlier does not supply it.")

    # a line bound exactly AT the landing time counts as after
    at_land = {"lines": [
        _line(1, "He walks into the garage.", clip_start="00:05:00",
              clip_end="00:05:08"),
        _line(2, "Marlowe strikes the match.", clip_start="00:10:00",
              clip_end="00:10:08")]}
    if cg.unnamed_reveals(at_land, p):
        return False, ("a line bound exactly AT the landing time was not "
                       "counted as after it - the hold applies BEFORE the "
                       "landing, not at it")
    return True, ("named after the landing time is clean; never named fires "
                  "and identifies the reveal; named only BEFORE it still "
                  "fires; a line exactly AT the landing time counts as after")


def test_name_at_reveal_scope() -> tuple[bool, str]:
    """A reveal naming nobody is ignored; the LONGEST matching name wins."""
    rv = {"reveals": [{"land": "00:10:00",
                       "fact": "the money was never in the car at all"}]}
    p = _project(reveals=rv, names=_NAMES)
    d = {"lines": [_line(1, "Nothing here names anyone.",
                         clip_start="00:12:00", clip_end="00:12:08")]}
    if cg.unnamed_reveals(d, p):
        return False, ("a reveal whose `fact` names no character in "
                       "names.json was still checked - the gate would then "
                       "fire on every reveal about an object or a place")

    rv2 = {"reveals": [{"land": "00:10:00",
                        "fact": "Dominic Toretto is the challenger"}]}
    nm2 = {"names": [{"character": "Dominic", "actor": "A"},
                     {"character": "Dominic Toretto", "actor": "A"}]}
    p2 = _project(reveals=rv2, names=nm2)
    r = cg.unnamed_reveals(
        {"lines": [_line(1, "The challenger says nothing.",
                         clip_start="00:12:00", clip_end="00:12:08")]}, p2)
    if not r:
        return False, "the two-name reveal did not fire at all"
    if r[0]["name"] != "Dominic Toretto":
        return False, (f"the subject resolved to {r[0]['name']!r}; the longest "
                       f"matching name must win, or a two-word name is "
                       f"shadowed by the one-word name inside it")
    # ...and the one-word name alone does NOT satisfy the two-word subject
    ok = cg.unnamed_reveals(
        {"lines": [_line(1, "Dominic Toretto gets out of the car.",
                         clip_start="00:12:00", clip_end="00:12:08")]}, p2)
    if ok:
        return False, f"naming the subject in full still fired: {ok}"
    return True, ("a reveal about no named character is ignored; with both "
                  "'Dominic' and 'Dominic Toretto' in names.json the subject "
                  "resolves to the longer one, and naming it clears the gate")


def test_name_at_reveal_real() -> tuple[bool, str]:
    """The real project: R4, Dominic at 01:36:38 on the overcorrected draft.

    Fixture: tools/fixtures/draft_tokyodrift_overcorrected.json against
    projects/tokyodrift2006 (real reveals.json + names.json).
    """
    if not OVER.exists():
        return False, f"the fixture {OVER.name} is missing"
    over = json.loads(OVER.read_text(encoding="utf-8-sig"))
    r = cg.unnamed_reveals(over, PROJ)
    if len(r) != 1 or r[0]["name"] != "Dominic":
        return False, (f"the overcorrected fixture no longer reports the one "
                       f"measured unnamed reveal (Dominic at 01:36:38): {r}")
    land = r[0]["land"]
    blob = " ".join(cg.continuity_report(over, PROJ)["errors"])
    if "[NAME-AT-REVEAL]" not in blob or "Dominic" not in blob:
        return False, ("unnamed_reveals reports it but continuity_report does "
                       "not carry it")
    # NAMING HIM ONCE AFTER THE LANDING CLEARS IT - the fix must be reachable,
    # and it must be the NAME that does the work, not the extra line.
    from pipeline.draft import parse_ts
    fixed = copy.deepcopy(over)
    late = [ln for ln in fixed["lines"]
            if isinstance(ln, dict) and str(ln.get("narration") or "").strip()
            and (cg._ts(ln.get("clip_start")) or -1) >= parse_ts(land)]
    if not late:
        return False, (f"no narrated line is bound at or after {land}, so the "
                       f"fixture cannot demonstrate the fix")
    late[0]["narration"] = "Dominic " + late[0]["narration"]
    if cg.unnamed_reveals(fixed, PROJ):
        return False, (f"adding the name to line {late[0].get('id')} did not "
                       f"clear the finding")
    # ...and the same extra WORD COUNT without the name does not clear it
    nofix = copy.deepcopy(over)
    nofix_late = [ln for ln in nofix["lines"]
                  if isinstance(ln, dict)
                  and str(ln.get("narration") or "").strip()
                  and (cg._ts(ln.get("clip_start")) or -1) >= parse_ts(land)]
    nofix_late[0]["narration"] = "The driver " + nofix_late[0]["narration"]
    if not cg.unnamed_reveals(nofix, PROJ):
        return False, ("describing him instead of naming him also cleared the "
                       "gate - it is not the name that is being checked")
    return True, (f"\"Dominic\" at {land} is reported on the overcorrected "
                  f"fixture and carried into continuity_report; naming him on "
                  f"line {late[0].get('id')} clears it, while calling him "
                  f"\"the driver\" instead does not")


# --------------------------------------------------------------------------- #

def test_gate_never_raises() -> tuple[bool, str]:
    """Missing inputs and malformed lines must DEGRADE, never raise.

    What this test can and cannot claim, stated rather than implied:

      * habitual_claims HAS a "cannot verify" voice - with no readable beat
        map a cited line is still reported, as "unverifiable". Asserted here.
      * unnamed_reveals has NO such voice. With no reveals.json it returns
        nothing, which is correct: a project that declares no reveals has no
        reveal to check. But with a reveals.json that EXISTS and cannot be
        parsed it also returns nothing, and that case is indistinguishable
        from "clean". This test pins the current behaviour and names the gap;
        it does not pretend the gap is absent.
    """
    junk = {"lines": [
        None,
        "not a dict at all",
        12345,
        {},
        {"id": 1},
        {"id": 2, "narration": None},
        {"id": 3, "narration": 4242},
        {"id": 4, "narration": _HAB, "clip_start": "not-a-timestamp"},
        {"id": 5, "narration": _HAB, "clip_start": None, "clip_end": None},
        {"id": 6, "narration": "Marlowe.", "clip_start": "00:12:00",
         "callback_beat": {"not": "a string"}},
    ]}
    probes = []
    for label, pdir in (("no beat map / no reveals / no names",
                         _project(beats=False)),
                        ("beat map only", _project()),
                        ("everything present",
                         _project(reveals=_REV, names=_NAMES)),
                        ("reveals.json present but corrupt",
                         _project(reveals="{ this is not json",
                                  names=_NAMES)),
                        ("names.json present but corrupt",
                         _project(reveals=_REV, names="[[[")),
                        ("the real project", PROJ)):
        try:
            hc = cg.habitual_claims(junk, pdir)
            ur = cg.unnamed_reveals(junk, pdir)
            rep = cg.continuity_report(junk, pdir)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, (f"{label}: the gate RAISED {type(e).__name__}: {e}. "
                           f"A malformed draft must come back as a report.")
        if not isinstance(rep, dict) or "errors" not in rep:
            return False, f"{label}: continuity_report returned {rep!r}"
        probes.append((label, len(hc), len(ur)))

    # the "cannot verify" path that EXISTS must say so
    nomap = cg.habitual_claims(
        {"lines": [_line(1, _HAB, callback_beat="B02")]},
        _project(beats=False))
    if not nomap or "unverifiable" not in nomap[0]["why"]:
        return False, ("with no beat map a cited habitual claim is not "
                       "reported as unverifiable - it passes silently")

    # the gap, pinned rather than hidden
    corrupt = cg.unnamed_reveals(
        {"lines": [_line(1, "The quiet one.", clip_start="00:12:00")]},
        _project(reveals="{ this is not json", names=_NAMES))
    gap = ("" if corrupt else
           "unnamed_reveals returns 0 findings on a reveals.json that EXISTS "
           "and cannot be parsed, which is indistinguishable from clean - it "
           "has no 'cannot verify' voice the way habitual_claims does")
    return True, ("no raise on non-dict, null, numeric, timestamp-less and "
                  "wrongly-typed line records across "
                  + ", ".join(f"{l} ({h} claim/{u} reveal)"
                              for l, h, u in probes)
                  + f"; the beat-map path says 'unverifiable'. GAP: {gap}"
                  if gap else
                  "no raise anywhere, and both cannot-verify paths say so")


TESTS = {
    "CLAIM-CITATION":        test_claim_citation,
    "CLAIM-PHRASES":         test_claim_phrases,
    "CLAIM-UNVERIFIABLE":    test_claim_unverifiable,
    "CLAIM-REAL-DRAFT":      test_claim_real_draft,
    "NAME-AT-REVEAL-BOTH":   test_name_at_reveal_both,
    "NAME-AT-REVEAL-SCOPE":  test_name_at_reveal_scope,
    "NAME-AT-REVEAL-REAL":   test_name_at_reveal_real,
    "GATE-NEVER-RAISES":     test_gate_never_raises,
}

if __name__ == "__main__":
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
        _cleanup()
    print("-" * 60)
    print("test_continuity_new: all pass" if not bad else
          f"test_continuity_new: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
