"""END-TO-END RENDER SMOKE TEST - the real render path, a tiny fake film.

WHY THIS EXISTS
---------------
The first full production render crashed on line 1 of the clip loop:

    KeyError: 'clip_start'      (render.py, `start = parse_ts(ln["clip_start"])`)

The clip loop skipped `over_montage` lines, which carry no clip window, but not
`film_intro` lines, which are the same category and were added later. Every
draft gate passed. check_craft passed. gate_selftest passed. The defect was
invisible to all of them because they validate draft.json and never RUN the
renderer - and the first time the renderer actually ran over a draft containing
a film_intro line was the first production render, 17 minutes of narration in.

A gate on the draft cannot catch a bug in the code that consumes the draft. So
this test renders a ~30-second fake film through `pipeline.render.render()` -
the real function, the real ffmpeg, the real intro builder - over a fixture
draft that contains ONE OF EVERY LINE TYPE:

    over_montage hook   (no clip window - intro builder owns it)
    film_intro line     (no clip window - intro builder owns it)  <- the crash
    3 bound lines       (ordinary clip_start/clip_end)
    1 hold              (narration_silence_seconds: wordless, music swell)
    1 film_speaks       (wordless, film audio at full level)

It is offline and takes seconds: the source is ffmpeg `testsrc`, and narration
is a generated tone of a known length instead of a TTS call, so no API key and
no network are involved. The thing under test is the RENDER path, not the voice.

WHAT THIS TEST DOES *NOT* PROVE
-------------------------------
[RENDER-CHECK] will report a positional drift on this fixture, and that finding
is MEANINGLESS here: the gate locates each line by finding its narration's
onset in the finished audio, and a 330 Hz tone under a music bed is not speech
for an envelope detector. Positional accuracy is proven separately, with
controlled envelopes, by tools/test_render_position.py - which is also where
the intro-offset regression lives. Read a RENDER-CHECK line in THIS test's
output as noise; read one in a real render as a finding.

Cases
-----
  1. smoke          - the fixture renders; final.mp4 exists and is ~the right
                      length; no line type raises.
  2. intro_owned    - EVERY flag in render.INTRO_OWNED survives a render, by
                      rendering a draft that uses each one. A new intro-owned
                      line type added without updating the clip loop fails here
                      instead of on a production render.
  3. censor_montage - a shot flagged for blur that is used ONLY in a montage
                      (no line bound to it) must STOP the render. This is the
                      "used but unblurred" class that the old "no line bound"
                      warning reported as if it were harmless.
  4. censor_unused  - a flagged shot that appears NOWHERE in the video must NOT
                      stop the render. The two must not be conflated.

Run:  python tools/test_render_smoke.py
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

PROJ = "_smoke_render"


# --------------------------------------------------------------------------- #
# fixture helpers
# --------------------------------------------------------------------------- #
def _ff(*args) -> None:
    """Run ffmpeg quietly; raise with the tail of stderr if it fails."""
    cmd = [config.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", *args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {(r.stderr or '')[-400:]}")


def _dur(p: Path) -> float:
    r = subprocess.run(
        [config.ffprobe(), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


def _make_source(pdir: Path, seconds: int = 90) -> None:
    """A synthetic film: moving test pattern + a tone, so the render has real
    video AND a real audio stream to mix (film_speaks needs one)."""
    _ff("-f", "lavfi", "-i", f"testsrc=size=640x360:rate=30:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(pdir / "source.mp4"))


def _silent_mp3(path: Path, seconds: float) -> None:
    _ff("-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
        "-t", f"{seconds:.3f}", "-c:a", "libmp3lame", "-q:a", "9", str(path))


def _voice_mp3(path: Path, seconds: float) -> None:
    """Stand-in narration that actually MAKES A SOUND.

    Not silence: RENDER-CHECK measures each line's position by finding the
    narration's onset in the finished audio, and silent narration has no onset
    to find - it reported a bogus 6s drift on every line, which is exactly the
    kind of noise that teaches you to ignore a gate. A tone that starts after a
    short lead of silence gives the envelope a real edge to lock onto.
    """
    seconds = max(0.6, float(seconds))
    _ff("-f", "lavfi", "-i", f"sine=frequency=330:duration={seconds:.3f}",
        "-af", f"volume=0.9,afade=t=in:st=0:d=0.02,"
               f"afade=t=out:st={seconds - 0.05:.3f}:d=0.05",
        "-c:a", "libmp3lame", "-q:a", "4", str(path))


def _narration_for(pdir: Path, lines: list[dict]) -> list:
    """[(id, Path, dur)] - silent audio of a plausible length per line.

    Mirrors what pipeline.tts.generate_tts returns, without a provider. Lines
    that carry no narration (hold / film_speaks) are absent, exactly as the
    real TTS pass leaves them.
    """
    ndir = pdir / "narration"
    ndir.mkdir(exist_ok=True)
    out = []
    for ln in lines:
        if (ln.get("narration_silence_seconds") is not None
                or ln.get("film_speaks_seconds") is not None):
            continue
        txt = str(ln.get("narration") or "").strip()
        if not txt:
            continue
        # Duration from SYLLABLE count, not word count. Real speech runs at a
        # roughly constant syllable rate, so deriving length from words makes
        # lines of long words artificially fast in syllables/sec - which is the
        # metric the voice-consistency gate measures tempo with. The earlier
        # word-based model made this fixture fail [VOICE-CONSISTENCY] for its
        # own vocabulary rather than for anything the render did.
        from pipeline.voice_check import _syllables
        syls = sum(_syllables(w) for w in txt.split()) or 1
        dur = max(1.0, syls / 4.3)        # ~4.3 syllables/sec
        p = ndir / f"line_{ln['id']:03d}.mp3"
        _voice_mp3(p, dur)
        out.append((ln["id"], p, _dur(p)))
    return out


def _fixture_draft() -> dict:
    """One of every line type, ~30s of narration over a 90s fake film."""
    return {
        "project": PROJ, "title": "Smoke Test (2026)", "target_minutes": 1,
        "voice": "tts",
        "lines": [
            # the hook, spoken OVER THE MONTAGE: no clip window by design
            {"id": 1, "over_montage": True, "delivery": "hook",
             "narration": "He had one night left and nobody told him why."},
            # the film-intro facts: no clip window by design. THE CRASH.
            {"id": 2, "film_intro": True, "delivery": "intro",
             "narration": "Welcome back to the channel. Today we are watching "
                          "Smoke Test, from twenty twenty six."},
            # three ordinary bound lines
            {"id": 3, "clip_start": "00:00:10.0", "clip_end": "00:00:18.0",
             "delivery": "normal", "note": "B01",
             "narration": "The pattern drifts left while the tone holds flat."},
            {"id": 4, "clip_start": "00:00:20.0", "clip_end": "00:00:28.0",
             "delivery": "tense", "note": "B02",
             "narration": "Something in the signal starts to come apart here."},
            {"id": 5, "clip_start": "00:00:30.0", "clip_end": "00:00:38.0",
             "delivery": "reveal", "note": "B03",
             "narration": "And then the colour bars give the whole thing away."},
            # a HOLD: wordless, music swells
            {"id": 6, "clip_start": "00:00:40.0", "clip_end": "00:00:45.0",
             "narration": "", "narration_silence_seconds": 3.0, "note": "B04"},
            # FILM SPEAKS: wordless, the film's own audio at full level
            {"id": 7, "clip_start": "00:00:50.0", "clip_end": "00:00:56.0",
             "narration": "", "film_speaks_seconds": 4.0, "note": "B05"},
        ],
    }


def _shots(flag_window: tuple | None = None) -> dict:
    """shots.json covering the fixture's windows; optionally flag one for blur."""
    shots = []
    for a, b, sid in ((10, 18, "s01"), (20, 28, "s02"), (30, 38, "s03"),
                      (40, 45, "s04"), (50, 56, "s05"), (60, 68, "s06")):
        s = {"id": sid, "clip_start": f"00:00:{a:04.1f}",
             "clip_end": f"00:00:{b:04.1f}", "action": "test pattern",
             "chars": []}
        shots.append(s)
    if flag_window:
        want = f"00:00:{flag_window[0]:04.1f}"
        for s in shots:
            if s["clip_start"] == want:
                s["censor"] = "blur"
    return {"shots": shots}


