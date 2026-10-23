# -*- coding: utf-8 -*-
"""
test_render_position.py - fixture test for render.py::_position_offsets, the
engine of the [RENDER-CHECK] positional gate.

Why this exists
---------------
[RENDER-CHECK] reported "narration is out of step with timeline.json by up to
5.53s" after the beat-cut intro block was prepended to final.mp4 (commit
a5eceb6). The diagnosis: the gate was mis-matching, not the render drifting.
`_position_offsets` was handed the finished file (which has the intro on the
front) together with the IN-MEMORY timeline, whose `start` values were measured
against a film with nothing on the front. Every line therefore appeared
`intro_offset` seconds late - a CONSTANT shift equal to the intro length, the
same number across head, middle and tail, which is the signature of a fixed
thing left uncounted, not of per-junction drift.

The fix: `_position_offsets(..., intro_offset=X)` centres its search on
`want + X`, so it measures drift about the position the render actually honours.

This test proves BOTH directions on synthetic audio - no TTS, no Whisper, no
20-minute render - so it is deterministic and runs in a couple of seconds:

  CORRECT  : build a `final` whose narration sits exactly where the (shifted)
             timeline says -> worst |delta| <= tolerance, gate SILENT.
  DRIFTED  : shift that same narration 2.0s later than the timeline says, the
             intro accounting held correct -> gate CATCHES ~2.0s.
  REGRESSION: run the OLD (no intro_offset) matching on a correct render that
             had an intro prepended -> it reports ~intro_offset of false drift,
             which is the bug this fixes. Asserted so the bug cannot return
             silently.

Usage:  python tools/test_render_position.py
Exit 0 = all pass.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from pipeline import render as _r  # noqa: E402

SR = 16000
FF = config.ffmpeg()


def _write_wav(path: Path, samples: np.ndarray) -> None:
    s16 = np.clip(samples, -1.0, 1.0)
    s16 = (s16 * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(s16.tobytes())


def _word_burst(seed: int, dur: float = 2.5) -> np.ndarray:
    """A short, distinctive energy envelope standing in for a line's TTS.

    Deterministic per seed, with amplitude modulation so the cross-correlation
    has real structure to lock onto (pure tone or white noise correlate poorly).
    """
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    carrier = np.sin(2 * np.pi * (180 + 40 * seed) * t)
    # three "syllable" bumps at seed-specific offsets
    env = np.zeros(n)
    for k in range(3):
        c = (0.3 + 0.6 * ((seed * 7 + k * 11) % 10) / 10.0) * dur
        env += np.exp(-((t - c) ** 2) / (2 * 0.12 ** 2))
    env += 0.05 * rng.standard_normal(n)
    return 0.6 * carrier * env


def _make_final(path: Path, placements: list[tuple[Path, float]],
                total: float) -> None:
    """Render an audio-only mp4 placing each wav at an absolute second offset.

    placements: [(wav_path, at_seconds)]. Built by summing into one buffer then
    muxing to an mp4 with a black video track, so `final` looks like a real
    render to the decode path (which reads -vn audio anyway).
    """
    buf = np.zeros(int(total * SR), dtype=np.float32)
    for wav, at in placements:
        x = np.frombuffer(
            Path(wav).read_bytes()[44:], dtype="<i2").astype(np.float32) / 32767.0
        i = int(at * SR)
        j = min(len(buf), i + len(x))
        buf[i:j] += x[: j - i]
    mix = path.with_suffix(".mix.wav")
    _write_wav(mix, buf)
    # mux with a black video so the file is an mp4 like a real final.mp4
    subprocess.run(
        [FF, "-v", "error", "-y",
         "-f", "lavfi", "-i", f"color=c=black:s=320x180:r=30:d={total:.3f}",
         "-i", str(mix),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(path)],
        check=True)
    mix.unlink()


def _case(tmp: Path):
    """Build three line wavs and the timeline slots they map to.

    Story layout (BEFORE any intro), slots measured from 0:
       line 10 @ 1.0s, line 20 @ 12.0s, line 30 @ 25.0s.
    An intro block of INTRO seconds is prepended, so in the finished file the
    lines really sit at 1.0+INTRO, 12.0+INTRO, 25.0+INTRO.
    """
    INTRO = 5.53  # the exact figure from the reported finding
    slots = [(10, 1.0), (20, 12.0), (30, 25.0)]
    narration = []
    wavs = {}
    for lid, _ in slots:
        w = tmp / f"line{lid}.wav"
        _write_wav(w, _word_burst(lid))
        wavs[lid] = w
        narration.append((lid, w, 2.5))
    timeline = [{"id": lid, "start": s, "end": s + 2.5} for lid, s in slots]
    total = 25.0 + INTRO + 6.0
    return INTRO, slots, narration, timeline, wavs, total


def main() -> int:
    tol = _r.POSITION_TOLERANCE
    fails = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        INTRO, slots, narration, timeline, wavs, total = _case(tmp)

        # ---- CORRECT render: lines placed at slot + INTRO ------------------
        correct = tmp / "final_correct.mp4"
        _make_final(correct,
                    [(wavs[lid], s + INTRO) for lid, s in slots], total)

        off = _r._position_offsets(FF, correct, timeline, narration,
                                   intro_offset=INTRO)
        if not off:
            fails.append("CORRECT: _position_offsets returned nothing "
                         "(numpy/ffmpeg?)")
        else:
            worst = max(abs(d) for *_x, d in off)
            detail = ", ".join(f"L{i} {d:+.2f}s" for i, _w, _m, d in off)
            print(f"CORRECT render  : worst |delta| {worst:.2f}s  ({detail})")
            if worst > tol:
                fails.append(f"CORRECT: gate should be SILENT but worst "
                             f"{worst:.2f}s > tol {tol:.2f}s")

        # ---- DRIFTED render: same lines 2.0s LATE than honoured ------------
        SHIFT = 2.0
        drifted = tmp / "final_drift.mp4"
        _make_final(drifted,
                    [(wavs[lid], s + INTRO + SHIFT) for lid, s in slots], total)

        off = _r._position_offsets(FF, drifted, timeline, narration,
                                   intro_offset=INTRO)
        if not off:
            fails.append("DRIFTED: _position_offsets returned nothing")
        else:
            worst = max(abs(d) for *_x, d in off)
            detail = ", ".join(f"L{i} {d:+.2f}s" for i, _w, _m, d in off)
            print(f"DRIFTED render  : worst |delta| {worst:.2f}s  ({detail})")
            if abs(worst - SHIFT) > 0.30:
                fails.append(f"DRIFTED: gate should catch ~{SHIFT:.1f}s but "
                             f"measured {worst:.2f}s")
            if worst <= tol:
                fails.append(f"DRIFTED: gate stayed SILENT ({worst:.2f}s "
                             f"<= tol {tol:.2f}s) - a real 2s drift would ship")

        # ---- REGRESSION: the OLD behaviour (intro_offset defaulting 0) on a
        #      correct-but-intro-prepended render must falsely report ~INTRO.
        #      This is the exact bug; asserting it reproduces guards the fix.
        off = _r._position_offsets(FF, correct, timeline, narration)  # no offset
        if off:
            worst = max(abs(d) for *_x, d in off)
            print(f"OLD matching    : worst |delta| {worst:.2f}s  "
                  f"(expected ~{INTRO:.2f}s false drift - the bug)")
            if abs(worst - INTRO) > 0.40:
                fails.append(f"REGRESSION: expected old path to show ~{INTRO}s "
                             f"of false drift, got {worst:.2f}s - the fixture no "
                             f"longer reproduces the bug it guards")

    print("-" * 60)
    if fails:
        for f in fails:
            print("FAIL:", f)
        return 1
    print("test_render_position: all pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
