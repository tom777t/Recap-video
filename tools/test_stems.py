"""Film-audio stem separation regression tests.

THE DEFECT
----------
Film audio was mixed under the narration at -17 dB and -6 dB inside holds. At
those levels the film's DIALOGUE is audible almost continuously, so the
narrator and the characters talk over each other. Muting the film would fix
that and throw away the best thing in the mix - engines, tyres, impacts.

So the audio is separated once per project into vocals / no-vocals, and the
no-vocals stem is used everywhere the narrator speaks and inside every hold.
The original mix is read ONLY inside a <film_speaks> unit.

Cases
-----
  AVAILABILITY        reports honestly whether separation can run, and the
                      install hint names both packages
  NEEDED-SPANS        only the footage the draft binds is separated, a hold's
                      REAL span is covered, spans are padded and merged
  SPAN-COVERAGE       a draft whose windows moved onto un-separated audio is
                      detected, not silently served silence
  CACHE-KEYED-TO-SOURCE  a different source invalidates the cache, so stems
                      from a previous film are never reused
  CLIP-SIGNATURE      switching stems on/off changes the clip cache key. Without
                      this, enabling stems would serve the whole film from
                      cache with the dialogue still in it.
  HOLD-USES-STEM      a hold reads the stem; a film_speaks unit reads the
                      ORIGINAL mix. That asymmetry is the whole design.
  REQUIRE-STOPS       a missing separation is a STOP, not a silent fallback to
                      the un-separated mix
  SEPARATE-REAL       an END-TO-END separation of a few seconds of real audio:
                      extract, separate, assemble, and the output is a valid
                      full-length wav. Slow but it is the only test that proves
                      the path rather than the plumbing. Skipped (reported, not
                      silently passed) when demucs is unavailable.

Run:  python tools/test_stems.py
      python tools/test_stems.py SEPARATE-REAL      # the slow one alone
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from pipeline import stems as st  # noqa: E402

PROJ = "_stemtest"


def _ff(*args) -> None:
    r = subprocess.run([config.ffmpeg(), "-y", "-hide_banner",
                        "-loglevel", "error", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg: {(r.stderr or '')[-300:]}")


def _dur(p: Path) -> float:
    r = subprocess.run(
        [config.ffprobe(), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


def _teardown():
    shutil.rmtree(Path(config.project_dir(PROJ)), ignore_errors=True)


def test_availability() -> tuple[bool, str]:
    ok, why = st.available()
    hint = st.install_hint()
    if "torch" not in hint or "demucs" not in hint:
        return False, f"the install hint names neither package: {hint!r}"
    return True, (f"separation {'available' if ok else 'unavailable'}: {why}; "
                  f"the hint names torch and demucs")


def test_needed_spans() -> tuple[bool, str]:
    pad = st.SPAN_PAD_SEC
    # EVERY window here is action/tense in a run, because separation now
    # covers only the windows where the film's track is actually heard. This
    # fixture used to carry no delivery tags at all and asserted that every
    # bound window gets separated - the old contract, under which the stem
    # played beneath all 111 lines and its artefacts were a constant bed.
    draft = {"lines": [
        # ordinary bound window
        {"id": 1, "clip_start": "00:00:10.000", "clip_end": "00:00:14.000",
         "delivery": "action", "narration": "x"},
        # a HOLD whose authored duration runs PAST its declared window.
        # _build_silence_clip ignores `end`, so the real span is start+hold.
        {"id": 2, "clip_start": "00:00:30.000", "clip_end": "00:00:31.000",
         "delivery": "action", "narration": "",
         "narration_silence_seconds": 9.0},
        # inline montage segments
        {"id": 3, "narration": "x", "delivery": "tense", "montage": [
            {"clip_start": "00:01:00.000", "clip_end": "00:01:02.000"},
            {"clip_start": "00:01:02.000", "clip_end": "00:01:04.000"}]},
        # intro-owned: no window, must contribute nothing
        {"id": 4, "narration": "x", "over_montage": True,
         "delivery": "action"},
        # a NORMAL line with a perfectly good window: the film's track does
        # not play here, so it must not be separated either.
        {"id": 5, "clip_start": "00:03:00.000", "clip_end": "00:03:40.000",
         "delivery": "normal", "narration": "x"},
    ]}
    spans = st.needed_spans(draft, src_dur=600.0)
    if not spans:
        return False, "no spans produced"
    if any(a <= 180.0 <= b for a, b in spans):
        return False, ("the `normal` line's window at 180-220s was separated; "
                       "the film's track does not play there, so separating "
                       "it is 40s of compute for audio nobody hears")
    # the hold must reach 39s (30 + 9), not 31s
    hold = [s for s in spans if s[0] <= 30.0 <= s[1]]
    if not hold or hold[0][1] < 39.0 - 1e-6:
        return False, (f"the hold's real span was not covered: {hold} - it "
                       f"plays 9s from 30s, so coverage must reach 39s")
    # padding applied
    first = [s for s in spans if s[0] <= 10.0 <= s[1]][0]
    if abs(first[0] - (10.0 - pad)) > 1e-6:
        return False, f"padding not applied: {first}"
    # the two abutting montage segments must be merged into one span
    mont = [s for s in spans if s[0] <= 60.0 <= s[1]]
    if len(mont) != 1 or mont[0][1] < 64.0:
        return False, f"abutting montage segments were not merged: {mont}"
    total = sum(b - a for a, b in spans)
    if total >= 600.0:
        return False, "spans cover the whole film; the point is to cover less"
    return True, (f"{len(spans)} merged span(s), {total:.0f}s of a 600s film; "
                  f"the hold's real 9s span is covered and padding is applied")


def test_span_coverage() -> tuple[bool, str]:
    """A window that moved onto un-separated audio must be detected."""
    man = {"spans": [[0.0, 100.0]]}
    # fully covered
    if st._covered(man, [(10.0, 20.0)]):
        return False, "a covered span was reported as missing"
    # partly outside
    miss = st._covered(man, [(90.0, 130.0)])
    if not miss:
        return False, "a span running past the separated range was not detected"
    if abs(miss[0][0] - 100.0) > 1e-6:
        return False, f"the missing part was mis-identified: {miss}"
    # entirely outside
    if not st._covered(man, [(200.0, 210.0)]):
        return False, "a span wholly outside the separated range was missed"
    return True, ("spans outside the separated range are detected, including "
                  "the uncovered TAIL of a partly-covered span")


def test_cache_keyed_to_source() -> tuple[bool, str]:
    pdir = Path(config.project_dir(PROJ))
    _teardown()
    pdir.mkdir(parents=True, exist_ok=True)
    try:
        src = pdir / "source.mp4"
        _ff("-f", "lavfi", "-i", "testsrc=size=160x90:rate=24:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=200:duration=2",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(src))
        sdir = st.stem_dir(pdir)
        sdir.mkdir(parents=True, exist_ok=True)
        st.no_vocals_path(pdir).write_bytes(b"x" * 1024)
        (sdir / st.MANIFEST).write_text(
            json.dumps(st._source_fingerprint(src)), encoding="utf-8")
        if not st.is_current(pdir, src):
            return False, "a matching manifest was not accepted"
        # change the source -> the cache must be void
        import time
        time.sleep(1.1)
        _ff("-f", "lavfi", "-i", "testsrc=size=160x90:rate=24:duration=3",
            "-f", "lavfi", "-i", "sine=frequency=300:duration=3",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(src))
        if st.is_current(pdir, src):
            return False, ("stems separated from a DIFFERENT source were "
                           "reused - a re-ingested film would keep the "
                           "previous film's audio")
        return True, ("the cache is keyed to the source's size+mtime+model, so "
                      "a re-ingested source invalidates it")
    finally:
        _teardown()


def test_clip_signature() -> tuple[bool, str]:
    """Switching stems on must change every clip's cache key."""
    from pipeline.render import _clip_signature
    pdir = Path(config.project_dir(PROJ))
    _teardown()
    pdir.mkdir(parents=True, exist_ok=True)
    try:
        src = pdir / "s.mp4"
        src.write_bytes(b"x" * 64)
        aud = pdir / "a.mp3"
        aud.write_bytes(b"y" * 64)
        stem = pdir / "no_vocals.wav"
        stem.write_bytes(b"z" * 64)
        # `idx` became `line_id`: the zoom phase and the cache key are keyed
        # on the line's own id now, not its position in the draft.
        base = dict(source=src, start=1.0, end=5.0, hold=0.0, line_id=0,
                    crop_top=0.0, narr_dur=3.0, audio_path=aud)
        a = _clip_signature(**base, film_audio=True, film_src=None)
        b = _clip_signature(**base, film_audio=True, film_src=stem)
        if a == b:
            return False, ("the clip cache key ignores which audio the film is "
                           "heard through - enabling stems would serve the "
                           "whole film from cache with the dialogue still in it")
        c = _clip_signature(**base, film_audio=True, film_src=stem,
                            film_speaks=True)
        if c == b:
            return False, ("film_speaks is not in the key, so a unit that must "
                           "read the ORIGINAL mix could be served a cached "
                           "stem-based clip")
        return True, ("the clip cache key covers both the stem identity and "
                      "film_speaks")
    finally:
        _teardown()