def _write(pdir: Path, draft: dict, shots: dict) -> None:
    io.open(pdir / "draft.json", "w", encoding="utf-8").write(
        json.dumps(draft, indent=2))
    io.open(pdir / "shots.json", "w", encoding="utf-8").write(
        json.dumps(shots, indent=2))
    # reveals.json: the intro paths ask where the first reveal lands so the
    # montage cannot spoil it. Put it late so the fixture has room.
    io.open(pdir / "reveals.json", "w", encoding="utf-8").write(json.dumps(
        {"reveals": [{"id": "R1", "land_ref": "00:01:10",
                      "what": "the bars", "holds": ["bars"]}]}, indent=2))


def _setup(flag_window: tuple | None = None, source_sec: int = 90) -> tuple:
    pdir = Path(config.project_dir(PROJ))
    if pdir.exists():
        shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir(parents=True, exist_ok=True)
    _make_source(pdir, source_sec)
    draft = _fixture_draft()
    _write(pdir, draft, _shots(flag_window))
    # music: a bed + one cue, so resolve_music's bed+cues path is exercised
    mdir = pdir / "music" / "cues"
    mdir.mkdir(parents=True, exist_ok=True)
    _silent_mp3(pdir / "music" / "bed.mp3", 30)
    _silent_mp3(mdir / "tense1.mp3", 8)
    _silent_mp3(pdir / "intro_music.mp3", 20)    # the montage needs its track
    return pdir, draft


