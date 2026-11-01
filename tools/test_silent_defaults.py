"""Unreadable input must be REPORTED, never turned into a default that passes.

THE DEFECT CLASS
----------------
Each of these turned a read/measure/write failure into an ordinary-looking
value that changed the output, with nothing said:

  * preflight.stale_audio      unreadable TTS manifest -> [] ("all fresh")
  * preflight._audio_dur       ffprobe failure -> 0.0, so capacity_findings
                               skipped the line: an overrun went unjudged
  * render timeline.json       a failed write left the PREVIOUS render's
                               timeline in place, read downstream as this one
  * music music_plan.json      a failed write (`except OSError: pass`) left
                               the previous plan, so MUSIC-CUE measured this
                               mix at another cut's cue positions
  * intro bound_windows        unreadable draft.json -> [] ("story shows
                               nothing"), freeing the montage to replay it
  * intro _measured_dur        ffprobe failure -> 0.0s block length, shifting
                               the intro offset
  * draft broll.json           unreadable -> empty pool, reported as "unknown
                               label" script errors

Cases
-----
  STALE-UNKNOWN-REPORTED   corrupt / missing manifest -> [] WITH a note naming
                           the consequence; a valid manifest -> no note.
  AUDIO-DUR-NONE           a failed probe is None, not 0.0.
  UNMEASURED-REPORTED      a line whose narration cannot be measured is listed
                           as not judged, never silently skipped.
  TIMELINE-WRITE-FAIL      a failed timeline.json write removes the stale file
                           and fails RENDER-CHECK (real render of the fixture).
  MUSIC-PLAN-WRITE-FAIL    a failed music_plan.json write removes the stale
                           plan and says what the cue check loses.
  INTRO-DRAFT-UNREADABLE   bound_windows says the story windows are unknown.
  INTRO-DUR-RAISES         a block that cannot be measured raises, not 0.0.
  BROLL-UNREADABLE         a corrupt broll.json is named as the cause.

Run:  python tools/test_silent_defaults.py
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config  # noqa: E402
from rich.console import Console  # noqa: E402


class _Rec:
    """Swap a module's console for a recording one."""

    def __init__(self, mod):
        self.mod = mod

    def __enter__(self):
        self.old = self.mod.console
        self.c = Console(record=True, width=400)
        self.mod.console = self.c
        return self

    def __exit__(self, *exc):
        self.mod.console = self.old

    @property
    def text(self):
        return self.c.export_text(clear=False)


def _tmpproj(name: str) -> Path:
    pdir = Path(config.project_dir(name))
    shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir(parents=True)
    return pdir


def test_stale_unknown_reported():
    from pipeline import preflight as pf
    from pipeline.tts import DEFAULT_PROVIDER
    from pipeline.tts_providers import all_providers
    pdir = _tmpproj("_silent_stale")
    try:
        (pdir / "narration").mkdir()
        draft = {"lines": [{"id": 1, "narration": "some words here"}]}
        # missing manifest
        ids, note = pf.stale_audio_status(draft, pdir)
        if ids != [] or not note or "UNKNOWN" not in note:
            return False, f"missing manifest gave {ids}, note {note!r}"
        # corrupt manifest: reported, and stale_audio prints it
        (pdir / "narration" / "_cache.json").write_text("{not json")
        with _Rec(pf) as r:
            ids = pf.stale_audio(draft, pdir)
        if ids != [] or "could not be read" not in r.text \
                or "judged as if it matches" not in r.text:
            return False, f"corrupt manifest not reported: {r.text!r}"
        # valid manifest: no note
        prov = all_providers().get(DEFAULT_PROVIDER)
        sig = prov.cache_signature("some words here", "normal", 1.0)
        (pdir / "narration" / "_cache.json").write_text(
            json.dumps({"line_001.mp3": sig}))
        ids, note = pf.stale_audio_status(draft, pdir)
        if ids != [] or note is not None:
            return False, f"valid manifest gave {ids}, note {note!r}"
        return True, ("missing/corrupt manifest -> [] with a note naming the "
                      "consequence; valid manifest -> no note")
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_audio_dur_none():
    from pipeline import preflight as pf
    d = Path(tempfile.mkdtemp())
    try:
        bad = d / "bad.mp3"
        bad.write_bytes(b"\0" * 512)
        got = pf._audio_dur(config.ffprobe(), bad)
        return got is None, f"failed probe -> {got!r} (want None)"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_unmeasured_reported():
    from pipeline import preflight as pf
    d = Path(tempfile.mkdtemp())
    try:
        bad = d / "line_001.mp3"
        bad.write_bytes(b"\0" * 512)
        draft = {"lines": [{"id": 1, "narration": "w " * 40,
                            "clip_start": "00:00:10.0",
                            "clip_end": "00:00:12.0"}]}
        un: list = []
        with _Rec(pf) as r:
            f = pf.capacity_findings(draft, [(1, bad, 0.0)], unmeasured=un)
        if un != [1]:
            return False, f"unmeasured line not listed: {un}"
        if "NOT judged" not in r.text:
            return False, "unmeasured line not reported on the console"
        if f:
            return False, f"an unmeasured line produced a finding: {f}"
        return True, ("a line whose narration cannot be measured is listed "
                      "and printed as NOT judged")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_timeline_write_fail():
    import test_render_smoke as T
    from pipeline import intro as _intro
    from pipeline.render import render
    orig = T._stub_intro_tts()
    restore = T._no_stems()
    real_write = Path.write_text

    def failing(self, *a, **k):
        if self.name == "timeline.json.tmp":
            raise OSError("disk full (simulated)")
        return real_write(self, *a, **k)
    try:
        pdir, draft = T._setup()
        stale = pdir / "timeline.json"
        stale.write_text(json.dumps({"lines": [], "stale": True}))
        narration = T._narration_for(pdir, draft["lines"])
        Path.write_text = failing
        try:
            render(T.PROJ, draft, narration, music=None, captions=False,
                   keep_temp=False, force_clips=True)
        finally:
            Path.write_text = real_write
        if stale.exists():
            return False, "the previous render's timeline.json was left in place"
        rep = (pdir / "final_report.md").read_text(encoding="utf-8")
        row = [ln for ln in rep.splitlines() if ln.startswith("| `RENDER-CHECK`")]
        if not row or "PASS" in row[0] or "timeline.json could not be written" \
                not in row[0]:
            return False, f"RENDER-CHECK does not report it: {row}"
        return True, ("failed write -> stale timeline.json removed and "
                      "RENDER-CHECK names it")
    finally:
        Path.write_text = real_write
        _intro._tts_line = orig
        restore()
        T._teardown()


