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
    for k, v, op in (("top20_line_share", 0.40, "<"),
                     ("judgment_share", 0.22, "<"),
                     ("frame_only_share", 0.15, ">"),
                     ("longest_one_line_run", 4, ">")):
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
        add(b, "The room goes quiet for a second longer than it needs to.")
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
        txt = ("Which is about as well as that was ever going to go."
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
    got = p["stats"].get("judgment_share")
    if got is None or abs(got - 0.132) > 0.01:
        return False, (f"judgment share measured {got}, not the 0.132 the "
                       f"draft's own payload labels give (14 of 106)")
    return True, (f"judgment share {got} comes from the draft's payload label "
                  f"and matches the brief's 14/109")


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


TESTS = {
    "CONTROL-ON-DISK":          test_control_on_disk,
    "TOP20-IS-THE-ROBUST-ONE":  test_top20_is_the_robust_one,
    "BASIS-IS-DECLARED":        test_basis_is_declared,
    "SHIPPED-DRAFT-FAILS":      test_shipped_draft_fails,
    "GOOD-SHAPE-PASSES":        test_good_shape_passes,
    "PERSONA-DETECTOR-SANE":    test_persona_detector_sane,
    "NAMED-DEFECTS":            test_named_defects,
    "ANGLE-SPEC-REQUIRED":      test_angle_spec_required,
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
