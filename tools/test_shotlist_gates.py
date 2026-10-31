"""The SHOT LIST gates - with the live Tokyo Drift draft as the fixture.

THE DEFECT, exactly
-------------------
Line 82 of projects/tokyodrift2006/draft.json, the narrated line immediately
after Han burns to death in the car, reads:

    "He walks away from the fire between the taxis. A tiled station floor, a
     walkway, a platform, a commuter train sliding in behind them."

The first sentence is fine. The SECOND is four comma-separated visible nouns
with no finite verb that makes anything happen, no agent, and nothing of the
narrator's own - a caption for a picture the viewer is already looking at, in
the seconds after a death, where the draft should either say something or say
nothing.

WHY THE OLD DETECTOR MISSED IT, measured here
---------------------------------------------
pacing_gates._is_frame_only is a POSITIVE match on a closed visual-verb list
over a WHOLE LINE:

    "He walks away from the fire between the taxis."           visual verb: walks
    "A tiled ... floor, a walkway, a platform, a ... train ..."  visual verb: NONE
    the two together                                 frame-only: True, for the
                                                     FIRST sentence only

So the line was already counted frame-only - for its harmless half. The verdict
named no sentence, the offending sentence contributed nothing to it, and the
per-line frame-only share was 0.105 against a 0.13 cap, so no finding was
emitted at all. Fixing the second sentence and leaving it alone scored
identically. OLD-DETECTOR-DILUTES asserts every number in that paragraph.

Cases
-----
  SHOT-LIST-BOTH-WAYS     a three-item verbless visible list fires; a two-item
                          list, a three-item list with an agent doing
                          something consequential, and a three-item list
                          carrying evaluation are all silent.
  AFTER-PEAK-BLOCKS       the SAME sentence one narrated line after a peak
                          beat is an ERROR; identical text far from any peak
                          is a WARNING. This is the core of the gate.
  PEAK-WINDOW-LIVE        distance 2 errors, distance 3 only warns, and moving
                          config.SHOTLIST_PEAK_WINDOW_LINES moves that verdict.
  HOLD-AFTER-PEAK-CLEAN   the prescribed remedy passes: the offending line
                          turned into a hold, or given a point, is clean.
                          Without this the gate would be unsatisfiable.
  BARS-FROM-CONFIG        all three constants move the verdict on the same
                          draft, so none of them is a literal in the module.
  PEAK-DEFINITION-SHARED  the peak set this gate uses is the same set
                          pacing_gates' [PEAK-ORDER] uses, tested
                          BEHAVIOURALLY over all of the real angle's anchors.
  REAL-DRAFT-FAILS        tools/fixtures/draft_tokyodrift_shotlist.json - the
                          permanent copy of the live draft - fires on line 82
                          and classifies it after-peak.
  OLD-DETECTOR-DILUTES    the whole-line / sentence-level diagnosis above,
                          with the frame-only share before and after.
  NO-ANGLE                no angle.md: the warning half works, the peak half
                          emits a note, nothing crashes.
  GATE-NEVER-RAISES       malformed drafts and a missing project directory
                          come back as reports.

Run:  python tools/test_shotlist_gates.py
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
from pipeline import pacing_gates as pg  # noqa: E402
from pipeline import shotlist_gates as sg  # noqa: E402

PROJ = Path(config.project_dir("tokyodrift2006"))
LIVE = PROJ / "draft.json"
FIX = Path(ROOT) / "tools" / "fixtures" / "draft_tokyodrift_shotlist.json"

# The real defect, and the three near-misses that must stay silent. Every
# piece of film-specific wording in this change lives here, never in
# pipeline/shotlist_gates.py.
BAD = ("A tiled station floor, a walkway, a platform, a commuter train "
       "sliding in behind them.")
BAD3 = "A tiled station floor, a walkway, a platform."
TWO = "A tiled station floor, a walkway."
AGENT = "The guard checks the floor, pays the driver, and leaves the platform."
EVAL = ("A tiled station floor, a walkway, a platform, and that is the whole "
        "of his pride.")
PLAIN = "He parks the car outside the garage and waits."
POINT = "You can see him decide, and that is the whole of his pride."

# The exact text of the offending live line, by its two sentences.
LIVE_S1 = "He walks away from the fire between the taxis."
LIVE_LINE = f"{LIVE_S1} {BAD}"


def _ts(t: float) -> str:
    return "%02d:%02d:%06.3f" % (int(t) // 3600, (int(t) % 3600) // 60, t % 60)


def _mk(units: list) -> dict:
    """[(beat, narration_or_None, payload)] -> a draft.

    narration None means a HOLD: no text, a silence duration. That is the
    remedy the error message prescribes, so the harness has to be able to
    build one.
    """
    lines = []
    t = 100.0
    for i, u in enumerate(units, 1):
        beat, text = u[0], u[1]
        payload = u[2] if len(u) > 2 else "stake"
        ln = {"id": i, "note": beat, "delivery": "normal",
              "clip_start": _ts(t), "clip_end": _ts(t + 8.0)}
        t += 9.0
        if text is None:
            ln.update({"narration": "", "narration_silence_seconds": 3.0})
        else:
            ln.update({"narration": text, "payload": payload})
        lines.append(ln)
    return {"lines": lines}


def _rep(draft: dict, pdir=PROJ) -> dict:
    return sg.shotlist_report(draft, Path(pdir))


def _err(draft: dict, pdir=PROJ) -> list:
    return [e for e in _rep(draft, pdir)["errors"]
            if e.startswith("[SHOT-LIST-AFTER-PEAK]")]


def _warn(draft: dict, pdir=PROJ) -> list:
    return [w for w in _rep(draft, pdir)["warns"]
            if w.startswith("[SHOT-LIST]")]


def _peak_beat() -> str:
    """One beat the real angle.md declares a peak."""
    beats, trouble = sg.peak_beats(PROJ)
    if trouble or not beats:
        raise AssertionError(f"the real angle declares no peak beat: {trouble}")
    return sorted(beats)[0]


# --------------------------------------------------------------------------- #
# 1. the SHAPE, both directions
# --------------------------------------------------------------------------- #
def test_shot_list_both_ways() -> tuple[bool, str]:
    ok, why = sg.is_shotlist_sentence(BAD3)
    if not ok:
        return False, (f"a three-item verbless visible list is NOT detected "
                       f"({why}): {BAD3!r}")
    ok4, _ = sg.is_shotlist_sentence(BAD)
    if not ok4:
        return False, f"the real four-item defect sentence is not detected: {BAD!r}"

    # MIN_ITEMS is live: the same nouns, one item short.
    bad2, w2 = sg.is_shotlist_sentence(TWO)
    if bad2:
        return False, (f"a TWO-item list fires, so config.SHOTLIST_MIN_ITEMS="
                       f"{config.SHOTLIST_MIN_ITEMS} is not being applied: "
                       f"{TWO!r}")
    if "item(s) <" not in w2:
        return False, f"the two-item case is rejected for the wrong reason: {w2}"

    # an AGENT DOING SOMETHING CONSEQUENTIAL. Deliberately written with no
    # pronoun subject, so this case can only be cleared by the verb test and
    # not by the nominative-pronoun guard.
    bada, wa = sg.is_shotlist_sentence(AGENT)
    if bada:
        return False, (f"a three-item list in which an agent pays and leaves "
                       f"fires: {AGENT!r}")
    if "consequential verb" not in wa:
        return False, (f"the agent case was cleared by something other than "
                       f"the verb test ({wa}), so the verb lexicon is not "
                       f"what is doing the work: {AGENT!r}")

    # EVALUATION. Must be cleared by the REUSED classifier, not by a second
    # opinion of its own - that is the whole reason for the reuse.
    bade, we = sg.is_shotlist_sentence(EVAL)
    if bade:
        return False, f"a three-item list carrying evaluation fires: {EVAL!r}"
    if "carries evaluation" not in we:
        return False, (f"the evaluation case was cleared by something other "
                       f"than classify_judgment ({we}); the two detectors can "
                       f"now disagree about what counts as meaning")
    if not pg.classify_judgment(EVAL)[0]:
        return False, (f"pacing_gates.classify_judgment does not read the "
                       f"evaluation fixture as evaluation, so this case "
                       f"proves nothing: {EVAL!r}")

    # ordinary prose, and the harmless half of the real line, stay silent
    for t in (PLAIN, LIVE_S1):
        if sg.is_shotlist_sentence(t)[0]:
            return False, f"ordinary prose is reported as a shot list: {t!r}"

    # per SENTENCE, not per line: the real line must yield exactly one
    sents = sg.shotlist_sentences(LIVE_LINE)
    if len(sents) != 1 or sents[0][0] != BAD:
        return False, (f"the two-sentence line yields {len(sents)} finding(s) "
                       f"instead of exactly the second sentence: {sents}")
    return True, (f"3 items fires ({why}); 2 items, an agent who pays and "
                  f"leaves, and a list carrying evaluation are all silent for "
                  f"the stated reason; the real two-sentence line yields "
                  f"exactly its second sentence")


# --------------------------------------------------------------------------- #
# 2. AFTER-PEAK: the blocking half. The core of the gate.
# --------------------------------------------------------------------------- #
def test_after_peak_blocks() -> tuple[bool, str]:
    b = _peak_beat()
    # ONE narrated line after the last line on a peak beat -> ERROR
    near = _mk([(b, PLAIN), ("C01", BAD)])
    e = _err(near)
    if not e:
        return False, (f"the shot list one narrated line after peak beat {b} "
                       f"is not an ERROR: {_rep(near)}")
    if "line 2" not in e[0] or BAD not in e[0]:
        return False, (f"the error does not name the line and the sentence: "
                       f"{e[0][:200]}")
    for remedy in ("narration_silence_seconds", "hold", "POINT"):
        if remedy not in e[0]:
            return False, (f"the error does not name the remedy {remedy!r}: "
                           f"{e[0][:300]}")
    if _warn(near):
        return False, ("the same sentence is reported as BOTH an error and a "
                       "warning; the two halves must partition the findings")

    # the sentence ON the peak beat itself is also an error (the live case)
    on = _mk([(b, PLAIN), (b, BAD)])
    if not _err(on):
        return False, f"the shot list ON peak beat {b} is not an ERROR"

    # IDENTICAL TEXT, far from any peak -> WARNING. Same draft shape, same
    # project, same angle, same sentence; only the distance changes.
    far = _mk([(b, PLAIN)] + [(f"C{i:02d}", PLAIN) for i in range(1, 9)]
              + [("C09", BAD)])
    w = _warn(far)
    if not w:
        return False, (f"the identical sentence far from any peak produces no "
                       f"warning either, so the gate only works near a peak: "
                       f"{_rep(far)}")
    if _err(far):
        return False, (f"the identical sentence 9 narrated lines after the "
                       f"peak is still an ERROR, so the window is not being "
                       f"applied: {_err(far)[0][:180]}")
    if BAD not in w[0] or "line 10" not in w[0]:
        return False, f"the warning does not name the line and sentence: {w[0][:200]}"
    return True, (f"the same sentence is an ERROR one line after peak {b} and "
                  f"ON {b}, and a WARNING nine lines later; the error names "
                  f"the line, the sentence and both remedies")


# --------------------------------------------------------------------------- #
# 3. the WINDOW is live
# --------------------------------------------------------------------------- #
def test_peak_window_live() -> tuple[bool, str]:
    b = _peak_beat()
    win = int(config.SHOTLIST_PEAK_WINDOW_LINES)

    def at(distance: int) -> dict:
        mid = [(f"C{i:02d}", PLAIN) for i in range(1, distance)]
        return _mk([(b, PLAIN)] + mid + [(f"C{distance:02d}", BAD)])

    inside = at(win)
    if not _err(inside):
        return False, (f"a shot list {win} narrated line(s) after the peak - "
                       f"the edge of the window - is not an ERROR")
    outside = at(win + 1)
    if _err(outside):
        return False, (f"a shot list {win + 1} narrated line(s) after the "
                       f"peak is an ERROR, but the window is {win}")
    if not _warn(outside):
        return False, (f"a shot list {win + 1} lines after the peak is "
                       f"neither an error nor a warning - it vanished")
    # move the constant and the verdict on the SAME draft must move
    _old = config.SHOTLIST_PEAK_WINDOW_LINES
    try:
        config.SHOTLIST_PEAK_WINDOW_LINES = win + 1
        widened = _err(outside)
        msg = widened[0] if widened else ""
    finally:
        config.SHOTLIST_PEAK_WINDOW_LINES = _old
    if not widened:
        return False, (f"raising config.SHOTLIST_PEAK_WINDOW_LINES to "
                       f"{win + 1} did not fail the draft at distance "
                       f"{win + 1} - the window is not read from config at "
                       f"call time")
    if f"within {win + 1} narrated line(s)" not in msg:
        return False, f"the message still quotes the old window: {msg[:160]}"
    if _err(outside):
        return False, "restoring the constant did not restore the verdict"
    return True, (f"distance {win} errors, distance {win + 1} only warns; "
                  f"raising the constant to {win + 1} fails the same draft "
                  f"and the message quotes the new window")


# --------------------------------------------------------------------------- #
# 4. the prescribed remedy must PASS, or the gate is unsatisfiable
# --------------------------------------------------------------------------- #
def test_hold_after_peak_clean() -> tuple[bool, str]:
    b = _peak_beat()
    offending = _mk([(b, PLAIN), ("C01", BAD)])
    if not _err(offending):
        return False, "the offending draft does not fail, so nothing is proven"

    # REMEDY 1: a HOLD - no narration, a silence duration.
    hold = _mk([(b, PLAIN), ("C01", None)])
    rep = _rep(hold)
    if rep["errors"] or rep["warns"]:
        return False, (f"the prescribed HOLD does not pass: "
                       f"{rep['errors'] + rep['warns']}")

    # REMEDY 2: keep the line, give it a point.
    pointed = _mk([(b, PLAIN), ("C01", POINT, "judgment")])
    rep2 = _rep(pointed)
    if rep2["errors"] or rep2["warns"]:
        return False, (f"giving the line a point does not pass: "
                       f"{rep2['errors'] + rep2['warns']}")

    # REMEDY 3: the real line with only its empty sentence deleted.
    trimmed = _mk([(b, PLAIN), ("C01", LIVE_S1)])
    rep3 = _rep(trimmed)
    if rep3["errors"] or rep3["warns"]:
        return False, (f"deleting just the offending sentence does not pass: "
                       f"{rep3['errors'] + rep3['warns']}")
    return True, ("all three prescribed remedies pass on the draft that fails "
                  "without them: a hold, a line with a point, and the same "
                  "line with only its shot-list sentence deleted")


# --------------------------------------------------------------------------- #
# 5. every bar comes from config
# --------------------------------------------------------------------------- #
def test_bars_from_config() -> tuple[bool, str]:
    b = _peak_beat()
    # BAD3 carries exactly 3 items, all 3 visible.
    draft = _mk([(b, PLAIN), ("C01", BAD3)])
    if not _err(draft):
        return False, "the three-item draft does not fail at the current bars"
    moved = []

    _old = config.SHOTLIST_MIN_ITEMS
    try:
        config.SHOTLIST_MIN_ITEMS = _old + 1
        quiet = _err(draft) + _warn(draft)
    finally:
        config.SHOTLIST_MIN_ITEMS = _old
    if quiet:
        return False, (f"raising config.SHOTLIST_MIN_ITEMS to {_old + 1} did "
                       f"not clear a {_old}-item list: {quiet[0][:160]}")
    moved.append(f"MIN_ITEMS {_old}->{_old + 1} clears it")

    _oldv = config.SHOTLIST_MIN_VISIBLE
    try:
        config.SHOTLIST_MIN_VISIBLE = 4
        quiet = _err(draft) + _warn(draft)
    finally:
        config.SHOTLIST_MIN_VISIBLE = _oldv
    if quiet:
        return False, (f"raising config.SHOTLIST_MIN_VISIBLE to 4 did not "
                       f"clear a list with 3 visible items: {quiet[0][:160]}")
    moved.append(f"MIN_VISIBLE {_oldv}->4 clears it")

    _oldw = config.SHOTLIST_PEAK_WINDOW_LINES
    try:
        config.SHOTLIST_PEAK_WINDOW_LINES = 0
        downgraded = _err(draft)
        still = _warn(draft)
    finally:
        config.SHOTLIST_PEAK_WINDOW_LINES = _oldw
    if downgraded:
        return False, (f"with the window at 0 the line one after the peak is "
                       f"still an error: {downgraded[0][:160]}")
    if not still:
        return False, ("with the window at 0 the finding disappeared entirely "
                       "instead of degrading to a warning")
    moved.append(f"PEAK_WINDOW_LINES {_oldw}->0 downgrades error to warning")

    if not _err(draft):
        return False, ("restoring all three constants did not restore the "
                       "original ERROR verdict, so one of the try/finally "
                       "blocks above leaked")
    if _warn(draft):
        return False, ("after restoring the constants the finding is a "
                       "warning as well as an error")
    return True, "; ".join(moved)


# --------------------------------------------------------------------------- #
# 6. the peak definition is SHARED with pacing_gates
# --------------------------------------------------------------------------- #
def test_peak_definition_shared() -> tuple[bool, str]:
    """Behavioural, over every anchor the real angle declares.

    Checked by BEHAVIOUR rather than by comparing word lists: this module's
    PEAK_WORDS is a second copy of a tuple that is a local variable inside
    pacing_report, so the thing worth asserting is that the two copies sort
    the real anchors identically, not that they are spelled the same.
    """
    mine, trouble = sg.peak_beats(PROJ)
    if trouble:
        return False, f"the peak set could not be read: {trouble}"
    anchors = angle_spec.require(PROJ)["anchors"]
    agree, disagree = [], []
    for a in anchors:
        beat = a["beats"][0]
        by_me = any(x in mine for x in a["beats"])
        # pacing_gates' [PEAK-ORDER] fires "the first line on peak ..." only
        # for an anchor it reads as a peak.
        probe = _mk([(beat, POINT, "judgment"), (beat, PLAIN), (beat, PLAIN)])
        hits = [e for e in pg.pacing_report(probe, PROJ)["errors"]
                if e.startswith("[PEAK-ORDER]") and "first line on peak" in e]
        by_pacing = bool(hits)
        (agree if by_me == by_pacing else disagree).append(
            f"{'/'.join(a['beats'])} ({a['kind']}) me={by_me} "
            f"pacing={by_pacing}")
    if disagree:
        return False, ("the two gates disagree about which anchors are peaks, "
                       "so a writer can be told a line is after a peak by one "
                       "and not by the other: " + "; ".join(disagree))
    n_peak = sum(1 for a in anchors if any(x in mine for x in a["beats"]))
    return True, (f"all {len(agree)} anchor(s) in the real angle are sorted "
                  f"identically by both gates ({n_peak} peak, "
                  f"{len(agree) - n_peak} not); peak beats "
                  f"{', '.join(sorted(mine))}")


# --------------------------------------------------------------------------- #
# 7. THE LIVE DRAFT
# --------------------------------------------------------------------------- #
def test_real_draft_fails() -> tuple[bool, str]:
    """The fixture is read, not the live draft, which will be edited.

    Measured 2026-10-31 on tools/fixtures/draft_tokyodrift_shotlist.json
    against projects/tokyodrift2006 (108 lines, 105 narrated, 262 sentences):

        shot-list sentences          5, on lines 23, 59, 82, 97, 111
        after a peak                 1, line 82 (ON peak beat B79)
        peak beats used              B13, B65, B79, B80, B101
    """
    if not FIX.exists():
        return False, f"the fixture {FIX.name} is missing"
    d = json.loads(FIX.read_text(encoding="utf-8-sig"))
    rep = _rep(d)
    s = rep["stats"]
    target = [ln for ln in d["lines"]
              if "a walkway, a platform" in str(ln.get("narration") or "")]
    if len(target) != 1:
        return False, (f"{len(target)} line(s) in the fixture contain "
                       f"\"a walkway, a platform\"; the fixture no longer "
                       f"demonstrates the defect")
    lid = target[0].get("id")
    if lid not in s["shotlist_line_ids"]:
        return False, (f"line {lid} is NOT reported as a shot list; found "
                       f"{s['shotlist_line_ids']}")
    if lid not in s["after_peak_line_ids"]:
        return False, (f"line {lid} is reported, but NOT as after a peak - "
                       f"which is the half that blocks. after_peak="
                       f"{s['after_peak_line_ids']}, peaks={s['peak_beats']}")
    blocking = [e for e in rep["errors"]
                if e.startswith("[SHOT-LIST-AFTER-PEAK]")]
    if not blocking:
        return False, "line 82 is classified after-peak but no ERROR was emitted"
    if BAD not in blocking[0]:
        return False, (f"the error does not quote the offending sentence: "
                       f"{blocking[0][:200]}")
    if s["sentences_examined"] < 200:
        return False, (f"only {s['sentences_examined']} sentence(s) examined; "
                       f"the fixture has {s['narrated_lines']} narrated lines "
                       f"and should yield far more")
    # the FIRST sentence of that same line must NOT be a finding: the gate is
    # per sentence, and a whole-line measure is what missed this.
    if sg.is_shotlist_sentence(LIVE_S1)[0]:
        return False, ("the harmless first sentence of the same line is also "
                       "reported, so the gate is not discriminating within "
                       "the line")
    return True, (f"{s['shotlist_sentences']} shot-list sentence(s) on lines "
                  f"{s['shotlist_line_ids']}, of which "
                  f"{len(s['after_peak_line_ids'])} after a peak "
                  f"(line {lid}, on peak beat "
                  f"{sg._beat_of(target[0])}); peaks {s['peak_beats']}; "
                  f"{s['sentences_examined']} sentence(s) examined across "
                  f"{s['narrated_lines']} narrated line(s)")


# --------------------------------------------------------------------------- #
# 8. why the OLD detector missed it, and what widening it costs
# --------------------------------------------------------------------------- #
def test_old_detector_dilutes() -> tuple[bool, str]:
    """The diagnosis in this file's docstring, asserted.

    Also measures what the widening does to the frame-only share, because
    config.PERSONA_FRAME_ONLY_SHARE_MAX was calibrated with the NARROW
    detector and the share is the only thing that constant is compared
    against.
    """
    if not FIX.exists():
        return False, f"the fixture {FIX.name} is missing"
    # the mechanism: the positive verb match hits the harmless sentence only
    if not pg._VISUAL_VERB.search(LIVE_S1):
        return False, ("the first sentence no longer matches _VISUAL_VERB, so "
                       "the dilution account does not hold")
    if pg._VISUAL_VERB.search(BAD):
        return False, ("the offending sentence DOES match _VISUAL_VERB, so it "
                        "was not missed for want of a verb")
    # the sentence on its own, by the ORIGINAL rule (verb match only), is not
    # frame-only; the whole line is - for the first sentence
    if not pg._is_frame_only(LIVE_LINE):
        return False, ("the whole line is not frame-only even now, so the "
                       "widening did not take effect")
    if not pg._is_frame_only(BAD):
        return False, ("the offending sentence alone is still not frame-only, "
                       "so pacing_gates._is_frame_only was not widened")

    d = json.loads(FIX.read_text(encoding="utf-8-sig"))
    lines = [ln for ln in d["lines"] if str(ln.get("narration") or "").strip()]
    new = [ln for ln in lines if pg._is_frame_only(str(ln["narration"]))]

    def narrow(t: str) -> bool:
        """_is_frame_only as it was BEFORE the widening."""
        if not t:
            return False
        if pg._is_move(t):
            return False
        if '"' in t or "\u201c" in t:
            return False
        return bool(pg._VISUAL_VERB.search(t))

    old = [ln for ln in lines if narrow(str(ln["narration"]))]
    o_share = len(old) / len(lines)
    n_share = len(new) / len(lines)
    cap = config.PERSONA_FRAME_ONLY_SHARE_MAX
    if n_share < o_share:
        return False, (f"the widened detector reports a SMALLER share "
                       f"({n_share:.4f} vs {o_share:.4f}); widening cannot "
                       f"remove lines")
    added = sorted(set(ln["id"] for ln in new) - set(ln["id"] for ln in old))
    if not added:
        return False, ("the widening added no lines on the live draft, so "
                       "either the shot-list detector or the extension is "
                       "not wired up")
    # the diluted verdict: the offending line was ALREADY counted, so the
    # share did not move because of it
    if target_id(d) not in [ln["id"] for ln in old]:
        return False, (f"line {target_id(d)} was NOT already frame-only under "
                       f"the narrow rule, so the dilution account - that it "
                       f"was counted for its harmless half - is wrong")
    if o_share > cap:
        return False, (f"the narrow share {o_share:.4f} was ALREADY over the "
                       f"{cap} cap, so the defect did draw a finding and the "
                       f"\"no finding at all\" account is wrong")
    return True, (f"the offending sentence has no visual verb and the "
                  f"harmless one does, so the line scored frame-only for its "
                  f"first half only; frame-only share {o_share:.4f} -> "
                  f"{n_share:.4f} on {len(lines)} narrated lines (cap {cap}), "
                  f"adding lines {added}; the narrow share was UNDER the cap, "
                  f"so the defect drew no finding at all")


def target_id(d: dict):
    for ln in d["lines"]:
        if "a walkway, a platform" in str(ln.get("narration") or ""):
            return ln.get("id")
    return None


# --------------------------------------------------------------------------- #
# 9. no angle.md
# --------------------------------------------------------------------------- #
def test_no_angle() -> tuple[bool, str]:
    td = Path(tempfile.mkdtemp(prefix="shotlist_noangle_"))
    try:
        if (td / "angle.md").exists():
            return False, "the temporary project is not clean"
        draft = _mk([("B79", PLAIN), ("C01", BAD)])
        rep = _rep(draft, td)
        if rep["errors"]:
            return False, (f"a project with no angle.md produces ERRORS: "
                           f"{rep['errors'][0][:200]}")
        if not rep["warns"]:
            return False, ("with no angle.md the warning half stopped working "
                           "too - the shot list was silently passed")
        if BAD not in rep["warns"][0]:
            return False, f"the warning does not name the sentence: {rep['warns'][0][:160]}"
        note = [n for n in rep["notes"]
                if n.startswith("[SHOT-LIST-AFTER-PEAK]")]
        if not note:
            return False, ("the peak half did not SAY it could not run; a "
                           "missing half that says nothing reads as a pass")
        for probe in ("no angle.md", "unchecked"):
            if probe not in note[0]:
                return False, (f"the note does not state {probe!r}: "
                               f"{note[0][:200]}")
        if rep["stats"]["peak_beats"]:
            return False, (f"peaks were reported anyway: "
                           f"{rep['stats']['peak_beats']}")
        # and an angle.md that EXISTS but declares no peak is a different note
        (td / "angle.md").write_text("# x\n\n## ANCHORS\n\n- **B79** | setup "
                                     "| nothing special\n", encoding="utf-8")
        rep2 = _rep(draft, td)
        n2 = [n for n in rep2["notes"]
              if n.startswith("[SHOT-LIST-AFTER-PEAK]")]
        if not n2 or "declared a peak" not in n2[0]:
            return False, (f"an angle that declares no peak does not say so: "
                           f"{rep2['notes']}")
        if not rep2["warns"]:
            return False, "the warning half stopped working on that angle too"
        return True, ("no angle.md: 0 errors, the shot list still warned, and "
                      "the peak half says out loud that it did not run and "
                      "that this is unchecked; an angle with no peak anchor "
                      "gets its own note")
    finally:
        shutil.rmtree(td, ignore_errors=True)


# --------------------------------------------------------------------------- #
# 10. the gate never raises
# --------------------------------------------------------------------------- #
def test_gate_never_raises() -> tuple[bool, str]:
    checked = []
    bad_inputs = [
        ("None", None),
        ("empty dict", {}),
        ("lines is a string", {"lines": "nope"}),
        ("lines is None", {"lines": None}),
        ("line is None", {"lines": [None]}),
        ("line is an int", {"lines": [3, 4]}),
        ("narration is an int", {"lines": [{"id": 1, "narration": 123}]}),
        ("narration is a list", {"lines": [{"id": 1, "narration": [BAD]}]}),
        ("no id, no note", {"lines": [{"narration": BAD}]}),
        ("note is an int", {"lines": [{"id": 1, "note": 7,
                                       "narration": BAD}]}),
    ]
    for name, d in bad_inputs:
        try:
            rep = sg.shotlist_report(d, PROJ)
        except Exception as e:
            return False, f"{name} RAISED {type(e).__name__}: {e}"
        for k in ("errors", "warns", "notes", "stats"):
            if k not in rep:
                return False, f"{name}: the report has no {k!r} key"
        if not isinstance(rep["stats"], dict):
            return False, f"{name}: stats is not a dict"
        checked.append(name)

    # a line with no id must still be nameable in a finding
    rep = sg.shotlist_report({"lines": [{"narration": BAD}]}, PROJ)
    blob = " ".join(rep["errors"] + rep["warns"])
    if BAD not in blob:
        return False, ("a line with no id produced no finding at all, so the "
                       "shot list was silently passed")

    # a MISSING project directory: the peak half cannot run, and says so
    missing = Path(ROOT) / "projects" / "_no_such_project_shotlist_test"
    if missing.exists():
        return False, f"{missing} unexpectedly exists"
    try:
        rep = sg.shotlist_report(_mk([("C01", BAD)]), missing)
    except Exception as e:
        return False, f"a missing project dir RAISED {type(e).__name__}: {e}"
    if not rep["warns"]:
        return False, "a missing project dir silently passed the shot list"
    if not any(n.startswith("[SHOT-LIST-AFTER-PEAK]") for n in rep["notes"]):
        return False, "a missing project dir did not state that peaks are unknown"
    checked.append("missing project dir")

    # a draft with no narration at all is a stated note, not a silent pass
    rep = sg.shotlist_report({"lines": [{"id": 1, "narration": ""}]}, PROJ)
    if not any("no text to measure" in n or "carry narration" in n
               for n in rep["notes"]):
        return False, "a draft with no narration does not say nothing was measured"
    checked.append("no narration")

    # a malformed sentence-level measurement is an ERROR, never an absence
    if sg.is_shotlist_sentence(None)[0]:
        return False, "is_shotlist_sentence(None) claims a shot list"
    return True, (f"{len(checked)} malformed input(s) come back as reports "
                  f"({', '.join(checked[:4])}, ...); a line with no id is "
                  f"still named; a missing project dir warns and states that "
                  f"the peaks are unknown")


TESTS = {
    "SHOT-LIST-BOTH-WAYS":    test_shot_list_both_ways,
    "AFTER-PEAK-BLOCKS":      test_after_peak_blocks,
    "PEAK-WINDOW-LIVE":       test_peak_window_live,
    "HOLD-AFTER-PEAK-CLEAN":  test_hold_after_peak_clean,
    "BARS-FROM-CONFIG":       test_bars_from_config,
    "PEAK-DEFINITION-SHARED": test_peak_definition_shared,
    "REAL-DRAFT-FAILS":       test_real_draft_fails,
    "OLD-DETECTOR-DILUTES":   test_old_detector_dilutes,
    "NO-ANGLE":               test_no_angle,
    "GATE-NEVER-RAISES":      test_gate_never_raises,
}

if __name__ == "__main__":
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
    print("test_shotlist_gates: all pass" if not bad else
          f"test_shotlist_gates: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
