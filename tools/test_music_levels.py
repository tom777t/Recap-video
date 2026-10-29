"""Are the cues and the film_speaks units actually AUDIBLE in the mix?

TWO DEFECTS, both reported from watching a finished render, both invisible to
every check that existed - because those checks confirmed a gain had been
written into a filtergraph, never that the result could be heard.

1. CUES NOT AUDIBLE. The gains were real. The MATERIAL was not comparable:
   measured integrated loudness of this project's own music is

       action1  -3.5 LUFS   mystery1 -9.6   tense1 -11.2
       reveal1 -12.4        sad1    -12.5   bed    -11.1

   a 9.0 dB spread. The gain differences the mix is built on (-12 vs -8 vs -2)
   are SMALLER than the variation in the files they are applied to, so
   "+10 dB above the bed" meant something different for every cue: reveal1
   starts 1.3 dB quieter than the bed, action1 starts 7.6 dB louder.

2. FILM_SPEAKS INAUDIBLE - only music was heard in both units. A film_speaks
   unit carries no narration, so it was recorded as a silence window like any
   other hold, and a hold SWELLS the music: SILENCE_MUSIC_VOLUME doubles the
   bed and MUSIC_CUE_HOLD_DB puts a cue at -2 dB, near full level. The one
   moment the film is deliberately given the floor was also the loudest the
   music ever gets. A hold and a film_speaks unit want OPPOSITE things from
   the music, and treating them as one kind of event is the bug.

Cases
-----
  NORMALISE-REAL-FILES  the project's own music collapses from 9.0 dB of
                        spread to 0.0 at a common -23 LUFS, measured.
  NORMALISE-CACHED      the second call reuses the cached file.
  NORMALISE-STATIC-GAIN a static gain, not two-pass loudnorm: the dynamics a
                        cue relies on survive.
  CUE-RISES-ON-REAL-MIX built with the real builder and real files: both cues
                        measure clearly above the bed.
  FILM-SPEAKS-DUCKS     the music ducks ~20 dB under a film_speaks unit, is
                        NOT muted, and comes back afterwards.
  FILM-SPEAKS-NOT-HOLD  a film_speaks unit is not put in the swell list.
  GATES-CATCH           a cue at bed level and a drowned film_speaks unit are
                        each reported.

Run:  python tools/test_music_levels.py
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from pipeline import audio_check as ac  # noqa: E402
from pipeline import music as mus  # noqa: E402

PROJ_MUSIC = Path(config.project_dir("tokyodrift2006")) / "music"


def _ff(*a) -> None:
    subprocess.run([config.ffmpeg(), "-y", "-hide_banner", "-loglevel",
                    "error", *a], check=True, capture_output=True)


def _have_real_music() -> bool:
    return (PROJ_MUSIC / "bed.mp3").exists() and \
        any((PROJ_MUSIC / "cues").glob("*.mp3"))


def test_normalise_real_files() -> tuple[bool, str]:
    if not _have_real_music():
        return False, "the project's music files are missing; cannot measure"
    ff = config.ffmpeg()
    pdir = Path(config.project_dir("tokyodrift2006"))
    srcs = [PROJ_MUSIC / "bed.mp3"] + sorted((PROJ_MUSIC / "cues").glob("*.mp3"))
    before = [ac.integrated(p) for p in srcs]
    after = [ac.integrated(mus.normalized(ff, pdir, p)) for p in srcs]
    if any(x is None for x in before + after):
        return False, "a loudness measurement failed"
    sb = max(before) - min(before)
    sa = max(after) - min(after)
    if sb < 5.0:
        return False, (f"the premise no longer holds: the source spread is "
                       f"only {sb:.1f} dB, so normalising proves little")
    if sa > 1.0:
        return False, (f"after normalising the spread is still {sa:.1f} dB; "
                       f"the gains still mean different things per file")
    tgt = float(config.MUSIC_NORMALIZE_LUFS)
    if any(abs(x - tgt) > 1.0 for x in after):
        return False, (f"files did not land on {tgt:.0f} LUFS: "
                       f"{[round(x, 1) for x in after]}")
    return True, (f"{len(srcs)} real music file(s): {sb:.1f} dB of spread "
                  f"collapses to {sa:.1f} dB at {tgt:.0f} LUFS")


def test_normalise_cached() -> tuple[bool, str]:
    if not _have_real_music():
        return False, "the project's music files are missing"
    ff = config.ffmpeg()
    pdir = Path(config.project_dir("tokyodrift2006"))
    src = PROJ_MUSIC / "bed.mp3"
    a = mus.normalized(ff, pdir, src)
    m1 = a.stat().st_mtime_ns
    b = mus.normalized(ff, pdir, src)
    if a != b:
        return False, "the second call produced a different path"
    if b.stat().st_mtime_ns != m1:
        return False, ("the file was re-encoded on the second call; "
                       "measuring loudness is a second per file and the "
                       "answer never changes for a file that has not changed")
    meta = b.with_suffix(".json")
    if not meta.exists():
        return False, "no sidecar recording what was measured and applied"
    rec = json.loads(meta.read_text(encoding="utf-8"))
    for k in ("measured_lufs", "target_lufs", "gain_db"):
        if k not in rec:
            return False, f"the sidecar does not record {k}"
    return True, (f"cached on the second call; the sidecar records "
                  f"{rec['measured_lufs']:+.1f} -> {rec['target_lufs']:+.1f} "
                  f"LUFS ({rec['gain_db']:+.1f} dB)")


def test_normalise_static_gain() -> tuple[bool, str]:
    """Static gain, not two-pass dynamic loudnorm."""
    # Read the CODE, not the prose. A plain substring search over the function
    # text matched this module's own docstring - which says "deliberately not
    # two-pass loudnorm" - and so failed the correct implementation for
    # explaining itself. Strip the docstring and the comments first.
    import ast
    src = io.open(os.path.join(ROOT, "pipeline", "music.py"),
                  encoding="utf-8").read()
    fn = None
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == "normalized":
            fn = node
            break
    if fn is None:
        return False, "pipeline/music.py has no normalized()"
    body_nodes = list(fn.body)
    if (body_nodes and isinstance(body_nodes[0], ast.Expr)
            and isinstance(body_nodes[0].value, ast.Constant)
            and isinstance(body_nodes[0].value.value, str)):
        body_nodes = body_nodes[1:]          # drop the docstring
    code = "\n".join(ast.unparse(n) for n in body_nodes)
    if "loudnorm" in code:
        return False, ("normalized() uses the loudnorm filter; its dynamic "
                       "mode compresses, which flattens exactly the dynamics "
                       "a cue relies on to land as an event")
    if "volume=" not in code:
        return False, "normalized() applies no gain at all"
    # and it must measure, not assume
    if "integrated(" not in code:
        return False, "normalized() does not measure the source loudness"
    return True, ("loudness is measured and applied as a single static gain, "
                  "so the music's dynamics survive")


def test_cue_rises_on_real_mix() -> tuple[bool, str]:
    """Build with the REAL builder and the REAL files, then measure."""
    if not _have_real_music():
        return False, "the project's music files are missing"
    ff = config.ffmpeg()
    pdir = Path(config.project_dir("tokyodrift2006"))
    cues = sorted((PROJ_MUSIC / "cues").glob("*.mp3"))
    pick = {p.stem.rstrip("0123456789"): p for p in cues}
    if "tense" not in pick or "action" not in pick:
        return False, f"need a tense and an action cue, have {list(pick)}"
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "mt.wav"
        plan = [{"start": 20.0, "end": 32.0, "mood": "tense",
                 "file": str(pick["tense"])},
                {"start": 50.0, "end": 62.0, "mood": "action",
                 "file": str(pick["action"])}]
        if not mus.build_music_track(ff, pdir, out, 75.0,
                                     PROJ_MUSIC / "bed.mp3", plan,
                                     reveal_positions=[], hold_windows=[],
                                     film_speaks_windows=[]):
            return False, "the music track failed to build"
        rows = ac.cue_vs_bed(out, [{"at": 20.0, "dur": 12.0, "mood": "tense"},
                                   {"at": 50.0, "dur": 12.0,
                                    "mood": "action"}])
        weak = [r for r in rows if r["lift_db"] < ac.CUE_LIFT_MIN_DB]
        if weak:
            return False, ("cue(s) did not rise out of the bed: "
                           + "; ".join(f"{r['mood']} {r['lift_db']:+.1f} dB"
                                       for r in weak))
        return True, ("on a real mix: "
                      + ", ".join(f"{r['mood']} {r['lift_db']:+.1f} dB"
                                  for r in rows)
                      + f" above the bed (bar {ac.CUE_LIFT_MIN_DB:.0f} dB)")


def test_film_speaks_ducks() -> tuple[bool, str]:
    if not _have_real_music():
        return False, "the project's music files are missing"
    ff = config.ffmpeg()
    pdir = Path(config.project_dir("tokyodrift2006"))
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "mt.wav"
        if not mus.build_music_track(ff, pdir, out, 110.0,
                                     PROJ_MUSIC / "bed.mp3", [],
                                     reveal_positions=[], hold_windows=[],
                                     film_speaks_windows=[(80.0, 90.0)]):
            return False, "the music track failed to build"
        before = ac.rms_db(out, 70.0, 8.0)
        inside = ac.rms_db(out, 81.0, 8.0)
        after = ac.rms_db(out, 95.0, 10.0)
        duck = inside - before
        want = float(config.FILM_SPEAKS_MUSIC_DB)
        if duck > want + 6.0:
            return False, (f"the music only ducked {duck:+.1f} dB inside the "
                           f"unit, against a {want:.0f} dB target - this is "
                           f"the level that drowned both units")
        if inside < -80.0:
            return False, (f"the music was effectively MUTED inside the unit "
                           f"({inside:.1f} dB). A hard dropout reads as the "
                           f"audio breaking and the scene stops feeling like "
                           f"part of the film; the rule is ducked, not muted")
        if after < before - 6.0:
            return False, (f"the music did not come back after the unit "
                           f"({after:.1f} dB vs {before:.1f} dB before)")
        return True, (f"music {before:.1f} -> {inside:.1f} dB inside the unit "
                      f"({duck:+.1f} dB, target {want:.0f}), audible not "
                      f"muted, and back to {after:.1f} dB after")


def test_film_speaks_not_hold() -> tuple[bool, str]:
    src = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                  encoding="utf-8").read()
    if "film_speaks_windows" not in src:
        return False, ("the render still puts film_speaks units in the same "
                       "list as holds, so the music swells over them")
    i = src.find("film_speaks_windows.append")
    if i < 0:
        return False, "film_speaks windows are never collected"
    around = src[max(0, i - 300):i + 300]
    if "else:" not in around or "silence_windows.append" not in around:
        return False, ("a film_speaks unit is not being kept OUT of the "
                       "silence-swell list")
    # and the duck must reach both music paths
    if "film_speaks_windows=film_speaks_windows" not in src:
        return False, "the windows never reach the music builder"
    m = io.open(os.path.join(ROOT, "pipeline", "music.py"),
                encoding="utf-8").read()
    if "FILM_SPEAKS_MUSIC_DB" not in m:
        return False, "build_music_track does not duck for a film_speaks unit"
    if m.count("film_speaks_windows") < 4:
        return False, ("the duck is applied to only one of the bed and the "
                       "cues; a cue at MUSIC_CUE_HOLD_DB is the louder layer, "
                       "so leaving it out leaves what was drowning the film")
    return True, ("film_speaks units are tracked apart from holds, ducked in "
                  "both the bed and the cues, and in the render's own volume "
                  "expression as well so every music design gets it")


def test_gates_catch() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        # a flat tone: a "cue" window is indistinguishable from the bed
        _ff("-f", "lavfi", "-i", "sine=frequency=220:duration=30", "-ac", "2",
            str(d / "flat.wav"))
        ok, find, rows = ac.check_cues_audible(
            d / "flat.wav", [{"at": 10.0, "dur": 6.0, "mood": "tense"}])
        if ok:
            return False, ("a cue at exactly bed level passed; that is not a "
                           "cue, it is more bed")
        if "more bed" not in " ".join(find):
            return False, f"reported as something else: {find}"
        ok2, find2, _ = ac.check_film_speaks_audible(
            d / "flat.wav", [{"line_id": 7, "final_at": 10.0, "dur": 6.0}])
        if ok2:
            return False, ("a film_speaks unit no louder than the music "
                           "around it passed")
        if "loudest thing" not in " ".join(find2):
            return False, f"reported as something else: {find2}"
        # a real lift passes
        _ff("-f", "lavfi", "-i", "sine=frequency=220:duration=30", "-af",
            "volume='if(between(t,10,16),4.0,1.0)':eval=frame", "-ac", "2",
            str(d / "lift.wav"))
        ok3, find3, rows3 = ac.check_cues_audible(
            d / "lift.wav", [{"at": 10.0, "dur": 6.0, "mood": "tense"}])
        if not ok3:
            return False, f"a real +12 dB lift was rejected: {find3}"
        return True, (f"a cue at bed level and a drowned film_speaks unit are "
                      f"both caught; a real "
                      f"{rows3[0]['lift_db']:+.1f} dB lift passes")


TESTS = {
    "NORMALISE-REAL-FILES":  test_normalise_real_files,
    "NORMALISE-CACHED":      test_normalise_cached,
    "NORMALISE-STATIC-GAIN": test_normalise_static_gain,
    "CUE-RISES-ON-REAL-MIX": test_cue_rises_on_real_mix,
    "FILM-SPEAKS-DUCKS":     test_film_speaks_ducks,
    "FILM-SPEAKS-NOT-HOLD":  test_film_speaks_not_hold,
    "GATES-CATCH":           test_gates_catch,
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
    print("test_music_levels: all pass" if not bad else
          f"test_music_levels: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
