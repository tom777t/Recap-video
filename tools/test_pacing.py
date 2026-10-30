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
    for k, v, op in (("top20_line_share",
                      config.PACING_TOP20_LINE_SHARE_MIN, "<"),
                     ("judgment_share",
                      config.PERSONA_JUDGMENT_SHARE_MIN, "<"),
                     ("frame_only_share",
                      config.PERSONA_FRAME_ONLY_SHARE_MAX, ">"),
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

    # 8 anchors x 4 lines, each ending on a narrator move
    for a in anchors:
        b = a["beats"][0]
        add(b, "He says the thing out loud and nobody argues with him.")
        add(b, '"You can\'t keep running," his father tells him.')
        add(b, "There is the whole problem, stated by the one adult who "
               "cannot enforce it.", "judgment")
        add(b, "You can see him decide, which is the only decision he makes "
               "all film.", "judgment")
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