def test_hold_uses_stem() -> tuple[bool, str]:
    """A hold reads the stem; film_speaks reads the original mix."""
    src = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                  encoding="utf-8").read()
    i = src.find("def _build_silence_clip")
    j = src.find("\ndef ", i + 10)
    body = src[i:j]
    if "_use_stem" not in body:
        return False, "the hold builder has no stem path at all"
    if "not film_speaks" not in body:
        return False, ("the hold builder does not exempt film_speaks - either "
                       "holds keep the dialogue, or film_speaks loses it")
    return True, ("a hold reads the no-vocals stem; a film_speaks unit reads "
                  "the original mix, which is the only place it is used")


def test_require_stops() -> tuple[bool, str]:
    """A missing separation must stop the render, not fall back silently."""
    src = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                  encoding="utf-8").read()
    if "FILM_AUDIO_REQUIRE_STEMS" not in src:
        return False, "render.py does not consult FILM_AUDIO_REQUIRE_STEMS"
    i = src.find("no no-vocals stem")
    if i < 0:
        return False, "render.py has no missing-stem branch"
    window = src[i:i + 900]
    if "sys.exit(1)" not in window:
        return False, ("a missing stem does not stop the render - it would "
                       "fall through to the un-separated mix, which is the "
                       "defect stems exist to remove")
    if "install" not in window.lower():
        return False, "the stop does not say how to fix it"
    if not config.FILM_AUDIO_REQUIRE_STEMS:
        return False, "config.FILM_AUDIO_REQUIRE_STEMS is False by default"
    return True, ("a missing separation stops the render and names the "
                  "install; the muted fallback is opt-in only")