def _teardown() -> None:
    shutil.rmtree(Path(config.project_dir(PROJ)), ignore_errors=True)


def _stub_intro_tts():
    """Make the intro block build OFFLINE.

    pipeline.intro._tts_line calls the production voice provider. The render
    path is what is under test, so swap it for silent audio of a believable
    length - the intro montage, the hook bake and the film-intro segment then
    all run for real, with real ffmpeg, without a key or a network.
    Returns the original so the caller can restore it.
    """
    from pipeline import intro as _intro
    orig = _intro._tts_line

    def _fake(project, ln, out: Path) -> float:
        words = len(str(ln.get("narration") or "").split())
        d = max(1.2, words / (185.0 / 60.0))
        _voice_mp3(Path(out), d)
        return d

    _intro._tts_line = _fake
    return orig


# --------------------------------------------------------------------------- #
# tests
# --------------------------------------------------------------------------- #
def test_smoke() -> tuple[bool, str]:
    """The fixture renders end to end and produces a plausible final.mp4."""
    from pipeline.render import render
    from pipeline import intro as _intro
    orig = _stub_intro_tts()
    try:
        pdir, draft = _setup()
        narration = _narration_for(pdir, draft["lines"])
        if len(narration) != 5:
            return False, (f"fixture should yield 5 narrated lines, got "
                           f"{len(narration)} (hold/film_speaks must be absent)")
        final = render(PROJ, draft, narration, music=None, captions=False,
                       keep_temp=False, force_clips=True)
        final = Path(final)
        if not final.exists():
            return False, "render returned but final.mp4 does not exist"
        d = _dur(final)
        # 5 narrated lines (~30s with leads/gaps) + hold + film_speaks + intro.
        if not (20.0 <= d <= 150.0):
            return False, f"final.mp4 is {d:.1f}s - outside the plausible band"
        tj = pdir / "timeline.json"
        if not tj.exists():
            return False, "timeline.json was not written"
        t = json.loads(tj.read_text(encoding="utf-8"))
        if float(t.get("intro_offset") or 0) <= 0:
            return False, ("intro_offset is 0 - the intro block was not "
                           "prepended, so the over_montage/film_intro lines "
                           "are silently missing from the video")
        return True, (f"rendered {d:.1f}s, intro_offset "
                      f"{float(t['intro_offset']):.1f}s, all 7 line types "
                      f"survived the real render path (ignore RENDER-CHECK "
                      f"above: synthetic narration has no speech envelope)")
    finally:
        _intro._tts_line = orig
        _teardown()


def test_intro_owned() -> tuple[bool, str]:
    """Every flag in render.INTRO_OWNED must survive a render.

    The crash was one missing entry in this set. A new intro-owned line type
    that the clip loop does not skip fails HERE, not on a production render.
    """
    from pipeline import render as _r
    from pipeline.render import render
    from pipeline import intro as _intro
    orig = _stub_intro_tts()
    try:
        bad = []
        for flag in _r.INTRO_OWNED:
            pdir, draft = _setup()
            # one line per intro-owned flag, no clip window, plus the hook so
            # the intro block is built at all
            draft["lines"] = [
                {"id": 1, "over_montage": True, "delivery": "hook",
                 "narration": "One night left and nobody said why."},
                {"id": 2, flag: True, "delivery": "intro",
                 "narration": f"This line is {flag} and owns no clip window."},
                {"id": 3, "clip_start": "00:00:10.0", "clip_end": "00:00:18.0",
                 "delivery": "normal", "note": "B01",
                 "narration": "An ordinary bound line to anchor the story."},
            ]
            narration = _narration_for(pdir, draft["lines"])
            try:
                render(PROJ, draft, narration, music=None, captions=False,
                       keep_temp=False, force_clips=True)
            except Exception as e:
                bad.append(f"{flag}: {type(e).__name__} {e}")
            finally:
                _teardown()
        ok = not bad
        return ok, (f"all {len(_r.INTRO_OWNED)} INTRO_OWNED flag(s) "
                    f"({', '.join(_r.INTRO_OWNED)}) render without a clip "
                    f"window" if ok else "; ".join(bad))
    finally:
        _intro._tts_line = orig


