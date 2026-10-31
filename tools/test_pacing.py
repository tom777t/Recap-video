"""Contour, persona and continuity gates - with the shipped draft as the fixture.

THE COMPLAINT, and the numbers behind it
----------------------------------------
"Technically solid, but the writing feels rushed outside 2-3 scenes and the
narrator lacks a personal voice."

Measured on the shipped Tokyo Drift draft (kept at
projects/tokyodrift2006/draft_prerewrite.json and copied to
tools/fixtures/draft_tokyodrift_flat.json):

    beats                       80
    one-line beats              59
    longest one-line run         9   (calibrated max 4)
    top-20% line share       0.324   (floor 0.40)
    judgment share           0.132   (floor 0.22)
    frame-only share         0.208   (cap 0.15, references max 0.131)

Every bar is derived in docs/stage2/PACING_CALIBRATION.md from
references/voice/*.vtt, and the derivation says which measured statistics are
NOT usable and why.

Cases
-----
  CONTROL-ON-DISK        the calibration is recorded and agrees with config.
  TOP20-IS-THE-ROBUST-ONE  the statistic the main bar rests on holds across
                         five reference files while lines-per-scene does not -
                         so the choice of bar is evidenced, not preferred.
  BASIS-IS-DECLARED      the docs state the beat-vs-cue conversion, because
                         comparing the two bases was the trap.
  SHIPPED-DRAFT-FAILS    the shipped draft fails every new gate, with the
                         exact defects from the brief named.
  GOOD-SHAPE-PASSES      a synthetic draft with the intended shape passes, so
                         the bars are reachable and not merely strict.
  PERSONA-DETECTOR-SANE  the judgment share comes from the draft's own label
                         and reproduces 13.2%; the loose text detector that
                         scored the same draft 42.5% is gone.
  NAMED-DEFECTS          line 101 backward, lines 16/17 Tokyo, Arizona vs
                         Alabama, line 53 "visitor", line 105 "Cut to".
  ANGLE-SPEC-REQUIRED    a missing ANCHORS section fails loudly instead of
                         passing vacuously.

The four CEILING gates - the half the floor never had. Each is tested in both
directions and each names the fixture that proves it:

  PERSONA-CEILING        40% judgment fires, 30% is clean, and moving
                         config.PERSONA_JUDGMENT_SHARE_MAX moves the verdict
                         on the same draft.
  PERSONA-RUN            3 in a row fires, 2 does not, and a hold, a
                         film-speaks unit or a plain line each break the run.
                         The hold case FOUND A BUG - see the docstring.
  PEAK-ORDER             commentary first on a peak fires; the same lines
                         reordered are clean; 2 reactions fire; a non-peak
                         anchor with the same shape is ignored.
  ANCHOR-CLEAN           an all-commentary anchor fires; one plain line, or
                         one quotation, clears it.
  OVERCORRECTED-FIXTURE-FAILS
                         tools/fixtures/draft_tokyodrift_overcorrected.json
                         against projects/tokyodrift2006 - 9 findings:
                         52.3% judgment, longest run 5, 6 PEAK-ORDER, 2
                         anchors with no clean line. This fixture IS the
                         defect and must stay caught.
  PREREWRITE-SEPARATES   the same four gates produce 3 findings on
                         projects/tokyodrift2006/draft_prerewrite.json and
                         NEITHER overcorrection gate fires on it, so the bars
                         separate the two drafts instead of being always-on.

Run:  python tools/test_pacing.py
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from pipeline import angle_spec  # noqa: E402
from pipeline import continuity_gates as cg  # noqa: E402
from pipeline import pacing_gates as pg  # noqa: E402

PROJ = Path(config.project_dir("tokyodrift2006"))
FIX = Path(ROOT) / "tools" / "fixtures" / "draft_tokyodrift_flat.json"
CONTROL = Path(ROOT) / "config" / "pacing_control.json"
DOCS = Path(ROOT) / "docs" / "stage2" / "PACING_CALIBRATION.md"


def _flat():
    return json.loads(FIX.read_text(encoding="utf-8-sig"))


def test_control_on_disk() -> tuple[bool, str]:
    if not CONTROL.exists():
        return False, "config/pacing_control.json is missing"
    c = json.loads(CONTROL.read_text(encoding="utf-8"))
    en = (c.get("by_lang") or {}).get("en")
    if not en:
        return False, "the control records no English measurements"
    if en["n_files"] < 4:
        return False, f"only {en['n_files']} English file(s) measured"
    lo, md, hi = en["top20_line_share"]
    if not (0.35 <= lo <= hi <= 0.60):
        return False, (f"the reference top20 line share is {lo:.3f}-{hi:.3f}, "
                       f"outside the range the bar was derived in")
    if config.PACING_TOP20_LINE_SHARE_MIN > lo:
        return False, (f"the bar {config.PACING_TOP20_LINE_SHARE_MIN} is above "
                       f"the lowest reference {lo:.3f} on its own basis; after "
                       f"the 0.75 basis conversion that would be unreachable")
    return True, (f"{en['n_files']} English reference(s): top20 line share "
                  f"{lo:.3f}-{hi:.3f} (median {md:.3f}); bar "
                  f"{config.PACING_TOP20_LINE_SHARE_MIN}")


def test_top20_is_the_robust_one() -> tuple[bool, str]:
    """The bar rests on the statistic that holds, not the one that swings."""
    c = json.loads(CONTROL.read_text(encoding="utf-8"))
    en = (c.get("by_lang") or {}).get("en")
    t_lo, _t, t_hi = en["top20_runtime_share"]
    l_lo, _l, l_hi = en["lines_per_scene_mean"]
    t_spread = t_hi - t_lo
    l_spread = (l_hi / max(l_lo, 1e-6))
    if t_spread > 0.12:
        return False, (f"top20 runtime share spreads {t_spread:.3f} across the "
                       f"references; it is no longer the robust statistic and "
                       f"the bar needs rethinking")
    if l_spread < 2.0:
        return False, (f"lines-per-scene only spreads {l_spread:.1f}x, so the "
                       f"argument for preferring top20 no longer holds")
    return True, (f"top20 runtime share holds to {t_spread:.3f} while "
                  f"lines-per-scene swings {l_spread:.1f}x on the same five "
                  f"files - the bar rests on the stable one")


def test_basis_is_declared() -> tuple[bool, str]:
    if not DOCS.exists():
        return False, "docs/stage2/PACING_CALIBRATION.md is missing"
    t = DOCS.read_text(encoding="utf-8")
    for probe in ("0.310", "0.412", "basis", "0.75"):
        if probe not in t:
            return False, (f"the calibration does not record {probe!r}; the "
                           f"beat-vs-cue basis conversion is the trap this "
                           f"whole measurement had to avoid")
    return True, ("the docs record both bases (0.310 beats vs 0.412 cue on the "
                  "same draft) and the 0.75 conversion")


def test_shipped_draft_fails() -> tuple[bool, str]:
    if not FIX.exists():
        return False, f"the fixture {FIX.name} is missing"
    d = _flat()
    p = pg.pacing_report(d, PROJ)
    c = cg.continuity_report(d, PROJ)
    blob = " ".join(p["errors"] + c["errors"])
    want = {
        "PACING-CONTOUR": "the flat contour",
        "PERSONA": "the missing narrator voice",
        "BACKWARD-CLIP": "line 101 going backward",
        "REPEATED-EVENT": "lines 16 and 17",
        "FACT-CONSISTENCY": "Arizona vs Alabama",
    }
    missing = [f"{k} ({v})" for k, v in want.items() if k not in blob]
    if missing:
        return False, f"the shipped draft is NOT failed for: {missing}"
    n = len(p["errors"]) + len(c["errors"])
    if n < 10:
        return False, (f"only {n} error(s) on the shipped draft; the brief "
                       f"lists more defects than that")
    s = p["stats"]
    # frame_only_share is NOT in this list any more, and the reason is a
    # measurement rather than a convenience.
    #
    # The cap was re-derived from 0.13 to 0.20 because the old number
    # compared the references' per-SENTENCE share against our per-LINE share
    # - two different units - and the same rule applied on one basis gives
    # 0.20 (tools/calibrate_frame_only.py, config/frame_only_control.json).
    # The shipped fixture measures 0.142, so it now sits INSIDE the corrected
    # band and no longer demonstrates a frame-only defect.
    #
    # The fixture still demonstrates the three below, which is what it is
    # for. The alternative - putting the cap back to 0.13 so this assertion
    # keeps passing - would be keeping a bar because a test likes it, and
    # the specific defect the viewer objected to is now caught directly by
    # [SHOT-LIST-AFTER-PEAK] regardless of any share.
    for k, v, op in (("top20_line_share",
                      config.PACING_TOP20_LINE_SHARE_MIN, "<"),
                     ("judgment_share",
                      config.PERSONA_JUDGMENT_SHARE_MIN, "<"),
                     ("longest_one_line_run",
                      config.PACING_ONE_LINE_RUN_MAX, ">")):
        got = s.get(k)
        if got is None:
            return False, f"the report does not measure {k}"
        bad = got < v if op == "<" else got > v
        if not bad:
            return False, (f"{k} measured {got}, which does not violate its "
                           f"bar {op} {v} - the fixture no longer "
                           f"demonstrates the defect")
    return True, (f"{n} error(s) on the shipped draft: contour "
                  f"{s['top20_line_share']}, run {s['longest_one_line_run']}, "
                  f"judgment {s['judgment_share']}, frame-only "
                  f"{s['frame_only_share']}")


def test_good_shape_passes() -> tuple[bool, str]:
    """The bars must be reachable, or they are not a target but a wall."""
    spec = angle_spec.require(PROJ)
    anchors = spec["anchors"]
    lines = []
    lid = 0
    t = 100.0

    def add(beat, text, payload="reasoning"):
        nonlocal lid, t
        lid += 1
        lines.append({
            "id": lid, "note": beat, "payload": payload,
            "narration": text, "delivery": "normal",
            "clip_start": "%02d:%02d:%06.3f" % (int(t) // 3600,
                                                (int(t) % 3600) // 60,
                                                t % 60),
            "clip_end": "%02d:%02d:%06.3f" % (int(t + 8) // 3600,
                                              (int(t + 8) % 3600) // 60,
                                              (t + 8) % 60)})
        t += 9.0

    # 8 anchors x 4 lines: the moment first, the narrator LAST and ONCE.
    #
    # This block used to end on TWO judgment lines, and when the persona
    # ceiling, the run cap and the peak-order rule arrived it failed all
    # three - a fixture built to satisfy a floor with no ceiling had encoded
    # the very shape the ceiling exists to stop (every anchor peaking on two
    # consecutive pieces of commentary, 41.9% judgment overall).
    #
    # The fixture was changed rather than the bars, and the distinction
    # matters: this is a SYNTHETIC shape demonstrator written to prove the
    # contour bars are reachable, not an externally validated piece of
    # writing. Had it been a real reference draft that failed, the bar would
    # have been the thing to move - that is the standing rule, and it is why
    # the reference-derived bars elsewhere were lowered to fit the references
    # rather than the references dismissed.
    for a in anchors:
        b = a["beats"][0]
        add(b, "He says the thing out loud and nobody argues with him.")
        add(b, '"You can\'t keep running," his father tells him.')
        add(b, "The room goes quiet and he picks his bag back up.")
        add(b, "You can see him decide, and it is the last time anyone has "
               "to tell him.", "judgment")
    # connective beats: single lines, with a silent beat every few to break
    # the run, and a judgment line often enough to clear the floor
    for i in range(40):
        beat = f"C{i:02d}"
        if i % 4 == 3:
            lid += 1
            lines.append({"id": lid, "note": beat, "narration": "",
                          "narration_silence_seconds": 3.0,
                          "delivery": "normal",
                          "clip_start": "00:50:00.000",
                          "clip_end": "00:50:03.000"})
            continue
        pay = "judgment" if i % 3 == 0 else "stake"
        txt = ("Which is why that was never going to hold for long."
               if pay == "judgment" else
               "The crew moves the shipment before anyone notices.")
        add(beat, txt, pay)
    draft = {"lines": lines}
    p = pg.pacing_report(draft, PROJ)
    hard = [e for e in p["errors"] if "PACING-CONTOUR" in e or "PERSONA" in e]
    if hard:
        return False, ("the intended shape does not pass its own bars: "
                       + " | ".join(x[:150] for x in hard[:3]))
    s = p["stats"]
    return True, (f"the intended shape passes: top20 {s['top20_line_share']}, "
                  f"run {s['longest_one_line_run']}, judgment "
                  f"{s['judgment_share']}, frame-only {s['frame_only_share']}")


def test_persona_detector_sane() -> tuple[bool, str]:
    src = io.open(os.path.join(ROOT, "pipeline", "pacing_gates.py"),
                  encoding="utf-8").read()
    if "_JUDGMENT = re.compile" in src:
        return False, ("the loose judgment regex is back; it scored the "
                       "shipped draft 42.5% against its own label's 13.2% and "
                       "PASSED a draft with no voice")
    if 'payload") or "").strip().lower() == "judgment"' not in src:
        return False, "the judgment share no longer reads the draft's own label"
    d = _flat()
    p = pg.pacing_report(d, PROJ)
    lab = p["stats"].get("judgment_labelled")
    agreed = p["stats"].get("judgment_share")
    if lab != 14:
        return False, (f"the draft's own label count is {lab}, not the 14 the "
                       f"brief quotes")
    if agreed is None or abs(agreed - 0.104) > 0.01:
        return False, (f"agreed judgment share measured {agreed}, not the "
                       f"0.104 measured on the shipped draft")
    return True, (f"the label gives 14 of 106 (13.2%, the brief's figure) and "
                  f"the agreed share is {agreed} - the gate counts the "
                  f"intersection, not the claim")


def test_named_defects() -> tuple[bool, str]:
    d = _flat()
    bc = cg.backward_clips(d)
    if not any(r["line_id"] == 101 for r in bc):
        return False, "line 101's backward clip_start is not detected"
    rp = cg.repeated_events(d)
    if not any({r["a"], r["b"]} == {16, 17} for r in rp):
        return False, (f"lines 16 and 17 (both landing him in Tokyo) are not "
                       f"detected; got {rp}")
    fc = cg.fact_conflicts(d, PROJ)
    if not any("Alabama" in r["msg"] and "Arizona" in r["msg"] for r in fc):
        return False, "the Arizona/Alabama conflict is not detected"
    ck = cg.chekhov(d)
    if not any(r["noun"] == "visitor" for r in ck):
        return False, f"line 53's unexplained visitor is not detected: {ck}"
    if len(ck) > 6:
        return False, (f"CHEKHOV reports {len(ck)} setups; a list that long is "
                       f"read as zero and buries the real finding")
    p = pg.pacing_report(d, PROJ)
    if not any("Cut to" in e for e in p["errors"]):
        return False, "line 105's \"Cut to\" is not detected"
    return True, ("line 101 backward, lines 16/17 Tokyo, Arizona vs Alabama, "
                  f"line 53 \"visitor\" ({len(ck)} CHEKHOV finding(s)), and "
                  f"line 105 \"Cut to\" are all caught")


def test_angle_spec_required() -> tuple[bool, str]:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "angle.md").write_text("# x\n\n## ANGLE\n\nsomething\n",
                                    encoding="utf-8")
        try:
            angle_spec.require(p)
        except angle_spec.AngleSpecError as e:
            if "ANCHORS" not in str(e):
                return False, f"the error does not name the missing section: {e}"
        else:
            return False, ("an angle.md with no ANCHORS section was accepted; "
                           "an empty anchor list makes PACING-CONTOUR pass on "
                           "every draft ever written")
        rep = pg.pacing_report({"lines": []}, p)
        if not rep["errors"]:
            return False, "the gate passes when the spec cannot be read"
    spec = angle_spec.require(PROJ)
    if not (config.PACING_ANCHORS_MIN <= len(spec["anchors"])
            <= config.PACING_ANCHORS_MAX):
        return False, (f"the real angle names {len(spec['anchors'])} anchors, "
                       f"outside {config.PACING_ANCHORS_MIN}-"
                       f"{config.PACING_ANCHORS_MAX}")
    if not spec["promises"]:
        return False, "the real angle declares no hook promises"
    return True, (f"a missing ANCHORS section fails loudly; the real angle has "
                  f"{len(spec['anchors'])} anchors and "
                  f"{len(spec['promises'])} hook promise(s)")



def test_anchor_evidence_verbatim() -> tuple[bool, str]:
    """A mapping is checked against the BEAT MAP, not against its own claim.

    The defect: "before he has learned to turn" mapped to B47/B52/B53, where
    B47 is "DK's uncle takes a cut of everyone's action", B52 is a car
    handover, and B53 is him still unable to drift - while B60, the only beat
    where the turning is taught, was filed as footage-only texture.
    """
    from pipeline import beats_spec as bs
    bm = bs.load_beats(PROJ)
    if len(bm) < 50:
        return False, f"the beat map parsed only {len(bm)} beats"
    # the OLD mapping must fail
    ok, why = bs.quote_supported("told to drift by feeling",
                                 ["B47", "B52", "B53"], bm)
    if ok:
        return False, ("the teaching quote verifies against B47/B52/B53, so "
                       "the beat map no longer demonstrates the defect")
    if "closest is" not in why:
        return False, f"the failure does not diagnose the near miss: {why}"
    # the NEW mapping must verify
    ok2, why2 = bs.quote_supported(
        "told to drift by feeling, he runs the hairpins again and again",
        ["B35", "B53", "B60"], bm)
    if not ok2:
        return False, f"the derived mapping does not verify: {why2}"
    if why2 != "B60":
        return False, f"the quote verified against {why2}, expected B60"
    # a too-short quote is refused rather than trivially matched
    ok3, _ = bs.quote_supported("drift", ["B60"], bm)
    if ok3:
        return False, "a 5-character quote was accepted as evidence"
    return True, ("the old B47/B52/B53 mapping fails the verbatim check and "
                  "names the near miss; the derived B60 mapping verifies; a "
                  "too-short quote is refused")


def test_anchor_evidence_required() -> tuple[bool, str]:
    """No evidence, or a load-bearing beat also filed as texture, fails."""
    import shutil
    import tempfile
    fix = Path(ROOT) / "tools" / "fixtures" / "angle_tokyodrift_unevidenced.md"
    if not fix.exists():
        return False, "the unevidenced-angle fixture is missing"
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        shutil.copy(fix, d / "angle.md")
        shutil.copy(PROJ / "beats_proposal.md", d / "beats_proposal.md")
        try:
            angle_spec.require(d)
        except angle_spec.AngleSpecError as e:
            if "evidence" not in str(e).lower():
                return False, f"the error does not demand evidence: {e}"
        else:
            return False, ("an angle with no evidence quotes was accepted - "
                           "which is the state that let B47 through")

        # A MINIMAL VALID angle, then one beat made both anchor and texture.
        # Built from scratch rather than patched into the fixture: patching
        # left other evidence quotes missing, so ANGLE-SPEC fired first and
        # the clash was never reached.
        ev = ("told to drift by feeling, he runs the hairpins again and "
              "again")
        ang = (
            "# x\n\n## ANCHORS\n\n"
            + "".join(
                f'- **B60** | kind{i} | why | evidence: "{ev}"\n'
                for i in range(5))
            + '\n## HOOK PROMISES\n\n- "a promise" -> B60 | note | '
              f'evidence: "{ev}"\n'
              "\n## NARRATOR PERSONA\n\n**Stance:** dry\n\n"
              "**Signature moves:**\n- direct address\n\n"
              "**Never:**\n- jargon\n"
              "\n## WHAT THE ANGLE SELECTS\n\n"
              "- B60 (training montage) - footage-only texture.\n")
        (d / "angle.md").write_text(ang, encoding="utf-8")
        rep = pg.pacing_report({"lines": []}, d)
        blob = " ".join(rep["errors"])
        if "both load-bearing" not in blob:
            return False, ("a beat that is an anchor AND listed as "
                           f"footage-only was not reported: {blob[:220]}")
    rep2 = pg.pacing_report(_flat(), PROJ)
    ae = [e for e in rep2["errors"] if "ANCHOR-EVIDENCE" in e]
    if ae:
        return False, f"the corrected angle still fails: {ae[0][:180]}"
    return True, ("a missing evidence quote and an anchor-and-texture clash "
                  "both fail; the corrected angle passes")


def test_audit_covers_mappings() -> tuple[bool, str]:
    """The independent audit is a required artifact, not an intention."""
    audit = Path(ROOT) / "docs" / "stage2" / "ANGLE_EVIDENCE_AUDIT.md"
    if not audit.exists():
        return False, "docs/stage2/ANGLE_EVIDENCE_AUDIT.md is missing"
    t = audit.read_text(encoding="utf-8", errors="replace").lower()
    spec = angle_spec.require(PROJ)
    for pr in spec["promises"]:
        if pr["clause"].lower() not in t:
            return False, f"the audit does not cover \"{pr['clause']}\""
    for a in spec["anchors"]:
        for b in a["beats"]:
            if b.lower() not in t:
                return False, f"the audit does not mention anchor beat {b}"
    for probe in ("b47", "b52", "b60", "car handover"):
        if probe not in t:
            return False, (f"the audit does not record {probe!r} - the "
                           f"overturned mapping has to stay on the record")
    return True, (f"the audit covers all {len(spec['promises'])} promises and "
                  f"all anchor beats, and records what it overturned")


def test_judgment_agreement() -> tuple[bool, str]:
    """Count only where the writer's label and the classifier AGREE."""
    d = _flat()
    rep = pg.pacing_report(d, PROJ)
    s = rep["stats"]
    for k in ("judgment_labelled", "judgment_classified", "judgment_agreed",
              "judgment_agreement_rate"):
        if k not in s:
            return False, f"the report does not expose {k}"
    if s["judgment_labelled"] != 14:
        return False, (f"the shipped draft labels {s['judgment_labelled']} "
                       f"lines judgment, not the 14 this was calibrated on")
    if s["judgment_agreed"] >= s["judgment_labelled"]:
        return False, ("label and classifier agree on everything, so the "
                       "agreement check is not discriminating")
    if abs(s["judgment_share"] - 0.104) > 0.01:
        return False, (f"agreed share measured {s['judgment_share']}, not the "
                       f"0.104 calibrated on the shipped draft")
    # the shipped draft must fail on the SHARE, not on the RATE: its labels
    # are honest, there are simply too few of them
    if s["judgment_agreement_rate"] < config.PERSONA_JUDGMENT_AGREEMENT_MIN:
        return False, (f"the shipped draft fails the agreement RATE "
                       f"({s['judgment_agreement_rate']}), but its labels are "
                       f"honest - it should fail the share instead")
    # ...and label inflation must fail the rate
    import copy
    g = copy.deepcopy(d)
    for ln in g["lines"]:
        if str(ln.get("narration") or "").strip():
            ln["payload"] = "judgment"
    rep2 = pg.pacing_report(g, PROJ)
    blob = " ".join(rep2["errors"])
    if "label inflation" not in blob:
        return False, ("labelling every line judgment did not trip the "
                       "agreement rate - the gate is gameable exactly as "
                       "before")
    s2 = rep2["stats"]
    if s2["judgment_share"] < config.PERSONA_JUDGMENT_SHARE_MIN:
        return False, ("the gamed draft still fails the share, so the rate "
                       "check was not what caught it")
    return True, (f"shipped: label {s['judgment_labelled']}, classifier "
                  f"{s['judgment_classified']}, agreed {s['judgment_agreed']} "
                  f"({s['judgment_share']:.1%}), rate "
                  f"{s['judgment_agreement_rate']:.0%} - fails the share, "
                  f"passes the rate; labelling everything judgment trips the "
                  f"rate instead")