def test_separate_real() -> tuple[bool, str]:
    """END TO END on a few seconds of REAL audio: extract, separate, assemble.

    This is the only test that exercises Demucs itself. It is deliberately
    tiny - a 6-second window - because the point is to prove the path, not the
    throughput. Reported as a skip, never a silent pass, when demucs is absent.
    """
    ok, why = st.available()
    if not ok:
        return False, f"SKIPPED - demucs unavailable: {why}"

    real = Path(config.project_dir("tokyodrift2006")) / "source.mp4"
    pdir = Path(config.project_dir(PROJ))
    _teardown()
    pdir.mkdir(parents=True, exist_ok=True)
    try:
        src = pdir / "source.mp4"
        if real.exists():
            # 20s of the real film, so there is genuine dialogue to remove
            _ff("-ss", "600", "-t", "20", "-i", str(real),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-pix_fmt", "yuv420p", "-c:a", "aac", str(src))
        else:
            _ff("-f", "lavfi", "-i", "testsrc=size=160x90:rate=24:duration=20",
                "-f", "lavfi", "-i", "sine=frequency=220:duration=20",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src))

        # a draft binding ONE 6-second window: only that span should separate
        io.open(pdir / "draft.json", "w", encoding="utf-8").write(json.dumps({
            "project": PROJ, "title": "Stem (2026)", "target_minutes": 1,
            "voice": "tts",
            "lines": [{"id": 1, "narration": "A line over the engines.",
                       "clip_start": "00:00:05.000",
                       "clip_end": "00:00:11.000", "delivery": "normal"}]}))

        out = st.separate(PROJ)
        if out is None:
            return False, "separation returned None on real audio"
        if not out.exists() or out.stat().st_size == 0:
            return False, "the no-vocals file is missing or empty"

        total = _dur(src)
        got = _dur(out)
        if abs(got - total) > 1.0:
            return False, (f"the assembled stem is {got:.1f}s but the source "
                           f"is {total:.1f}s - absolute seeks into it would "
                           f"land on the wrong audio")
        man = json.loads((st.stem_dir(pdir) / st.MANIFEST)
                         .read_text(encoding="utf-8"))
        spans = man.get("spans") or []
        if not spans:
            return False, "the manifest records no separated spans"
        span_sec = sum(b - a for a, b in spans)
        if span_sec >= total - 1.0:
            return False, (f"{span_sec:.1f}s of {total:.1f}s separated - the "
                           f"span limiting did not apply")
        # a second call must be a cache hit, not a re-separation
        import time
        t0 = time.time()
        again = st.separate(PROJ)
        if again is None or time.time() - t0 > 20:
            return False, "the second call re-separated instead of caching"
        return True, (f"extract -> separate -> assemble works on real audio: "
                      f"{span_sec:.1f}s separated of a {total:.1f}s source, "
                      f"assembled to {got:.1f}s, second call cached")
    finally:
        _teardown()