def _silent(path: Path, sec: float) -> None:
    subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=48000:cl=mono", "-t", f"{sec:.2f}",
                    str(path)], capture_output=True)


def test_music_plan_write_fail():
    from pipeline import music
    pdir = _tmpproj("_silent_music")
    real_write = Path.write_text

    def failing(self, *a, **k):
        if self.name == "music_plan.json.tmp":
            raise OSError("disk full (simulated)")
        return real_write(self, *a, **k)
    try:
        bed = pdir / "bed.wav"
        _silent(bed, 5)
        (pdir / "music_plan.json").write_text(json.dumps(
            {"cues": [{"at": 99.0, "dur": 4.0, "mood": "stale"}]}))
        Path.write_text = failing
        try:
            with _Rec(music) as r:
                music.build_music_track(config.ffmpeg(), pdir,
                                        pdir / "track.wav", 4.0, bed, [])
        finally:
            Path.write_text = real_write
        if (pdir / "music_plan.json").exists():
            return False, "the previous mix's music_plan.json was left in place"
        if "could not write music_plan.json" not in r.text:
            return False, f"the failure was not reported: {r.text[-300:]!r}"
        return True, ("failed write -> stale plan removed, failure reported "
                      "with what the cue check loses")
    finally:
        Path.write_text = real_write
        shutil.rmtree(pdir, ignore_errors=True)


def test_intro_draft_unreadable():
    from pipeline import intro
    pdir = _tmpproj("_silent_intro")
    try:
        (pdir / "draft.json").write_text("{broken")
        with _Rec(intro) as r:
            got = intro.bound_windows("_silent_intro")
        ok = got == [] and "UNKNOWN" in r.text
        return ok, ("unreadable draft.json -> [] with a note"
                    if ok else f"not reported: {got} {r.text!r}")
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_intro_dur_raises():
    from pipeline import intro
    d = Path(tempfile.mkdtemp())
    try:
        bad = d / "block.mp4"
        bad.write_bytes(b"\0" * 512)
        try:
            v = intro._measured_dur(bad)
        except RuntimeError as e:
            return True, f"unmeasurable block raises: {e}"[:120]
        return False, f"unmeasurable block measured as {v!r}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_broll_unreadable():
    from pipeline import draft as dr
    pdir = _tmpproj("_silent_broll")
    try:
        (pdir / "draft.json").write_text(json.dumps({
            "project": "_silent_broll", "title": "T",
            "lines": [{"id": 1, "pool": "cars", "delivery": "normal",
                       "narration": "The cars line up at the start."}]}))
        (pdir / "broll.json").write_text("{broken")
        with _Rec(dr) as r:
            try:
                dr.validate_draft("_silent_broll")
            except SystemExit:
                pass
        if "broll.json exists but could not be read" not in r.text:
            return False, "a corrupt broll.json was not named as the cause"
        return True, "corrupt broll.json is reported as the cause"
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


TESTS = {
    "STALE-UNKNOWN-REPORTED": test_stale_unknown_reported,
    "AUDIO-DUR-NONE":         test_audio_dur_none,
    "UNMEASURED-REPORTED":    test_unmeasured_reported,
    "TIMELINE-WRITE-FAIL":    test_timeline_write_fail,
    "MUSIC-PLAN-WRITE-FAIL":  test_music_plan_write_fail,
    "INTRO-DRAFT-UNREADABLE": test_intro_draft_unreadable,
    "INTRO-DUR-RAISES":       test_intro_dur_raises,
    "BROLL-UNREADABLE":       test_broll_unreadable,
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
    print("test_silent_defaults: all pass" if not bad else
          f"test_silent_defaults: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