def test_classifier_corrected() -> tuple[bool, str]:
    """The classifier's two known bugs stay fixed."""
    # "US Navy" must not read as the pronoun "us"
    if pg.classify_judgment("a US Navy officer he has barely seen")[0]:
        return False, ("\"US Navy\" is still classified as narrator stance - "
                       "\\bus\\b matching a country code")
    # quoted character speech is not narrator voice
    if pg.classify_judgment('He asks, "where are we moving to?"')[0]:
        return False, ("quoted character speech is still read as narrator "
                       "stance")
    # evaluation without a pronoun must be caught - the first version missed
    # all of these and scored 3 of the writer's 14
    for t in ("There's the mistake.",
              "The hustler with the ridiculous van is the loyalest person in "
              "this film.",
              "That's the whole of his pride. Borrowed, and ugly with it."):
        if not pg.classify_judgment(t)[0]:
            return False, f"evaluation without a pronoun is still missed: {t!r}"
    return True, ("\"US Navy\" and quoted speech are not stance; pronoun-free "
                  "evaluation is caught")

# --------------------------------------------------------------------------- #
# The four DRAFT-STAGE CEILING gates. Every one is tested in BOTH directions,
# because a gate that only fires, or only stays silent, is not tested at all.
#
# The fixture that proves each of them is named in its own docstring and in the
# three registries' rows where the format allows it (see the note at the foot
# of docs/WRITING_CRAFT_CRITERION.md).
# --------------------------------------------------------------------------- #

