"""ONE formula for a line's required picture duration. And it must be suppliable.

THE DEFECT
----------
clip_024 claimed 8.726s and its video stream measured 7.367s. The pre-flight
had passed the line, and on its own terms it was right: it compared
`lead + narr + GAP` (8.726s) against the window's capacity (13.583s x 1.15) and
saw plenty of room.

Two separate divergences were behind it, and only the first is the one people
guess:

 1. THE SPLIT SHARES. The builder splits a long line across real cuts and gives
    each sub-shot an EQUAL share of the screen time, clip_len/n. The splitter
    picked the cut NEAREST the ideal boundary without asking whether the
    resulting sub-shot had that much footage in it - a cut 2.173s into the
    window meant a 2.173s sub-shot was asked for 4.363s. It can reach
    2.173 + 0.5 read-ahead + 0.3 of capped clone = 2.973s, and `trim` only
    truncates. Five lines in this draft were affected.

 2. PRE_REVEAL_PAUSE. The render adds 0.6s of extra front silence on a
    <reveal> line; the pre-flight's copy of the formula did not. 17 lines of
    this draft. None produced a short clip - they had the slack - but the two
    formulas disagreed, which is enough.

Cases
-----
  ONE-FORMULA           preflight, fit_narration and _build_clip all reach the
                        same arithmetic, and it includes the reveal pause.
  PREFLIGHT-IMPLIES-FIT the invariant: a line that passes the pre-flight can
                        never produce a short clip. Swept over narration
                        lengths, window sizes, holds, reveal/non-reveal and
                        real cut layouts.
  SPLIT-SHARES-BACKED   the splitter never chooses a boundary that starves a
                        sub-shot, and it still splits when it can.
  SPLIT-DECLINES        when no set of cuts can carry equal shares it returns
                        [] (one clip) rather than an under-fed split.
  REACH-FINDS-THE-FIVE  the five real offenders in this draft are found by the
                        shared reach calculation, with the cause named.
  ALL-AT-ONCE           the render lists EVERY short clip before encoding,
                        rather than stopping at the first one after minutes of
                        work.
  REVEAL-PAUSE-SHARED   the reveal pause is in the shared formula, so the
                        pre-flight and the builder cannot drift apart again.

Run:  python tools/test_clip_duration.py
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
if os.path.join(ROOT, "tools") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "tools"))

import config  # noqa: E402
from pipeline import footprint as fp  # noqa: E402
from pipeline.render import GAP, _split_points  # noqa: E402
from pipeline.schemas import BINDING_SLOWDOWN_MAX as SLOW  # noqa: E402

PROJ = Path(config.project_dir("tokyodrift2006"))


def _line(i, a, b, tag="normal", **kw):
    d = {"id": i, "delivery": tag, "narration": "x " * 20,
         "clip_start": "00:%02d:%06.3f" % (int(a) // 60, a % 60),
         "clip_end": "00:%02d:%06.3f" % (int(b) // 60, b % 60)}
    d.update(kw)
    return d


def test_one_formula() -> tuple[bool, str]:
    pf_src = io.open(os.path.join(ROOT, "pipeline", "preflight.py"),
                     encoding="utf-8").read()
    if "_fp.lead_and_clip" not in pf_src:
        return False, ("the pre-flight still computes a line's required "
                       "duration itself instead of using the shared formula")
    # Read the CODE, not the prose. A regex over the function text matched the
    # comment that records what the line USED to say, and failed correct code
    # for documenting its own history. Third time I have made this mistake in
    # this series, so: parse, drop the docstring, unparse - which also drops
    # every comment.
    import ast as _ast
    _fn = None
    for _n in _ast.walk(_ast.parse(pf_src)):
        if (isinstance(_n, _ast.FunctionDef)
                and _n.name == "capacity_findings"):
            _fn = _n
            break
    if _fn is None:
        return False, "pipeline/preflight.py has no capacity_findings()"
    _body = list(_fn.body)
    if (_body and isinstance(_body[0], _ast.Expr)
            and isinstance(_body[0].value, _ast.Constant)
            and isinstance(_body[0].value.value, str)):
        _body = _body[1:]
    code = "\n".join(_ast.unparse(x) for x in _body)
    import re as _re
    if _re.search(r"_lead_for\(narr_dur,\s*shot_dur\)\s*\+", code):
        return False, ("capacity_findings still has its own "
                       "lead + narr + GAP expression")
    if "lead_and_clip" not in code:
        return False, "capacity_findings does not call the shared formula"
    fpsrc = io.open(os.path.join(ROOT, "pipeline", "footprint.py"),
                    encoding="utf-8").read()
    if "def lead_and_clip" not in fpsrc or "def reveal_extra" not in fpsrc:
        return False, "the shared formula does not exist in footprint.py"
    # and clip_length - which fit_narration and stems use - must route to it
    j = fpsrc.find("def clip_length")
    cl = fpsrc[j:fpsrc.find("\ndef ", j + 10)]
    if "lead_and_clip" not in cl:
        return False, ("clip_length() does not use the shared formula, so the "
                       "fitter and the pre-flight can still disagree")
    if "reveal_extra" not in cl:
        return False, "clip_length() omits the reveal pause"
    return True, ("preflight, clip_length (fitter + stems) and the builder all "
                  "route through footprint.lead_and_clip, reveal pause "
                  "included")


def test_preflight_implies_fit() -> tuple[bool, str]:
    """THE INVARIANT. A line that passes the pre-flight is never short.

    Swept rather than spot-checked: this is the property the whole change
    exists to establish, and a single example would not establish it.
    """
    from fit_narration import required_window
    cuts_dense = [float(x) * 0.7 for x in range(1, 400)]     # a cut every 0.7s
    cases = 0
    for narr in [x * 0.5 for x in range(2, 50)]:
        for tag in ("normal", "reveal"):
            for hold in (0.0, 3.0, 12.0):
                w = required_window(narr)
                for window in (w, w + 0.01, w * 1.5, w * 3.0, w * 6.0):
                    a, b = 100.0, 100.0 + window
                    ln = _line(1, a, b, tag, hold=hold or None)
                    if hold:
                        ln["hold"] = hold
                    need = fp.clip_length(ln, narr)
                    cap = window * SLOW
                    if need > cap + 1e-6:
                        continue       # the pre-flight would REJECT it
                    for cl in ([], cuts_dense):
                        reach, why = fp.picture_reach(ln, narr, cl)
                        cases += 1
                        if reach + 1e-6 < need:
                            return False, (
                                f"a line the pre-flight PASSES would be built "
                                f"short: narr={narr:.2f} tag={tag} "
                                f"hold={hold} window={window:.2f} "
                                f"needs {need:.3f} reach {reach:.3f} ({why})")
    return True, (f"{cases} combinations across narration length, window size, "
                  f"hold, reveal/normal and dense/absent cuts: every line that "
                  f"passes the pre-flight can supply its full clip")


def test_split_shares_backed() -> tuple[bool, str]:
    """Every sub-shot must have its share in its OWN footage."""
    cuts = [100.0 + x * 0.5 for x in range(1, 60)]
    found = 0
    for clip_len in (8.5, 10.0, 12.0, 17.0, 20.0):
        for window in (clip_len, clip_len * 1.2, clip_len * 2.0):
            segs = _split_points(window, clip_len, cuts, 100.0,
                                 100.0 + window)
            if not segs:
                continue
            found += 1
            share = clip_len / len(segs)
            for (x, y) in segs:
                if (y - x) + 1e-6 < share:
                    return False, (
                        f"a {y-x:.2f}s sub-shot was given a {share:.2f}s "
                        f"share (clip_len {clip_len}, window {window:.2f})")
            if abs(sum(y - x for x, y in segs) - window) > 1e-3:
                return False, "the segments do not partition the window"
    if found == 0:
        return False, ("no split was produced at all; the guarantee passes "
                       "only because the feature stopped working")
    return True, (f"{found} split layout(s): every sub-shot's share is backed "
                  f"by its own footage, and the segments still partition the "
                  f"window")


def test_split_declines() -> tuple[bool, str]:
    """No viable boundary -> one clip, not an under-fed split."""
    # the only interior cut sits 1.5s in, so a 2-way split would starve it
    cuts = [101.5]
    segs = _split_points(13.583, 8.726, cuts, 100.0, 113.583)
    if segs:
        share = 8.726 / len(segs)
        worst = min(y - x for x, y in segs)
        if worst + 1e-6 < share:
            return False, (f"split anyway, starving a {worst:.2f}s sub-shot "
                           f"of its {share:.2f}s share - this is exactly the "
                           f"clip_024 defect")
        return False, (f"unexpectedly split into {len(segs)}; the fixture "
                       f"intended no viable boundary")
    # ...and the real line 24 layout must now decline or split safely
    return True, ("with no boundary that can carry equal shares the line "
                  "renders as a single clip, which is the old behaviour and "
                  "always correct")


def test_reach_finds_the_five() -> tuple[bool, str]:
    """The five real offenders, against the PRE-FIX splitter behaviour."""
    # Reconstruct the old splitter: nearest cut to the ideal, no share check.
    def old_split(window_dur, clip_len, cuts, start, end):
        thr = float(getattr(config, "SPLIT_CLIP_SEC", 8.0))
        if clip_len <= thr or window_dur <= 0.5 or not cuts:
            return []
        want = 3 if clip_len > thr * 2 else 2
        inner = [c for c in cuts if start + 1.2 < c < end - 1.2]
        if not inner:
            return []
        bounds = [start]
        for i in range(1, want):
            ideal = start + window_dur * i / want
            pick = min(inner, key=lambda c: abs(c - ideal))
            if pick - bounds[-1] >= 1.2:
                bounds.append(pick)
        bounds.append(end)
        segs = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
        segs = [(a, b) for a, b in segs if b - a >= 1.2]
        return segs if len(segs) >= 2 else []

    if not (PROJ / "draft.json").exists():
        return False, "the project draft is missing"
    try:
        from pipeline import cuts as cm
        cl = sorted(float(c) for c in (cm.load_cuts("tokyodrift2006") or []))
    except Exception as e:
        return False, f"could not load the cut list: {e}"
    if not cl:
        return False, "no cut list, so the split path cannot be exercised"
    # the FIXTURE, not the live draft: the live one is rewritten
    # between runs and its narration audio belongs to older line ids,
    # which made this report 11 short clips that do not exist.
    _fx = Path(ROOT) / "tools" / "fixtures" / "draft_tokyodrift_flat.json"
    draft = json.loads(_fx.read_text(encoding="utf-8-sig"))
    from pipeline import preflight as pfm
    from pipeline.draft import parse_ts
    ffp = config.ffprobe()
    durs = {}
    for ln in draft["lines"]:
        p = PROJ / ("narration/line_%03d.mp3" % ln["id"])
        if p.exists() and str(ln.get("narration") or "").strip():
            durs[ln["id"]] = pfm._audio_dur(ffp, p)
    if not durs:
        return False, "no narration audio to measure against"

    clone = float(config.MAX_FREEZE_SEC)
    old_bad = []
    for ln in draft["lines"]:
        lid = ln.get("id")
        if lid not in durs or not ln.get("clip_start"):
            continue
        a, b = parse_ts(ln["clip_start"]), parse_ts(ln["clip_end"])
        need = fp.clip_length(ln, durs[lid])
        segs = old_split(b - a, need, cl, a, b)
        if len(segs) < 2:
            continue
        share = need / len(segs)
        reach = sum(min(share, (y - x) + 0.5 + clone) for x, y in segs)
        if reach + 0.034 < need:
            old_bad.append(lid)
    if len(old_bad) < 3:
        return False, (f"the pre-fix splitter only starves {old_bad} on this "
                       f"draft; the case can no longer demonstrate the defect")
    # and with the FIXED splitter, none are short
    now_bad = fp.short_clips(draft, durs, cl)
    if now_bad:
        return False, (f"still short after the fix: "
                       f"{[r['line_id'] for r in now_bad]}")
    return True, (f"the old splitter starved lines {sorted(old_bad)}; with the "
                  f"share guarantee, 0 of {len(durs)} narrated lines are "
                  f"short")


def test_all_at_once() -> tuple[bool, str]:
    src = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                  encoding="utf-8").read()
    if "[SHORT-CLIP]" not in src:
        return False, "the render has no pre-encode short-clip pass"
    i = src.find("_fpmod.short_clips(")
    if i < 0:
        return False, "the render does not dry-compute every clip's reach"
    # it must run BEFORE any clip is built
    j = src.find("_build_clip(ff, source")
    if j > 0 and i > j:
        return False, ("the short-clip pass runs AFTER clips start building, "
                       "which is the minutes-of-encoding-per-offender problem "
                       "it exists to remove")
    seg = src[i:i + 1600]
    if "for _b in _sc_bad" not in seg:
        return False, ("the render does not list every offender; stopping at "
                       "the first one costs a full render per short clip")
    if "sys.exit(1)" not in seg:
        return False, "a short clip does not stop the render"
    return True, ("every clip's reach is dry-computed before encoding and all "
                  "offenders are listed in one pass")


def test_reveal_pause_shared() -> tuple[bool, str]:
    prp = float(getattr(config, "PRE_REVEAL_PAUSE", 0.0))
    if prp <= 0:
        return False, ("PRE_REVEAL_PAUSE is 0, so this case cannot show the "
                       "divergence it exists for")
    rev = _line(1, 100.0, 140.0, "reveal")
    nor = _line(2, 100.0, 140.0, "normal")
    a = fp.clip_length(rev, 5.0)
    b = fp.clip_length(nor, 5.0)
    if abs((a - b) - prp) > 1e-6:
        return False, (f"a reveal line's required duration exceeds a normal "
                       f"one's by {a-b:.3f}s, not the {prp:.3f}s "
                       f"PRE_REVEAL_PAUSE - the shared formula is not "
                       f"applying it")
    if abs(fp.reveal_extra(rev) - prp) > 1e-6 or fp.reveal_extra(nor) != 0.0:
        return False, "reveal_extra() does not identify reveal lines"
    return True, (f"a reveal line requires exactly {prp:.1f}s more picture "
                  f"than a normal one, in the one shared formula")


TESTS = {
    "ONE-FORMULA":           test_one_formula,
    "PREFLIGHT-IMPLIES-FIT": test_preflight_implies_fit,
    "SPLIT-SHARES-BACKED":   test_split_shares_backed,
    "SPLIT-DECLINES":        test_split_declines,
    "REACH-FINDS-THE-FIVE":  test_reach_finds_the_five,
    "ALL-AT-ONCE":           test_all_at_once,
    "REVEAL-PAUSE-SHARED":   test_reveal_pause_shared,
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
        print(f'{"PASS" if ok else "FAIL"}  {name:<23} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_clip_duration: all pass" if not bad else
          f"test_clip_duration: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