def test_censor_montage() -> tuple[bool, str]:
    """A flagged shot used ONLY in a montage must STOP the render.

    No line is bound to it, so the old census called it an orphan and printed a
    yellow "nothing will blur for them" - while the footage played clear inside
    a montage clip. _build_montage_clip applies no censor filter at all.
    """
    from pipeline.render import render
    from pipeline import intro as _intro
    orig = _stub_intro_tts()
    try:
        pdir, draft = _setup(flag_window=(60, 68))   # s06: flagged
        # nothing BINDS 60-68, but a montage cuts it in
        draft["lines"] = [
            {"id": 1, "over_montage": True, "delivery": "hook",
             "narration": "One night left and nobody said why."},
            {"id": 2, "clip_start": "00:00:10.0", "clip_end": "00:00:18.0",
             "delivery": "normal", "note": "B01",
             "narration": "An ordinary bound line to anchor the story."},
            {"id": 3, "delivery": "normal", "note": "B02",
             "narration": "And the montage runs across the flagged footage.",
             "montage": [{"clip_start": "00:00:60.0", "clip_end": "00:00:64.0"},
                         {"clip_start": "00:00:64.0", "clip_end": "00:00:68.0"}]},
        ]
        narration = _narration_for(pdir, draft["lines"])
        try:
            render(PROJ, draft, narration, music=None, captions=False,
                   keep_temp=False, force_clips=True)
        except SystemExit as e:
            if int(getattr(e, "code", 1) or 0) != 0:
                return True, ("flagged footage used only in a montage STOPS "
                              "the render (exit non-zero), instead of being "
                              "reported as a harmless orphan")
            return False, "render exited 0 despite exposed flagged footage"
        return False, ("render COMPLETED with a flagged shot playing unblurred "
                       "inside a montage - this is the bug")
    finally:
        _intro._tts_line = orig
        _teardown()


def test_censor_unused() -> tuple[bool, str]:
    """A flagged shot that is in NO footage window must not stop the render."""
    from pipeline.render import render
    from pipeline import intro as _intro
    orig = _stub_intro_tts()
    try:
        pdir, draft = _setup(flag_window=(60, 68))   # s06 flagged, never used
        narration = _narration_for(pdir, draft["lines"])
        try:
            final = Path(render(PROJ, draft, narration, music=None,
                                captions=False, keep_temp=False,
                                force_clips=True))
        except SystemExit:
            return False, ("a flagged shot that never appears in the video "
                           "stopped the render - 'not used' was conflated with "
                           "'used but unblurred'")
        ok = final.exists() and _dur(final) > 10.0
        return ok, ("a flagged shot absent from the cut is reported and "
                    "allowed" if ok else "render produced no usable final.mp4")
    finally:
        _intro._tts_line = orig
        _teardown()


def test_censor_bound() -> tuple[bool, str]:
    """A flagged shot WITH a line bound to it renders blurred and does not trip
    the audit. The counterpart to CENSOR-MONTAGE: a resolver that marked
    everything exposed would stop every censored render, and 'stop the render'
    must mean something specific, not 'there is a censor flag anywhere'."""
    from pipeline.render import render
    from pipeline import censor as _censor
    from pipeline import intro as _intro
    orig = _stub_intro_tts()
    try:
        pdir, draft = _setup(flag_window=(10, 18))   # s01, bound by line 3
        narration = _narration_for(pdir, draft["lines"])
        try:
            final = Path(render(PROJ, draft, narration, music=None,
                                captions=False, keep_temp=False,
                                force_clips=True))
        except SystemExit:
            return False, ("a flagged shot that IS bound to a line stopped the "
                           "render - the blur resolves for it, so it is covered")
        flagged = _censor.flagged_shots(pdir)
        ok = final.exists() and len(flagged) == 1
        return ok, ("a flagged shot bound to a line is classified blurred and "
                    "the render completes" if ok else
                    f"final={final.exists()} flagged={len(flagged)}")
    finally:
        _intro._tts_line = orig
        _teardown()


TESTS = {
    "SMOKE":          test_smoke,
    "INTRO-OWNED":    test_intro_owned,
    "CENSOR-MONTAGE": test_censor_montage,
    "CENSOR-UNUSED":  test_censor_unused,
    "CENSOR-BOUND":   test_censor_bound,
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
        print(f'{"PASS" if ok else "FAIL"}  {name:<16} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_render_smoke: all pass" if not bad else
          f"test_render_smoke: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