PRE = PROJ / "draft_prerewrite.json"
OVER = Path(ROOT) / "tools" / "fixtures" / "draft_tokyodrift_overcorrected.json"
_CEILING_GATES = ("PERSONA-CEILING", "PERSONA-RUN", "PEAK-ORDER",
                  "ANCHOR-CLEAN")

# The three sentence shapes the persona gates sort lines into. Each test
# asserts, before it asserts anything else, that the classifier really does
# read them that way - a synthetic fixture whose vocabulary has drifted
# produces a green run that measures nothing.
_PG_J = "You can see him decide, and that is the whole of his pride."
_PG_P = "He parks the car outside the garage and waits."
_PG_Q = '"Pick a car," the older man tells him, and walks off.'


def _fixture_vocabulary_problem() -> str:
    if not pg.classify_judgment(_PG_J)[0]:
        return f"the judgment sentence is NOT classified as judgment: {_PG_J!r}"
    if pg.classify_judgment(_PG_P)[0]:
        return f"the plain sentence IS classified as judgment: {_PG_P!r}"
    if pg.classify_judgment(_PG_Q)[0]:
        return f"the quoted line IS classified as judgment: {_PG_Q!r}"
    return ""


def _pg_ts(t: float) -> str:
    return "%02d:%02d:%06.3f" % (int(t) // 3600, (int(t) % 3600) // 60, t % 60)


def _mkdraft(units: list) -> dict:
    """(kind, beat) pairs -> a draft.

    kind: J a judgment line (labelled AND classified), P a plain line,
          Q a quotation, H a hold, F a film-speaks unit. H and F carry NO
          narration, which is the whole point of the PERSONA-RUN case below.
    """
    lines = []
    t = 100.0
    for i, (kind, beat) in enumerate(units, 1):
        ln = {"id": i, "note": beat, "delivery": "normal",
              "clip_start": _pg_ts(t), "clip_end": _pg_ts(t + 8.0)}
        t += 9.0
        if kind == "J":
            ln.update({"narration": _PG_J, "payload": "judgment"})
        elif kind == "P":
            ln.update({"narration": _PG_P, "payload": "stake"})
        elif kind == "Q":
            ln.update({"narration": _PG_Q, "payload": "stake"})
        elif kind == "H":
            ln.update({"narration": "", "narration_silence_seconds": 3.0})
        elif kind == "F":
            ln.update({"narration": "", "film_speaks_seconds": 6.0})
        else:
            raise ValueError(f"unknown unit kind {kind!r}")
        lines.append(ln)
    return {"lines": lines}


def _hits(draft: dict, gate: str) -> list:
    rep = pg.pacing_report(draft, PROJ)
    return [e for e in rep["errors"] if e.startswith(f"[{gate}]")]


def _anchor(peak: bool):
    """The first anchor the angle declares that is (or is not) a PEAK."""
    words = ("reveal", "death", "dies", "peak", "win", "climax")
    for a in angle_spec.require(PROJ)["anchors"]:
        blob = f"{a.get('kind', '')} {a.get('why', '')}".lower()
        if any(w in blob for w in words) == peak:
            return a
    return None


def test_persona_ceiling() -> tuple[bool, str]:
    """[PERSONA-CEILING] both directions, and the bar is read from config.

    Fixture: synthetic (20 lines, judgment share dialled exactly); the real
    one is tools/fixtures/draft_tokyodrift_overcorrected.json at 52.3%.
    """
    bad = _fixture_vocabulary_problem()
    if bad:
        return False, f"the fixture vocabulary is wrong: {bad}"
    over = _mkdraft([("J" if i < 8 else "P", f"C{i:02d}") for i in range(20)])
    if not _hits(over, "PERSONA-CEILING"):
        return False, ("8 judgment lines in 20 (40.0%) did not breach the "
                       f"{config.PERSONA_JUDGMENT_SHARE_MAX:.0%} ceiling")
    under = _mkdraft([("J" if i < 6 else "P", f"C{i:02d}") for i in range(20)])
    quiet = _hits(under, "PERSONA-CEILING")
    if quiet:
        return False, (f"6 of 20 (30.0%) is under the ceiling but fired: "
                       f"{quiet[0][:140]}")
    # THE BAR IS NOT A LITERAL. Move the constant and the verdict on the SAME
    # draft must move with it - otherwise the gate carries its own copy of
    # 0.35 and config is decoration.
    _old = config.PERSONA_JUDGMENT_SHARE_MAX
    try:
        config.PERSONA_JUDGMENT_SHARE_MAX = 0.25
        moved = _hits(under, "PERSONA-CEILING")
    finally:
        config.PERSONA_JUDGMENT_SHARE_MAX = _old
    if not moved:
        return False, ("lowering config.PERSONA_JUDGMENT_SHARE_MAX to 0.25 "
                       "did not fail the 30.0% draft - the bar is not read "
                       "from config at call time")
    if "25% ceiling" not in moved[0]:
        return False, (f"the message still quotes the old ceiling: "
                       f"{moved[0][:140]}")
    if _hits(under, "PERSONA-CEILING"):
        return False, "restoring the constant did not restore the verdict"
    return True, (f"40.0% fires, 30.0% is clean at the "
                  f"{_old:.0%} ceiling; moving the constant to 25% fails the "
                  f"same 30.0% draft and the message quotes the new bar")


def test_persona_run() -> tuple[bool, str]:
    """[PERSONA-RUN] both directions, and a hold really does break a run.

    Fixture: synthetic; the real one is the overcorrected draft (8 places, the
    longest 5 lines back to back).

    THIS TEST FOUND A BUG. The documented behaviour - "a hold or a film-speaks
    unit breaks it" - was NOT real: the run loop iterated the NARRATED lines,
    and a hold and a film-speaks unit both carry empty narration, so both were
    invisible to it and "judgment, judgment, hold, judgment" reported a run of
    3. The gate's own error text tells the writer to break a run with a hold,
    and doing so did not clear the error. Fixed in pacing_gates.py; this case
    is the regression test.
    """
    bad = _fixture_vocabulary_problem()
    if bad:
        return False, f"the fixture vocabulary is wrong: {bad}"
    rmax = config.PERSONA_JUDGMENT_RUN_MAX
    three = _mkdraft([("J", "C01"), ("J", "C02"), ("J", "C03"), ("P", "C04")])
    fired = _hits(three, "PERSONA-RUN")
    if not fired:
        return False, f"{rmax + 1} consecutive judgment lines did not fire"
    if f"longest {rmax + 1}" not in fired[0]:
        return False, f"the finding does not state the run length: {fired[0][:140]}"
    two = _mkdraft([("J", "C01"), ("J", "C02"), ("P", "C03")])
    if _hits(two, "PERSONA-RUN"):
        return False, (f"{rmax} consecutive judgment lines fired, but the "
                       f"maximum is {rmax}")
    # the three documented breakers
    for kind, what in (("H", "a hold"), ("F", "a film-speaks unit"),
                       ("P", "a plain line")):
        broken = _mkdraft([("J", "C01"), ("J", "C02"), (kind, "C03"),
                           ("J", "C04")])
        got = _hits(broken, "PERSONA-RUN")
        if got:
            return False, (f"{what} between judgment lines did NOT break the "
                           f"run - the gate tells writers to do exactly this: "
                           f"{got[0][:140]}")
    _old = config.PERSONA_JUDGMENT_RUN_MAX
    try:
        config.PERSONA_JUDGMENT_RUN_MAX = 3
        relaxed = _hits(three, "PERSONA-RUN")
    finally:
        config.PERSONA_JUDGMENT_RUN_MAX = _old
    if relaxed:
        return False, ("raising config.PERSONA_JUDGMENT_RUN_MAX to 3 did not "
                       "clear a run of 3 - the bar is not read from config")
    return True, (f"{rmax + 1} in a row fires and names the length, {rmax} is "
                  f"clean, and a hold, a film-speaks unit and a plain line "
                  f"each break the run (the hold/film-speaks case was BROKEN "
                  f"until this test; see the docstring)")


def test_peak_order() -> tuple[bool, str]:
    """[PEAK-ORDER] the moment lands before the opinion of it.

    Fixture: synthetic, bound to the first PEAK anchor the real angle.md
    declares; the real one is the overcorrected draft (6 findings).
    """
    bad = _fixture_vocabulary_problem()
    if bad:
        return False, f"the fixture vocabulary is wrong: {bad}"
    a = _anchor(peak=True)
    if a is None:
        return False, ("the real angle.md declares no anchor whose kind/why "
                       "names a peak, so this gate cannot be reached at all")
    b = a["beats"][0]
    first_is_cmt = _hits(_mkdraft([("J", b), ("P", b), ("P", b)]), "PEAK-ORDER")
    if not any("first line on peak" in e for e in first_is_cmt):
        return False, (f"opening peak {b} on commentary was not reported: "
                       f"{first_is_cmt}")
    reordered = _hits(_mkdraft([("P", b), ("J", b), ("P", b)]), "PEAK-ORDER")
    if reordered:
        return False, (f"the SAME three lines with the action first still "
                       f"fail, so the gate is not reading order: "
                       f"{reordered[0][:160]}")
    pmax = config.PERSONA_PEAK_REACTION_MAX
    many = _hits(_mkdraft([("P", b), ("J", b), ("J", b)]), "PEAK-ORDER")
    if not any("reaction lines" in e for e in many):
        return False, (f"{pmax + 1} reaction lines on peak {b} (max {pmax}) "
                       f"were not reported: {many}")
    if any("first line on peak" in e for e in many):
        return False, ("the action-first draft was ALSO reported for order - "
                       "the two halves of the gate are not separable")
    # a non-peak anchor with the same shape must be ignored: the gate reads
    # the angle's declaration, not a keyword hunt over the narration.
    na = _anchor(peak=False)
    if na is not None:
        quiet = _hits(_mkdraft([("J", na["beats"][0]), ("J", na["beats"][0]),
                                ("P", na["beats"][0])]), "PEAK-ORDER")
        if quiet:
            return False, (f"the same shape on the NON-peak anchor "
                           f"{'/'.join(na['beats'])} ({na['kind']}) also "
                           f"fired: {quiet[0][:140]}")
    return True, (f"on peak {b} ({a['kind']}): commentary first fires, the "
                  f"same lines reordered are clean, {pmax + 1} reactions "
                  f"fires; the non-peak anchor "
                  f"{'/'.join(na['beats']) if na else '-'} is ignored")


def test_anchor_clean() -> tuple[bool, str]:
    """[ANCHOR-CLEAN] an anchor keeps at least one line that is just the moment.

    Fixture: synthetic, bound to the first NON-peak anchor (so PEAK-ORDER
    cannot be what is firing); the real one is the overcorrected draft
    (B58 and B65, 4 lines each, 0 without commentary).
    """
    bad = _fixture_vocabulary_problem()
    if bad:
        return False, f"the fixture vocabulary is wrong: {bad}"
    a = _anchor(peak=False)
    if a is None:
        return False, "the real angle.md declares no non-peak anchor"
    b = a["beats"][0]
    cmin = config.PERSONA_ANCHOR_CLEAN_LINES_MIN
    dirty = _hits(_mkdraft([("J", b), ("J", b), ("J", b)]), "ANCHOR-CLEAN")
    if not dirty:
        return False, (f"an anchor whose every line is commentary did not "
                       f"fire the {cmin}-clean-line floor")
    if f"{b} (3 lines, 0 without commentary)" not in dirty[0]:
        return False, f"the finding does not count the lines: {dirty[0][:160]}"
    clean = _hits(_mkdraft([("J", b), ("J", b), ("J", b), ("P", b)]),
                  "ANCHOR-CLEAN")
    if clean:
        return False, (f"adding one plain line did not clear it: "
                       f"{clean[0][:160]}")
    # a QUOTATION is a clean line too - that is the gate's stated intent
    quoted = _hits(_mkdraft([("J", b), ("J", b), ("Q", b)]), "ANCHOR-CLEAN")
    if quoted:
        return False, (f"a quotation does not count as a line that is purely "
                       f"the moment: {quoted[0][:160]}")
    _old = config.PERSONA_ANCHOR_CLEAN_LINES_MIN
    try:
        config.PERSONA_ANCHOR_CLEAN_LINES_MIN = 2
        stricter = _hits(_mkdraft([("J", b), ("J", b), ("J", b), ("P", b)]),
                         "ANCHOR-CLEAN")
    finally:
        config.PERSONA_ANCHOR_CLEAN_LINES_MIN = _old
    if not stricter:
        return False, ("raising config.PERSONA_ANCHOR_CLEAN_LINES_MIN to 2 "
                       "did not fail a draft with one clean line - the bar is "
                       "not read from config")
    return True, (f"anchor {b} ({a['kind']}) with 3 commentary lines and 0 "
                  f"clean fires; one plain line clears it; a quotation counts "
                  f"as clean; raising the floor to 2 fails it again")


def _ceiling_counts(path: Path) -> tuple:
    d = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    rep = pg.pacing_report(d, PROJ)
    per = {g: [e for e in rep["errors"] if e.startswith(f"[{g}]")]
           for g in _CEILING_GATES}
    return per, rep["stats"]


def test_overcorrected_fixture_fails() -> tuple[bool, str]:
    """THE DEFECT ITSELF. All four ceiling gates must stay caught on it.

    Measured 2026-10-30 on tools/fixtures/draft_tokyodrift_overcorrected.json
    against projects/tokyodrift2006 (111 narrated lines of 114):

        PERSONA-CEILING  58 of 111 lines (52.3%) judgment, ceiling 35%
        PERSONA-RUN      8 places over the run cap of 2, the longest 5
        PEAK-ORDER       6 findings: B65 and B79/B80 open on commentary;
                         B13 x3, B65 x4, B79/B80 x5 and B101 x3 reactions
                         against a cap of 1
        ANCHOR-CLEAN     2 anchors with no clean line (B58 and B65, 4 lines
                         each, 0 without commentary)
    """
    if not OVER.exists():
        return False, f"the fixture {OVER.name} is missing"
    per, s = _ceiling_counts(OVER)
    silent = [g for g in _CEILING_GATES if not per[g]]
    if silent:
        return False, (f"the overcorrected fixture no longer fires: {silent}. "
                       f"That fixture IS the defect; if it passes, the gates "
                       f"stopped measuring, not the draft stopped offending.")
    if s.get("judgment_share", 0) <= config.PERSONA_JUDGMENT_SHARE_MAX:
        return False, (f"judgment share measured {s.get('judgment_share')}, "
                       f"not over the {config.PERSONA_JUDGMENT_SHARE_MAX} "
                       f"ceiling - the fixture no longer demonstrates it")
    if s.get("longest_judgment_run", 0) <= config.PERSONA_JUDGMENT_RUN_MAX:
        return False, (f"longest judgment run measured "
                       f"{s.get('longest_judgment_run')}, inside the cap")
    order = sum(1 for e in per["PEAK-ORDER"] if "first line on peak" in e)
    react = sum(1 for e in per["PEAK-ORDER"] if "reaction lines" in e)
    if not (order and react):
        return False, (f"PEAK-ORDER fires only one of its two halves "
                       f"(order={order}, reactions={react})")
    n = sum(len(v) for v in per.values())
    return True, (f"{n} finding(s): judgment share {s['judgment_share']:.3f} "
                  f"(ceiling {config.PERSONA_JUDGMENT_SHARE_MAX}), longest "
                  f"run {s['longest_judgment_run']} (cap "
                  f"{config.PERSONA_JUDGMENT_RUN_MAX}), PEAK-ORDER "
                  f"{len(per['PEAK-ORDER'])} ({order} order + {react} "
                  f"reaction-count), ANCHOR-CLEAN {len(per['ANCHOR-CLEAN'])}")


def test_prerewrite_separates() -> tuple[bool, str]:
    """The gates must SEPARATE the two drafts, not fire on everything.

    The pre-rewrite draft is the OPPOSITE defect - too flat, not too loud - so
    the two overcorrection gates (PERSONA-CEILING, PERSONA-RUN) must be silent
    on it. Measured 2026-10-30: 9 findings on the overcorrected draft against
    3 on the pre-rewrite one (2 x PEAK-ORDER order, 1 x ANCHOR-CLEAN), and the
    two ceiling gates fire on the overcorrected draft only.
    """
    if not PRE.exists():
        return False, f"{PRE} is missing"
    over, _ = _ceiling_counts(OVER)
    pre, pres = _ceiling_counts(PRE)
    n_over = sum(len(v) for v in over.values())
    n_pre = sum(len(v) for v in pre.values())
    for g in ("PERSONA-CEILING", "PERSONA-RUN"):
        if pre[g]:
            return False, (f"{g} fires on the PRE-REWRITE draft "
                           f"(judgment share {pres.get('judgment_share')}, "
                           f"longest run {pres.get('longest_judgment_run')}) "
                           f"- a gate aimed at overcorrection that also fails "
                           f"the flat draft separates nothing: "
                           f"{pre[g][0][:140]}")
    if n_pre != 3:
        return False, (f"the pre-rewrite draft produces {n_pre} of these "
                       f"findings, not the 3 measured; recheck which, and "
                       f"whether the change was intended: "
                       + "; ".join(f"{g}={len(v)}" for g, v in pre.items()))
    if n_over <= n_pre:
        return False, (f"the overcorrected draft produces {n_over} findings "
                       f"and the pre-rewrite one {n_pre} - the gates do not "
                       f"separate the two drafts")
    return True, (f"overcorrected {n_over} finding(s) vs pre-rewrite "
                  f"{n_pre} ("
                  + ", ".join(f"{g} {len(over[g])}/{len(pre[g])}"
                              for g in _CEILING_GATES)
                  + f"); the two overcorrection gates are silent on the flat "
                    f"draft (share {pres.get('judgment_share')}, run "
                    f"{pres.get('longest_judgment_run')})")


TESTS = {
    "CONTROL-ON-DISK":          test_control_on_disk,
    "TOP20-IS-THE-ROBUST-ONE":  test_top20_is_the_robust_one,
    "BASIS-IS-DECLARED":        test_basis_is_declared,
    "SHIPPED-DRAFT-FAILS":      test_shipped_draft_fails,
    "GOOD-SHAPE-PASSES":        test_good_shape_passes,
    "PERSONA-DETECTOR-SANE":    test_persona_detector_sane,
    "NAMED-DEFECTS":            test_named_defects,
    "ANGLE-SPEC-REQUIRED":      test_angle_spec_required,
    "ANCHOR-EVIDENCE-VERBATIM": test_anchor_evidence_verbatim,
    "ANCHOR-EVIDENCE-REQUIRED": test_anchor_evidence_required,
    "AUDIT-COVERS-MAPPINGS":    test_audit_covers_mappings,
    "JUDGMENT-AGREEMENT":       test_judgment_agreement,
    "CLASSIFIER-CORRECTED":     test_classifier_corrected,
    "PERSONA-CEILING":          test_persona_ceiling,
    "PERSONA-RUN":              test_persona_run,
    "PEAK-ORDER":               test_peak_order,
    "ANCHOR-CLEAN":             test_anchor_clean,
    "OVERCORRECTED-FIXTURE-FAILS": test_overcorrected_fixture_fails,
    "PREREWRITE-SEPARATES":     test_prerewrite_separates,
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
    print("test_pacing: all pass" if not bad else
          f"test_pacing: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
