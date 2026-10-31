"""[RUNTIME-BAND] - the arithmetic, the seam, and the wire to the exit code.

THE DEFECT
----------
The old band warned in BOTH directions on a share of 15-20% of film runtime -
a floor that was the shipped population's CEILING, so no render ever reached
the middle of it. Being a bare console.print with no severity it could not
stop anything either: a draft 30% over came back from a brief to CUT words and
shipped as a note nobody had to act on.

The replacement is an ABSOLUTE-MINUTES ceiling with a share guard for
out-of-domain films, and over the top it BLOCKS. Measured in
config/runtime_control.json across nine shipped renders: film length varies
1.67x while the finished recap holds 15.0-18.8 min, so absolute runtime is the
tighter statistic (spread 2.06x against the share's 2.18x) and a share band
wide enough to contain every shipped render rejects nothing.

The draft can only see words/WPM. The bar describes the FINISHED video, which
also carries holds, the intro, music tails and the gaps between lines, so the
estimate is multiplied by the measured RECAP_RUNTIME_RENDER_OVER_DRAFT (1.046,
the median of eight paired renders) before it is compared. Testing that factor
is the whole point of RUNTIME-CONVERSION-APPLIED below: a draft whose RAW
estimate is 18.5 min is under the 19.0 ceiling and must still fail.

THE SEAM
--------
`pipeline.draft._run_phase1_audits(project, pdir)` IS callable in isolation -
it needs only draft.json and transcript.json in the project directory, runs in
under a second, and returns the audit dict. So these tests drive the REAL
gate, not a re-implementation of its arithmetic; a test that recomputed
words/WPM x 1.046 itself would pass whatever the gate did. No render is run.

Cases:
  RUNTIME-OVER-ABSOLUTE     a prediction above the 19.0 min ceiling sets
                            runtime_over and sev="hard".
  RUNTIME-INSIDE-BAND       a prediction of 17.0 min does not.
  RUNTIME-CONVERSION-APPLIED a RAW estimate of 18.5 min - under the ceiling -
                            predicts 19.35 and MUST fail. This is the case
                            that proves the x1.046 is not decorative.
  RUNTIME-SHORT-FILM-SHARE  15.0 min on a 60-min film passes the absolute band
                            and must still be over, on the share guard alone.
  RUNTIME-UNDER-WARNS-ONLY  a prediction under the 14.0 min floor warns and
                            does NOT populate runtime_over.
  RUNTIME-WIRED-END-TO-END  by AST, not by text: the producer writes
                            `runtime_over` into the audit dict, validate_draft
                            carries it across into the draft dict, and recap.py
                            reads it in a causes.append branch. ALL THREE, in
                            the parsed tree - the middle one is the link that
                            was broken, and a test of either END would have
                            passed over it.
  RUNTIME-CONTROL-CONSISTENT the constants exist and config/runtime_control.json
                            agrees with them: the ceiling above the largest
                            shipped render, the floor below the smallest
                            non-outlier.

Run:  python tools/test_runtime_band.py
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from pipeline import draft as dr  # noqa: E402

CONTROL = Path(ROOT) / "config" / "runtime_control.json"
DRAFT_PY = Path(ROOT) / "pipeline" / "draft.py"
RECAP_PY = Path(ROOT) / "recap.py"

_SCRATCH: list = []


def _ts(t: float) -> str:
    return "%02d:%02d:%06.3f" % (int(t) // 3600, (int(t) % 3600) // 60, t % 60)


def _run_band(words: int, film_min: float) -> dict:
    """Drive the REAL audit over a scratch project of exactly `words` words.

    Returns the audit dict. Nothing is rendered and nothing outside the
    scratch project directory is touched.
    """
    name = f"_selftest_rtband_{words}_{int(film_min)}"
    pdir = Path(config.project_dir(name))
    shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir(parents=True)
    _SCRATCH.append(pdir)
    per = 20
    lines = []
    t = 10.0
    left = words
    i = 0
    while left > 0:
        n = min(per, left)
        left -= n
        i += 1
        lines.append({"id": i, "narration": " ".join(["word"] * n),
                      "clip_start": _ts(t), "clip_end": _ts(t + 5.0)})
        t += 10.0
    (pdir / "draft.json").write_text(json.dumps(
        {"project": name, "title": "runtime band selftest",
         "target_minutes": 17, "voice": "tts", "lines": lines},
        ensure_ascii=False), encoding="utf-8")
    (pdir / "transcript.json").write_text(json.dumps(
        {"language": "en", "duration": film_min * 60.0, "segments": []}),
        encoding="utf-8")
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            out = dr._run_phase1_audits(name, pdir)
    finally:
        shutil.rmtree(pdir, ignore_errors=True)
    if not isinstance(out, dict):
        raise RuntimeError(f"the audit returned {out!r}, not a metrics dict")
    return out


def _words_for(pred_min: float) -> int:
    """The word count whose PREDICTED finished runtime is `pred_min`."""
    wpm = float(config.TTS_WORDS_PER_MINUTE)
    k = float(config.RECAP_RUNTIME_RENDER_OVER_DRAFT)
    return int(round(pred_min / k * wpm))


def test_runtime_over_absolute() -> tuple[bool, str]:
    """Above the absolute ceiling, with the share guard well clear."""
    mx = float(config.RECAP_RUNTIME_MAX_MINUTES)
    w = _words_for(mx + 1.0)
    a = _run_band(w, 150.0)
    if not a.get("runtime_over"):
        return False, (f"{w} words -> a predicted {mx + 1.0:.1f} min did not "
                       f"populate runtime_over (ceiling {mx})")
    if a.get("sev") != "hard":
        return False, (f"runtime_over is set but sev is {a.get('sev')!r}, so "
                       f"nothing blocks - that is the old defect exactly")
    msg = a["runtime_over"]
    if "ceiling" not in msg:
        return False, f"the cause does not name the ceiling: {msg}"
    if "share guard" in msg:
        return False, (f"the SHARE guard also fired on a 150-min film "
                       f"({mx + 1.0:.1f} min is "
                       f"{100 * (mx + 1.0) / 150:.1f}% of it), so this case "
                       f"does not isolate the absolute bar: {msg}")
    return True, (f"{w} words on a 150-min film -> {msg[:110]}... ; "
                  f"sev=hard")


def test_runtime_inside_band() -> tuple[bool, str]:
    """17.0 min predicted is inside the band and must not be over."""
    w = _words_for(17.0)
    a = _run_band(w, 150.0)
    if a.get("runtime_over"):
        return False, (f"{w} words -> a predicted 17.0 min was reported over "
                       f"the {config.RECAP_RUNTIME_MAX_MINUTES} min band: "
                       f"{a['runtime_over']}")
    pct = 100 * 17.0 / 150.0
    if pct < config.RECAP_RUNTIME_PCT_LO:
        return False, (f"this case accidentally sits under the "
                       f"{config.RECAP_RUNTIME_PCT_LO}% share floor "
                       f"({pct:.1f}%), so a clean result proves nothing")
    return True, (f"{w} words -> 17.0 min predicted ({pct:.1f}% of a 150-min "
                  f"film) is clean inside {config.RECAP_RUNTIME_MIN_MINUTES}-"
                  f"{config.RECAP_RUNTIME_MAX_MINUTES} min")


def test_runtime_conversion_applied() -> tuple[bool, str]:
    """THE CASE THAT PROVES x1.046 IS NOT DECORATIVE.

    A draft whose RAW words/WPM estimate is 18.5 min is UNDER the 19.0 min
    ceiling. Converted by the measured factor it predicts 19.35 and must fail.
    If the conversion were dropped, or applied to the bar instead of the
    estimate, this draft would pass.
    """
    k = float(config.RECAP_RUNTIME_RENDER_OVER_DRAFT)
    mx = float(config.RECAP_RUNTIME_MAX_MINUTES)
    raw = 18.5
    pred = raw * k
    if not (raw < mx < pred):
        return False, (f"the constants no longer make this case decisive: raw "
                       f"{raw} min, ceiling {mx}, predicted {pred:.2f}. Pick "
                       f"a raw estimate that straddles the ceiling after the "
                       f"x{k} conversion.")
    w = int(round(raw * float(config.TTS_WORDS_PER_MINUTE)))
    a = _run_band(w, 150.0)
    if not a.get("runtime_over"):
        return False, (f"{w} words = {raw} min RAW, {pred:.2f} min predicted, "
                       f"ceiling {mx} - and the gate passed it. The x{k} "
                       f"conversion is not being applied to the estimate.")
    msg = a["runtime_over"]
    if f"{raw:.1f} min of narration" not in msg:
        return False, f"the cause does not report the raw estimate: {msg}"
    if f"{pred:.1f} min finished" not in msg:
        return False, (f"the cause does not report the CONVERTED prediction "
                       f"{pred:.1f}: {msg}")
    if f"x{k:.3f}" not in msg:
        return False, f"the cause does not state the factor it used: {msg}"
    # and the control file must be where that factor came from
    ctl = json.loads(CONTROL.read_text(encoding="utf-8"))
    med = (ctl.get("render_over_draft") or {}).get("median")
    if med is None or abs(float(med) - k) > 1e-9:
        return False, (f"config.RECAP_RUNTIME_RENDER_OVER_DRAFT is {k} but "
                       f"config/runtime_control.json measured {med} - the "
                       f"factor is not the measured one")
    return True, (f"{w} words = {raw} min RAW (UNDER the {mx} min ceiling) "
                  f"predicts {pred:.2f} min finished and FAILS; the message "
                  f"states x{k:.3f}, which is the measured median in "
                  f"runtime_control.json")


def test_runtime_short_film_share() -> tuple[bool, str]:
    """The out-of-domain guard: absolute minutes pass, the share does not."""
    mn = float(config.RECAP_RUNTIME_MIN_MINUTES)
    mx = float(config.RECAP_RUNTIME_MAX_MINUTES)
    phi = float(config.RECAP_RUNTIME_PCT_HI)
    pred, film = 15.0, 60.0
    if not (mn < pred < mx):
        return False, (f"{pred} min is no longer inside the absolute band "
                       f"{mn}-{mx}, so this case cannot isolate the share")
    pct = 100.0 * pred / film
    if pct <= phi:
        return False, (f"{pred} min of a {film:.0f}-min film is {pct:.1f}%, "
                       f"not over the {phi}% guard - pick a shorter film")
    w = _words_for(pred)
    a = _run_band(w, film)
    if not a.get("runtime_over"):
        return False, (f"{pred:.1f} min on a {film:.0f}-min film is "
                       f"{pct:.0f}% of it, over the {phi}% guard, and was not "
                       f"reported. A film shorter than anything calibrated is "
                       f"exactly what that guard is for.")
    msg = a["runtime_over"]
    if "share guard" not in msg:
        return False, f"the cause does not name the share guard: {msg}"
    if "ceiling" in msg:
        return False, (f"the ABSOLUTE ceiling also fired at {pred:.1f} min, "
                       f"which is inside {mn}-{mx}: {msg}")
    if a.get("sev") != "hard":
        return False, f"the share guard did not set sev=hard: {a.get('sev')!r}"
    # the same word count on a long film must be clean - so it is the SHARE
    # doing the work and not the words
    b = _run_band(w, 150.0)
    if b.get("runtime_over"):
        return False, (f"the same {w} words on a 150-min film "
                       f"({100 * pred / 150:.0f}%) also failed, so the share "
                       f"is not what caught it: {b['runtime_over']}")
    return True, (f"{w} words -> {pred:.1f} min finished is inside the "
                  f"{mn}-{mx} min band but {pct:.0f}% of a {film:.0f}-min "
                  f"film, over the {phi}% guard: hard, named as the share "
                  f"guard; the same words on a 150-min film are clean")


def test_runtime_under_warns_only() -> tuple[bool, str]:
    """Under the floor WARNS. It must not populate runtime_over."""
    mn = float(config.RECAP_RUNTIME_MIN_MINUTES)
    pred, film = mn - 1.0, 130.0
    pct = 100.0 * pred / film
    if pct < config.RECAP_RUNTIME_PCT_LO:
        return False, (f"{pred:.1f} min of a {film:.0f}-min film is "
                       f"{pct:.1f}%, under the share floor too - this case "
                       f"cannot isolate the absolute floor")
    w = _words_for(pred)
    a = _run_band(w, film)
    if a.get("runtime_over"):
        return False, (f"a draft UNDER the {mn} min floor populated "
                       f"runtime_over and would block: {a['runtime_over']}. "
                       f"Under is a warning - a film can honestly have less "
                       f"to say.")
    return True, (f"{w} words -> {pred:.1f} min predicted ({pct:.0f}% of a "
                  f"{film:.0f}-min film) is under the {mn} min floor: "
                  f"runtime_over is None, so it warns and does not block")


# --------------------------------------------------------------------------- #
# WIRING - by AST.
#
# Not by regex over the source text. A text search matches the explanatory
# comments that surround every one of these branches, and this repo has had
# four tests pass that way while the code underneath did nothing. `ast.parse`
# discards comments entirely, so a Constant node carrying "runtime_over" can
# only have come from code. Fixed-byte-window slicing is out for the same
# reason: the window is chosen by the test, not by the structure.
# --------------------------------------------------------------------------- #

def _fn(tree: ast.AST, name: str):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _str_consts(node: ast.AST) -> set:
    """Every string literal in `node` EXCEPT bare-expression docstrings."""
    doc = {id(n.value) for n in ast.walk(node)
           if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
           and isinstance(n.value.value, str)}
    return {n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in doc}


def test_runtime_wired_end_to_end() -> tuple[bool, str]:
    """Producer -> bridge -> consumer, all three asserted in the parsed tree.

    THIS TEST FOUND A BUG. `_run_phase1_audits` returned `runtime_over` and
    recap.py read `runtime_over` - both ends existed and matched. But
    validate_draft copies only a WHITELIST of audit keys onto the dict it
    returns, and `runtime_over` was not on it, so `r.get("runtime_over")` was
    always None: a draft over the band exited 1 with the useless fallback
    cause "a hard audit finding that is NOT a binding mismatch", and `render`
    never blocked on it despite recap.py being written to. Fixed in draft.py.

    A test of either END would have passed. That is why the BRIDGE is asserted
    by name here.
    """
    dtree = ast.parse(DRAFT_PY.read_text(encoding="utf-8"))
    rtree = ast.parse(RECAP_PY.read_text(encoding="utf-8"))

    # ---- 1. the producer ------------------------------------------------- #
    prod = _fn(dtree, "_run_phase1_audits")
    if prod is None:
        return False, "pipeline/draft.py has no _run_phase1_audits"
    key_node = None
    for n in ast.walk(prod):
        if not (isinstance(n, ast.Return) and isinstance(n.value, ast.Dict)):
            continue
        for k, v in zip(n.value.keys, n.value.values):
            if isinstance(k, ast.Constant) and k.value == "runtime_over":
                key_node = v
    if key_node is None:
        return False, ("_run_phase1_audits does not return a dict carrying "
                       "'runtime_over'. A hard gate that does not report its "
                       "own cause makes recap.py print the fallback line.")
    if not isinstance(key_node, ast.Name):
        return False, (f"'runtime_over' is mapped to a "
                       f"{type(key_node).__name__}, not to a variable - a "
                       f"literal there would be the same as no gate")
    var = key_node.id
    assigned = [n for n in ast.walk(prod) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == var
                        for t in n.targets)]
    if len(assigned) < 2:
        return False, (f"{var} is assigned {len(assigned)} time(s) in "
                       f"_run_phase1_audits; it must be initialised AND set "
                       f"by the over-band branch, or it can never be truthy")

    # ---- 2. the bridge --------------------------------------------------- #
    vd = _fn(dtree, "validate_draft")
    if vd is None:
        return False, "pipeline/draft.py has no validate_draft"
    carried = None
    for n in ast.walk(vd):
        if not isinstance(n, ast.For):
            continue
        if not isinstance(n.iter, (ast.Tuple, ast.List)):
            continue
        if not all(isinstance(e, ast.Constant) and isinstance(e.value, str)
                   for e in n.iter.elts):
            continue
        writes_draft = any(
            isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
            and t.value.id == "draft"
            for a in ast.walk(n) if isinstance(a, ast.Assign)
            for t in a.targets)
        if writes_draft:
            carried = {e.value for e in n.iter.elts}
    if carried is None:
        return False, ("validate_draft no longer copies audit keys onto the "
                       "draft dict through a literal whitelist, so this test "
                       "cannot see the bridge. Re-point it at whatever "
                       "replaced that loop - do NOT delete the assertion: it "
                       "is the link that was broken.")
    if "runtime_over" not in carried:
        return False, (f"validate_draft carries {sorted(carried)} from the "
                       f"audit onto the draft dict, and 'runtime_over' is NOT "
                       f"among them. Both ends of the wire exist and match; "
                       f"the wire does not. recap.py's r.get('runtime_over') "
                       f"is always None.")

    # ---- 3. the consumer ------------------------------------------------- #
    def _branch(appends_to: str):
        for n in ast.walk(rtree):
            if not isinstance(n, ast.If):
                continue
            if "runtime_over" not in _str_consts(n.test):
                continue
            for c in ast.walk(n):
                if (isinstance(c, ast.Call)
                        and isinstance(c.func, ast.Attribute)
                        and c.func.attr == "append"
                        and isinstance(c.func.value, ast.Name)
                        and c.func.value.id == appends_to):
                    return n
        return None

    if _branch("causes") is None:
        return False, ("recap.py has no `if ...runtime_over...: "
                       "causes.append(...)` branch, so a hard runtime failure "
                       "would be reported as 'a hard audit finding that is "
                       "NOT a binding mismatch'")
    if _branch("_fatal") is None:
        return False, ("recap.py's render path has no runtime_over branch - "
                       "a draft the draft stage blocks would still render")
    return True, (f"producer: _run_phase1_audits returns 'runtime_over' bound "
                  f"to {var} ({len(assigned)} assignments); bridge: "
                  f"validate_draft carries {len(carried)} audit keys onto the "
                  f"draft dict INCLUDING 'runtime_over' (this was the broken "
                  f"link); consumer: recap.py reads it in a causes.append and "
                  f"a _fatal.append branch - all asserted on the parsed tree, "
                  f"no source-text matching")


def test_runtime_control_consistent() -> tuple[bool, str]:
    """The constants exist, and the control file agrees with them.

    The ceiling must be ABOVE the largest shipped render or it rejects work
    that has already shipped; the floor must be BELOW the smallest non-outlier
    or it rejects the honest short recap. Outliers by the 1.5 x IQR rule, so
    "non-outlier" is a definition and not a preference.
    """
    need = ("RECAP_RUNTIME_MAX_MINUTES", "RECAP_RUNTIME_MIN_MINUTES",
            "RECAP_RUNTIME_PCT_HI", "RECAP_RUNTIME_PCT_LO",
            "RECAP_RUNTIME_RENDER_OVER_DRAFT", "TTS_WORDS_PER_MINUTE")
    missing = [k for k in need if not hasattr(config, k)]
    if missing:
        return False, f"config is missing {missing}"
    if not CONTROL.exists():
        return False, ("config/runtime_control.json is missing - the bars "
                       "have no recorded derivation")
    ctl = json.loads(CONTROL.read_text(encoding="utf-8"))
    vals = sorted(float(v) for v in
                  (ctl.get("absolute_minutes") or {}).get("values") or [])
    if len(vals) < 5:
        return False, f"the control records only {len(vals)} shipped render(s)"

    def q(p):
        half = vals[:len(vals) // 2] if p == 1 else vals[(len(vals) + 1) // 2:]
        n = len(half)
        return (half[n // 2] if n % 2 else (half[n // 2 - 1] + half[n // 2]) / 2)

    q1, q3 = q(1), q(3)
    iqr = q3 - q1
    lo_fence, hi_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inliers = [v for v in vals if lo_fence <= v <= hi_fence]
    outliers = [v for v in vals if v not in inliers]
    if not inliers:
        return False, "every shipped render is an outlier by the IQR rule"

    mx = float(config.RECAP_RUNTIME_MAX_MINUTES)
    mn = float(config.RECAP_RUNTIME_MIN_MINUTES)
    if mx <= max(vals):
        return False, (f"the ceiling {mx} min is at or below the largest "
                       f"shipped render {max(vals)} min - it rejects work "
                       f"this repo has already published")
    if mn >= min(inliers):
        return False, (f"the floor {mn} min is at or above the smallest "
                       f"non-outlier shipped render {min(inliers)} min "
                       f"(inliers {inliers}, outliers {outliers} by 1.5xIQR "
                       f"fences {lo_fence:.2f}/{hi_fence:.2f})")
    # the wpm the control was measured at must be the wpm the gate uses
    basis = ctl.get("wpm_basis")
    if basis is not None and abs(float(basis)
                                 - float(config.TTS_WORDS_PER_MINUTE)) > 1e-9:
        return False, (f"runtime_control.json was measured at {basis} WPM but "
                       f"config.TTS_WORDS_PER_MINUTE is "
                       f"{config.TTS_WORDS_PER_MINUTE}; every draft_est_min "
                       f"in that file, and therefore the x"
                       f"{config.RECAP_RUNTIME_RENDER_OVER_DRAFT} factor, is "
                       f"on a different basis from the gate")
    # the share guard must likewise contain the shipped population
    shares = sorted(float(v) * 100.0 for v in
                    (ctl.get("render_share") or {}).get("values") or [])
    if shares and float(config.RECAP_RUNTIME_PCT_HI) <= max(shares):
        return False, (f"the {config.RECAP_RUNTIME_PCT_HI}% share guard is at "
                       f"or below the largest shipped share {max(shares):.1f}%")
    return True, (f"{len(vals)} shipped renders {min(vals)}-{max(vals)} min; "
                  f"ceiling {mx} > max {max(vals)}; floor {mn} < smallest "
                  f"non-outlier {min(inliers)} (outlier(s) {outliers} by "
                  f"1.5xIQR); share guard {config.RECAP_RUNTIME_PCT_HI}% > "
                  f"max shipped share {max(shares):.1f}%; both measured at "
                  f"{basis} WPM, which is config.TTS_WORDS_PER_MINUTE")


TESTS = {
    "RUNTIME-OVER-ABSOLUTE":      test_runtime_over_absolute,
    "RUNTIME-INSIDE-BAND":        test_runtime_inside_band,
    "RUNTIME-CONVERSION-APPLIED": test_runtime_conversion_applied,
    "RUNTIME-SHORT-FILM-SHARE":   test_runtime_short_film_share,
    "RUNTIME-UNDER-WARNS-ONLY":   test_runtime_under_warns_only,
    "RUNTIME-WIRED-END-TO-END":   test_runtime_wired_end_to_end,
    "RUNTIME-CONTROL-CONSISTENT": test_runtime_control_consistent,
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
            print(f'{"PASS" if ok else "FAIL"}  {name:<28} {msg}')
            bad += (not ok)
    finally:
        for d in _SCRATCH:
            shutil.rmtree(d, ignore_errors=True)
    print("-" * 60)
    print("test_runtime_band: all pass" if not bad else
          f"test_runtime_band: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