def test_film_speaks_gate() -> tuple[bool, str]:
    """film_speaks is the ONLY original dialogue left, so it is bounded.

    Also locks the schema fix: film_speaks_seconds and film_speaks_reason were
    missing from Line, so _drop_unknown stripped them and every gate that
    inspects Line objects was blind to the unit. render.py reads the raw dict,
    so the feature worked while being unenforceable.
    """
    from pipeline.schemas import Line, _drop_unknown
    ln = Line(id=1, narration="", film_speaks_seconds=6.0,
              film_speaks_reason="lands the R4 reveal")
    if ln.film_speaks_seconds != 6.0 or not ln.film_speaks_reason:
        return False, "the schema does not carry film_speaks fields"
    kept = _drop_unknown(Line, {"id": 2, "narration": "",
                                "film_speaks_seconds": 6.0,
                                "film_speaks_reason": "the climax",
                                "junk": 1})
    if "film_speaks_seconds" not in kept or "film_speaks_reason" not in kept:
        return False, ("_drop_unknown still strips the film_speaks fields, so "
                       "no gate can see the unit")
    if int(config.FILM_SPEAKS_MAX_PER_FILM) > 3:
        return False, (f"FILM_SPEAKS_MAX_PER_FILM is "
                       f"{config.FILM_SPEAKS_MAX_PER_FILM}; the cap is 3 now "
                       f"that this is the only original dialogue in the video")
    must = tuple(getattr(config, "FILM_SPEAKS_MUST_SERVE", ()))
    if not {"reveal", "climax", "thesis"} <= set(must):
        return False, f"FILM_SPEAKS_MUST_SERVE is {must}"
    # draft.py must DELEGATE to the one rule set rather than hold a second
    # copy of the rules. It briefly held both, and they disagreed the moment
    # the schema grew: the inline copy looked for the criterion inside
    # `film_speaks_reason` after it moved to its own field, and spaced units by
    # LINE ID - calling two units 3,766 seconds apart "1 apart". The individual
    # gate behaviours are covered by tools/test_film_speaks.py; duplicating
    # them here is how the two copies drifted in the first place.
    src = io.open(os.path.join(ROOT, "pipeline", "draft.py"),
                  encoding="utf-8").read()
    if "[FILM-SPEAKS]" not in src:
        return False, "no [FILM-SPEAKS] gate in draft.py"
    i = src.find("[FILM-SPEAKS]: the only place")
    window = src[i:i + 2600]
    for probe, label in (("film_speaks as _fsmod", "the rule set import"),
                         ("_fsmod.audit(", "the rule set call"),
                         ('sev = "hard"', "a hard failure")):
        if probe not in window:
            return False, f"draft.py does not use {label}"
    if "MIN_SPACING_LINES" in window:
        return False, ("draft.py is spacing film_speaks units by LINE ID "
                       "again - meaningless once units carry appended ids")
    return True, (f"film_speaks is typed, survives _drop_unknown, capped at "
                  f"{config.FILM_SPEAKS_MAX_PER_FILM}, must name a "
                  f"{'/'.join(must)}, and draft.py delegates to the single "
                  f"rule set as a hard failure")


