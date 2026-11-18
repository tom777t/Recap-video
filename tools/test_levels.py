# -*- coding: utf-8 -*-
"""test_levels.py - every film and music level is set against the NARRATOR.

Owner, 18 Nov: the film's own dialogue is still too quiet, the music bed is
too thin, the ending track is weak. Measured on the shipped Furious 7
render: narration -24.7 LUFS; the two film_speaks windows -34.7 and -40.2
LUFS on the source and played at "0 dB, full level", so 10 and 15.5 dB under
the narrator; the stem at -17 dB put most action clips 27-42 dB under the
voice; music normalised to -23 LUFS, -22 dB, then a sidechain duck on top.
See pipeline/levels.py.

  VOICE-REF           the reference is the median loudness of the project's
                      narration files, cached; no files -> the fallback, said
  SPEAKS-AT-VOICE     a REAL hold clip built with film_speaks from a source
                      whose dialogue sits 15 dB under the narrator comes out
                      at the narrator's loudness (it used to stay 15 dB under)
  UNDER-PER-WINDOW    by default the stem keeps its fixed gains (owner, 18
                      Nov: it sounds right); with FILM_AUDIO_LEVEL_TO_VOICE
                      on, a loud window lands at FILM_AUDIO_DB under the
                      voice and a quiet one is raised at most
                      FILM_AUDIO_GAIN_MAX_DB
  SILENT-OR-UNREAD    a silent window or an unreadable file keeps the level as
                      written - nothing is dragged up out of the noise floor
  MUSIC-TO-VOICE      by default music is normalised to the fixed -23 LUFS
                      (owner: the bed and the ending sound right); with
                      MUSIC_NORMALIZE_TO_VOICE on, to the narrator
  BED-AS-BEFORE       the final mix ducks the bed exactly as before
  HOLD-LIMITED        a lifted hold / film_speaks clip runs through a limiter
  CACHE-KEY           a different narrator reference changes the clip cache key
                      (otherwise every cached clip keeps its old film level)

Run:  python tools/test_levels.py      (exit 0 = all pass)
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
from pipeline import levels as LV  # noqa: E402


def _ff(*args):
    subprocess.run([config.ffmpeg(), "-v", "error", "-y", *args], check=True)


def _tone(path: Path, amp: float, dur: float = 6.0, freq: int = 440):
    _ff("-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}",
        "-af", f"volume={amp}", "-ac", "2", "-ar", "48000", str(path))


def _noise_film(path: Path, segs: list):
    """A film with a picture and an audio track built from (seconds, amp)
    pieces of pink noise, so a window's loudness is known in advance."""
    parts, labels = [], []
    for i, (d, a) in enumerate(segs):
        parts.append(f"anoisesrc=color=pink:amplitude={a}:duration={d}:"
                     f"seed={i + 1},aformat=sample_rates=48000:"
                     f"channel_layouts=stereo[a{i}]")
        labels.append(f"[a{i}]")
    tot = sum(d for d, _ in segs)
    g = ";".join(parts) + ";" + "".join(labels) + \
        f"concat=n={len(segs)}:v=0:a=1[a]"
    _ff("-f", "lavfi", "-i", f"color=c=gray:s=320x180:d={tot}:r=25",
        "-filter_complex", g, "-map", "0:v", "-map", "[a]", "-t", str(tot),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-b:a", "192k", str(path))


def _pdir_with_narration(tmp: Path, amps: list) -> Path:
    pdir = tmp / "proj"
    (pdir / "narration").mkdir(parents=True)
    for i, a in enumerate(amps):
        _tone(pdir / "narration" / f"line_{i + 1:03d}.wav", a, 4.0,
              300 + 40 * i)
    (pdir / "narration" / "_cache.json").write_text("{}", encoding="utf-8")
    return pdir


def t_voice_ref():
    tmp = Path(tempfile.mkdtemp(prefix="lv_"))
    try:
        pdir = _pdir_with_narration(tmp, [0.3, 0.7, 0.7, 0.7, 1.4])
        mid = LV.measure(pdir / "narration" / "line_002.wav")
        cache = tmp / "levels.json"
        v1, h1 = LV.voice_ref(pdir, cache)
        calls = {"n": 0}
        real = LV.measure

        def counting(*a, **k):
            calls["n"] += 1
            return real(*a, **k)
        LV.measure = counting
        try:
            v2, h2 = LV.voice_ref(pdir, cache)
        finally:
            LV.measure = real
        empty = tmp / "empty"
        empty.mkdir()
        v3, h3 = LV.voice_ref(empty)
        ok = (abs(v1 - mid) < 0.6 and v2 == v1 and calls["n"] == 0
              and h2.startswith("cached")
              and v3 == float(config.VOICE_REF_FALLBACK_LUFS)
              and "assumed" in h3)
        return ok, (f"median {v1:.1f} LUFS (the middle file measures "
                    f"{mid:.1f}; the loud and quiet outliers do not move it), "
                    f"cached on the second call; no narration -> {v3} "
                    f"assumed, said" if ok else
                    f"{v1} vs {mid}, {v2}/{h2} calls {calls['n']}, {v3}/{h3}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_speaks_at_voice():
    from pipeline import render as R
    tmp = Path(tempfile.mkdtemp(prefix="lv_"))
    try:
        pdir = _pdir_with_narration(tmp, [0.7] * 3)
        src = tmp / "source.mp4"
        # 4 s loud, then 8 s of 'dialogue' about 15 dB quieter
        _noise_film(src, [(4.0, 0.3), (8.0, 0.05)])
        v, _h = LV.begin(pdir)
        before = LV.measure(src, 5.0, 6.0)
        out = tmp / "fs.mp4"
        saved = config.MOTION_ENABLE
        config.MOTION_ENABLE = False
        try:
            R._build_silence_clip(config.ffmpeg(), src, 5.0, 11.0, out, 6.0,
                                  0, 0.0, "none", None, 0.0, film_audio=True,
                                  film_speaks=True, film_src=None,
                                  src_wh=(320, 180))
        finally:
            config.MOTION_ENABLE = saved
        got = LV.measure(out)
        ok = (got is not None and before is not None
              and v - before > 8.0 and abs(got - v) < 1.5)
        return ok, (f"dialogue {before:.1f} LUFS on the source "
                    f"({v - before:.1f} dB under the {v:.1f} LUFS narrator) "
                    f"-> {got:.1f} LUFS in the clip" if ok else
                    f"voice {v}, source {before}, clip {got}")
    finally:
        LV.end()
        shutil.rmtree(tmp, ignore_errors=True)


def t_under_per_window():
    tmp = Path(tempfile.mkdtemp(prefix="lv_"))
    try:
        pdir = _pdir_with_narration(tmp, [0.7] * 3)
        stem = tmp / "no_vocals.wav"
        _ff("-f", "lavfi", "-i",
            "anoisesrc=color=pink:amplitude=0.5:duration=6:seed=3",
            "-f", "lavfi", "-i",
            "anoisesrc=color=pink:amplitude=0.01:duration=6:seed=4",
            "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1,"
            "aformat=sample_rates=48000:channel_layouts=stereo",
            str(stem))
        v, _ = LV.begin(pdir)
        d_under, _ = LV.under_gain(stem, 0.5, 5.0)
        d_hold, _ = LV.hold_gain(stem, 0.5, 5.0)
        if (d_under, d_hold) != (float(config.FILM_AUDIO_DB),
                                 float(config.FILM_AUDIO_HOLD_DB)):
            return False, (f"default changed the stem's fixed gains: "
                           f"{d_under}/{d_hold}")
        saved = config.FILM_AUDIO_LEVEL_TO_VOICE
        config.FILM_AUDIO_LEVEL_TO_VOICE = True
        try:
            g_loud, m_loud = LV.under_gain(stem, 0.5, 5.0)
            g_quiet, m_quiet = LV.under_gain(stem, 6.5, 5.0)
        finally:
            config.FILM_AUDIO_LEVEL_TO_VOICE = saved
        want = float(config.FILM_AUDIO_DB)
        cap = float(config.FILM_AUDIO_GAIN_MAX_DB)
        ok = (abs((m_loud + g_loud) - (v + want)) < 0.2
              and g_quiet == cap and m_quiet + g_quiet < v + want)
        return ok, (f"default: fixed {d_under:+.0f}/{d_hold:+.0f} dB (owner, "
                    f"18 Nov); switched on: loud window {m_loud:.1f} LUFS -> "
                    f"{g_loud:+.1f} dB, "
                    f"at {want:+.0f} under the voice; quiet window "
                    f"{m_quiet:.1f} -> capped at {g_quiet:+.1f} dB" if ok
                    else f"voice {v}: loud {m_loud}/{g_loud}, quiet "
                    f"{m_quiet}/{g_quiet}")
    finally:
        LV.end()
        shutil.rmtree(tmp, ignore_errors=True)


def t_silent_or_unread():
    tmp = Path(tempfile.mkdtemp(prefix="lv_"))
    try:
        sil = tmp / "sil.wav"
        _ff("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "5",
            str(sil))
        junk = tmp / "junk.wav"
        junk.write_bytes(b"x" * 64)
        g1, _ = LV.under_gain(sil, 0.0, 4.0)
        g2, m2 = LV.speaks_gain(junk, 0.0, 4.0)
        g3, _ = LV.under_gain(tmp / "missing.wav", 0.0, 4.0)
        ok = (g1 == float(config.FILM_AUDIO_DB) and m2 is None
              and g2 == float(config.FILM_SPEAKS_DB)
              and g3 == float(config.FILM_AUDIO_DB))
        return ok, ("silence and an unreadable/missing file keep the written "
                    "level" if ok else f"{g1} {g2}/{m2} {g3}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_music_to_voice():
    from pipeline import music as M
    tmp = Path(tempfile.mkdtemp(prefix="lv_"))
    try:
        pdir = _pdir_with_narration(tmp, [0.7] * 3)
        (pdir / "music").mkdir()
        bed = pdir / "music" / "bed.wav"
        _tone(bed, 4.0, 8.0, 220)                 # louder than the voice
        v, _ = LV.begin(pdir)
        fixed = LV.measure(M.normalized(config.ffmpeg(), pdir, bed))
        saved = config.MUSIC_NORMALIZE_TO_VOICE
        config.MUSIC_NORMALIZE_TO_VOICE = True
        try:
            got = LV.measure(M.normalized(config.ffmpeg(), pdir, bed))
        finally:
            config.MUSIC_NORMALIZE_TO_VOICE = saved
        want = float(config.MUSIC_NORMALIZE_LUFS)
        ok = (fixed is not None and abs(fixed - want) < 0.6
              and got is not None and abs(got - v) < 0.6)
        return ok, (f"default: bed at {fixed:.1f} LUFS (the fixed "
                    f"{want:.0f}, owner 18 Nov); switched on: {got:.1f} = the "
                    f"narrator ({v:.1f})" if ok else
                    f"default {fixed} vs {want}; on {got} vs {v}")
    finally:
        LV.end()
        shutil.rmtree(tmp, ignore_errors=True)


def t_no_double_duck():
    from pipeline import render as R
    cap: dict = {}
    orig = R._run
    R._run = lambda cmd, desc: cap.update(cmd=list(cmd))
    tmp = Path(tempfile.mkdtemp(prefix="lv_"))
    try:
        av, mus = tmp / "av.mp4", tmp / "m.wav"
        for p in (av, mus):
            p.write_bytes(b"x" * 64)
        R._render_with_music(config.ffmpeg(), av, mus, None, 30.0,
                             tmp / "final.mp4", silence_windows=[(5, 9)])
        g = cap["cmd"][cap["cmd"].index("-filter_complex") + 1]
        ok = (("sidechaincompress" in g) == bool(config.MUSIC_DUCK)
              and config.MUSIC_DUCK_DB == -22.0)
        return ok, (f"bed at {config.MUSIC_DUCK_DB:+.0f} dB, sidechain "
                    f"{'on' if config.MUSIC_DUCK else 'off'} - as it was "
                    f"(owner, 18 Nov: the bed sounds right)" if ok else
                    f"sidechain in graph={('sidechaincompress' in g)}, "
                    f"MUSIC_DUCK={config.MUSIC_DUCK}, "
                    f"MUSIC_DUCK_DB={config.MUSIC_DUCK_DB}")
    finally:
        R._run = orig
        shutil.rmtree(tmp, ignore_errors=True)


def t_hold_limited():
    from pipeline import render as R
    cap: dict = {}
    orig = R._run
    R._run = lambda cmd, desc: cap.update(cmd=list(cmd))
    tmp = Path(tempfile.mkdtemp(prefix="lv_"))
    try:
        src, stem = tmp / "s.mp4", tmp / "no_vocals.wav"
        for p in (src, stem):
            p.write_bytes(b"x" * 64)
        bad = []
        for fs in (False, True):
            R._build_silence_clip(config.ffmpeg(), src, 10.0, 20.0,
                                  tmp / "o.mp4", 4.0, 0, 0.0, "none", None,
                                  0.0, film_audio=True, film_speaks=fs,
                                  film_src=stem, src_wh=(320, 180))
            g = cap["cmd"][cap["cmd"].index("-filter_complex") + 1]
            if "alimiter" not in g:
                bad.append("film_speaks" if fs else "hold")
        return not bad, ("hold and film_speaks clips are limited after the "
                         "lift" if not bad else f"no limiter: {bad}")
    finally:
        R._run = orig
        shutil.rmtree(tmp, ignore_errors=True)


def t_cache_key():
    from pipeline import render as R
    tmp = Path(tempfile.mkdtemp(prefix="lv_"))
    try:
        a = tmp / "n.mp3"
        a.write_bytes(b"x" * 64)
        args = (Path("s.mp4"), 5.0, 18.0, 0.0, 1, 0.0, 8.0, a)
        LV._CTX.update(voice=-24.7)
        k1 = R._clip_signature(*args, film_audio=True)
        LV._CTX.update(voice=-20.0)
        k2 = R._clip_signature(*args, film_audio=True)
        ok = k1 != k2
        return ok, ("the narrator reference is in the clip cache key" if ok
                    else "a new reference reuses clips built at the old one")
    finally:
        LV.end()
        shutil.rmtree(tmp, ignore_errors=True)


TESTS = [("VOICE-REF", t_voice_ref), ("SPEAKS-AT-VOICE", t_speaks_at_voice),
         ("UNDER-PER-WINDOW", t_under_per_window),
         ("SILENT-OR-UNREAD", t_silent_or_unread),
         ("MUSIC-TO-VOICE", t_music_to_voice),
         ("BED-AS-BEFORE", t_no_double_duck),
         ("HOLD-LIMITED", t_hold_limited), ("CACHE-KEY", t_cache_key)]

if __name__ == "__main__":
    if not shutil.which(config.ffmpeg()) and not Path(config.ffmpeg()).exists():
        print("FAIL  ffmpeg not found - NOT RUN (not a pass)")
        sys.exit(1)
    fails = 0
    for name, fn in TESTS:
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:17s} {msg}")
    print("-" * 60)
    print("test_levels: all pass" if not fails
          else f"test_levels: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
