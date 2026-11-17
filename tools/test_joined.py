# -*- coding: utf-8 -*-
"""test_joined.py - a joined line's picture follows its voice.

  INTACT             parts drive the picture only while the narration still
                     IS its pieces
  WORD-SHARE         without alignment, piece i starts at its share of the
                     words
  ALIGNED-CACHED     with an aligner, offsets come from the audio and are
                     cached; the second call reads the cache, no aligner run
  ALIGN-FAILS-SAFE   an aligner that raises, or places a piece past the end
                     of the audio, falls back to the word share and says why
  SHARES             piece 0 holds through the lead-in until the voice
                     reaches piece 1; a piece spoken longer than its footage,
                     or on screen under 1 s, refuses (the render keeps the
                     even split)
  SIGNATURE          a segment's screen time is part of the clip cache key
  PICTURE-SWITCH     a real ffmpeg build: the picture changes from piece 1's
                     footage (red) to piece 2's (green) when the voice
                     reaches piece 2 (3.0 s), not at the even split (4.1 s)

Run:  python tools/test_joined.py      (exit 0 = all pass)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline import joined as J  # noqa: E402

LN = {"narration": "So they turn her into the ball in a game of keep-away, "
                   "passing her from car to car while Dom goes after Shaw.",
      "parts": [
          {"slot": "S041", "clip_start": "00:00:05.000",
           "clip_end": "00:00:10.000",
           "text": "So they turn her into the ball in a game of keep-away,"},
          {"slot": "S042", "clip_start": "00:00:10.000",
           "clip_end": "00:00:18.000",
           "text": "passing her from car to car while Dom goes after Shaw."}]}


def t_intact():
    stale = dict(LN, narration="They play keep-away with Ramsey.")
    ok = J.intact(LN) and not J.intact(stale) and not J.intact(
        {"narration": "x", "parts": LN["parts"][:1]})
    return ok, ("intact while the narration is its pieces; stale or one "
                "piece -> no" if ok else "intact() wrong")


def t_word_share():
    o = J.word_share_offsets(LN, 8.0)
    # 13 words ("keep-away" is two), then 11: piece 2 at 8.0 x 13/24
    ok = o[0] == 0.0 and abs(o[1] - 8.0 * 13 / 24) < 0.01
    return ok, (f"offsets {o}" if ok else f"got {o}")


def _audio(tmp: Path) -> Path:
    a = tmp / "n.mp3"
    a.write_bytes(b"x" * 64)
    return a


def t_aligned_cached():
    tmp = Path(tempfile.mkdtemp())
    n = {"calls": 0}

    def aligner(audio, text):
        n["calls"] += 1
        words = text.split()
        return [[w, round(i * 0.3, 3), round(i * 0.3 + 0.25, 3)]
                for i, w in enumerate(words)]
    try:
        a, c = _audio(tmp), tmp / "_cache" / "joined_offsets.json"
        o1, h1 = J.piece_offsets(LN, a, 8.0, cache=c, aligner=aligner)
        o2, h2 = J.piece_offsets(LN, a, 8.0, cache=c, aligner=aligner)
        ok = (h1 == "aligned" and h2 == "cached" and n["calls"] == 1
              and o1 == o2 and abs(o1[1] - 12 * 0.3) < 0.01)
        return ok, (f"piece 2 at {o1[1]}s (word 13 x 0.3s), cached on the "
                    f"second call" if ok else f"{h1}/{h2} {o1} calls "
                    f"{n['calls']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_align_fails_safe():
    tmp = Path(tempfile.mkdtemp())
    try:
        a = _audio(tmp)

        def boom(audio, text):
            raise RuntimeError("no faster-whisper model")

        def backwards(audio, text):
            # every word 'heard' past the end of the audio
            ws = text.split()
            return [[w, 9.0 + i * 0.1, 9.05 + i * 0.1]
                    for i, w in enumerate(ws)]
        o1, h1 = J.piece_offsets(LN, a, 8.0, aligner=boom)
        o2, h2 = J.piece_offsets(LN, a, 8.0, aligner=backwards)
        ws = J.word_share_offsets(LN, 8.0)
        ok = (h1.startswith("word-share (no faster-whisper") and o1 == ws
              and h2.startswith("word-share") and o2 == ws)
        return ok, ("aligner raises / past the audio -> word share, reason "
                    "kept" if ok else f"{h1} {o1}; {h2} {o2}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_shares():
    sh, why = J.shares(0.5, [0.0, 2.5], 8.2, [(5, 10), (10, 18)])
    long_, w2 = J.shares(0.5, [0.0, 2.5], 12.0, [(5, 10), (10, 15)])
    short, w3 = J.shares(0.5, [0.0, 0.2], 8.2, [(5, 10), (10, 18)])
    ok = (sh == [3.0, 5.2] and not why and long_ is None
          and "footage is 5.0s" in w2 and short is None and "under" in w3)
    return ok, (f"shares {sh}; over-long piece and a flash refused" if ok
                else f"{sh} {why}; {long_} {w2}; {short} {w3}")


def t_signature():
    from pipeline import render as R
    tmp = Path(tempfile.mkdtemp())
    try:
        a = _audio(tmp)
        args = (Path("s.mp4"), 5.0, 18.0, 0.0, 1, 0.0, 8.0, a)

        def sig(seg):
            return R._clip_signature(*args, split_segments=seg)
        s_even = sig([(5.0, 10.0), (10.0, 18.0)])
        s_j1 = sig([(5.0, 10.0, 3.0), (10.0, 18.0, 5.2)])
        s_j2 = sig([(5.0, 10.0, 4.1), (10.0, 18.0, 4.1)])
        ok = len({s_even, s_j1, s_j2}) == 3
        return ok, ("screen time per segment is in the cache key" if ok
                    else "two different splits share a cache key")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _rgb_at(clip: Path, t: float) -> tuple:
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i",
                        str(clip), "-frames:v", "1", "-vf", "scale=1:1",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True)
    b = r.stdout[:3]
    return tuple(b) if len(b) == 3 else (0, 0, 0)


def t_picture_switch():
    if not shutil.which("ffmpeg"):
        return False, "ffmpeg not found - NOT RUN (not a pass)"
    from pipeline import render as R
    tmp = Path(tempfile.mkdtemp(prefix="joined_"))
    try:
        src, aud = tmp / "src.mp4", tmp / "n.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y",
             "-f", "lavfi", "-i", "color=c=red:s=320x180:d=10:r=25",
             "-f", "lavfi", "-i", "color=c=lime:s=320x180:d=10:r=25",
             "-f", "lavfi", "-i", "color=c=blue:s=320x180:d=10:r=25",
             "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
             "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
             "-map", "[v]", "-map", "3:a", "-t", "30",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
             str(src)], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "sine=f=440:d=7.5", str(aud)], check=True)
        lead, narr = 0.5, 7.5
        clen = lead + narr + float(R.GAP)
        sh, why = J.shares(lead, [0.0, 2.5], clen, [(5.0, 10.0),
                                                     (10.0, 18.0)])
        if not sh:
            return False, f"shares refused: {why}"
        out = tmp / "clip.mp4"
        saved = config.MOTION_ENABLE
        config.MOTION_ENABLE = False
        try:
            R._build_clip(config.ffmpeg(), src, 5.0, 18.0, aud, narr, out, 1,
                          0.0, 0.0, "none", None, 0.0, lead_in=lead,
                          film_audio=False,
                          split_segments=[(5.0, 10.0, sh[0]),
                                          (10.0, 18.0, sh[1])],
                          src_wh=(320, 180))
        finally:
            config.MOTION_ENABLE = saved
        before, after = _rgb_at(out, 2.6), _rgb_at(out, 3.5)
        is_red = before[0] > 150 and before[1] < 100
        is_green = after[1] > 150 and after[0] < 100
        ok = is_red and is_green
        return ok, (f"red at 2.6s, green at 3.5s: the switch is at the "
                    f"voice (3.0s), not the even split ({clen / 2:.1f}s)"
                    if ok else f"rgb at 2.6s {before}, at 3.5s {after}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


TESTS = [("INTACT", t_intact), ("WORD-SHARE", t_word_share),
         ("ALIGNED-CACHED", t_aligned_cached),
         ("ALIGN-FAILS-SAFE", t_align_fails_safe), ("SHARES", t_shares),
         ("SIGNATURE", t_signature), ("PICTURE-SWITCH", t_picture_switch)]

if __name__ == "__main__":
    fails = 0
    for name, fn in TESTS:
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:16s} {msg}")
    print("-" * 60)
    print("test_joined: all pass" if not fails
          else f"test_joined: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