def test_stem_reaches_ffmpeg() -> tuple[bool, str]:
    """The stem must actually be the audio ffmpeg reads - not just resolved.

    Everything upstream can look right while the filter graph still reads
    [0:a], the source's own track. So this captures the REAL ffmpeg command
    for all four cases and checks which input the film-audio chain references.

    It also pins the log message, which said "source audio mixed under the
    voice" long after the stem was in use - a reader checking whether the
    dialogue fix had taken effect saw a description of the behaviour it
    replaced.
    """
    import re
    import tempfile
    from pipeline import render as R

    cap: dict = {}
    orig_run = R._run
    R._run = lambda cmd, desc: cap.update(cmd=list(cmd))
    tmp = Path(tempfile.mkdtemp(prefix="stemff_"))
    try:
        src, aud, stem = tmp / "s.mp4", tmp / "a.mp3", tmp / "no_vocals.wav"
        for p in (src, aud, stem):
            p.write_bytes(b"x" * 256)

        def graph_uses_stem():
            cmd = cap["cmd"]
            g = cmd[cmd.index("-filter_complex") + 1]
            ins = [cmd[i + 1] for i, x in enumerate(cmd) if x == "-i"]
            si = ins.index(str(stem)) if str(stem) in ins else None
            return (si is not None and f"[{si}:a]" in g), ("[0:a]" in g)

        ff = config.ffmpeg()
        # 1. narrated clip WITH a stem -> must read the stem, never [0:a]
        R._build_clip(ff, src, 10.0, 20.0, aud, 5.0, tmp / "o.mp4", 0, 0.0,
                      0.0, "none", None, 0.0, lead_in=0.5, film_audio=True,
                      film_src=stem, src_wh=(1280, 544))
        used, raw = graph_uses_stem()
        if not used or raw:
            return False, (f"a narrated clip did not read the stem "
                           f"(stem={used}, source track={raw})")
        # 2. narrated clip with NO stem -> falls back to the source track
        R._build_clip(ff, src, 10.0, 20.0, aud, 5.0, tmp / "o.mp4", 0, 0.0,
                      0.0, "none", None, 0.0, lead_in=0.5, film_audio=True,
                      film_src=None, src_wh=(1280, 544))
        used, raw = graph_uses_stem()
        if used or not raw:
            return False, "with no stem the clip did not fall back to [0:a]"
        # 3. a HOLD must read the stem
        R._build_silence_clip(ff, src, 10.0, 20.0, tmp / "o.mp4", 4.0, 0, 0.0,
                              "none", None, 0.0, film_audio=True,
                              film_speaks=False, film_src=stem,
                              src_wh=(1280, 544))
        used, raw = graph_uses_stem()
        if not used or raw:
            return False, ("a HOLD did not read the stem - at -6 dB its "
                           "dialogue is the clearest thing in the recap")
        # 4. a FILM_SPEAKS unit must read the ORIGINAL mix
        R._build_silence_clip(ff, src, 10.0, 20.0, tmp / "o.mp4", 4.0, 0, 0.0,
                              "none", None, 0.0, film_audio=True,
                              film_speaks=True, film_src=stem,
                              src_wh=(1280, 544))
        used, raw = graph_uses_stem()
        if used or not raw:
            return False, ("a film_speaks unit read the STEM - it is the one "
                           "place the characters are supposed to be heard")
    finally:
        R._run = orig_run
        shutil.rmtree(tmp, ignore_errors=True)

    # the message must name which audio it used
    rsrc = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                   encoding="utf-8").read()
    i = rsrc.find("Film audio:[/] {_src_label}")
    if i < 0:
        return False, ("the Film audio log line does not report WHICH audio "
                       "was used - it said 'source audio mixed under the "
                       "voice' for a whole release after stems landed")
    if "NO-VOCALS stem" not in rsrc or "UN-SEPARATED" not in rsrc:
        return False, "the message does not distinguish stem from source track"
    return True, ("captured from the real ffmpeg command: narrated clips and "
                  "holds read the stem, film_speaks reads the original mix, "
                  "no stem falls back to the source track, and the log names "
                  "which")


TESTS = {
    "AVAILABILITY":          test_availability,
    "STEM-REACHES-FFMPEG":   test_stem_reaches_ffmpeg,
    "FILM-SPEAKS-GATE":      test_film_speaks_gate,
    "NEEDED-SPANS":          test_needed_spans,
    "SPAN-COVERAGE":         test_span_coverage,
    "CACHE-KEYED-TO-SOURCE": test_cache_keyed_to_source,
    "CLIP-SIGNATURE":        test_clip_signature,
    "HOLD-USES-STEM":        test_hold_uses_stem,
    "REQUIRE-STOPS":         test_require_stops,
    "SEPARATE-REAL":         test_separate_real,
}

# SEPARATE-REAL loads a neural model and separates real audio. It is the only
# test that exercises Demucs rather than the plumbing around it, and it is far
# slower than everything else here, so it is OPT-IN:
#       python tools/test_stems.py SEPARATE-REAL
# It is excluded from the default run so a suite that should take seconds does
# not take minutes - not because it is optional. Run it after any change to
# pipeline/stems.py.
SLOW = ("SEPARATE-REAL",)

if __name__ == "__main__":
    want = sys.argv[1:] or [k for k in TESTS if k not in SLOW]
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
    skipped = [k for k in SLOW if k not in want]
    if skipped:
        print(f"(not run: {', '.join(skipped)} - slow, run it explicitly "
              f"after changing pipeline/stems.py)")
    print("test_stems: all pass" if not bad else
          f"test_stems: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
