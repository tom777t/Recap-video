# -*- coding: utf-8 -*-
"""levels.py - every level in the mix is set against the NARRATOR.

THE DEFECT (owner, 18 Nov: "phần thoại gốc tiếng vẫn hơi nhỏ", "nhạc nền
quá mỏng", "nhạc kết yếu"). Measured on the shipped Furious 7 render:

  narration files            -24.7 LUFS (median of 15)
  film_speaks L193, source   -34.7 LUFS   -> 10.0 dB under the narrator
  film_speaks L194, source   -40.2 LUFS   -> 15.5 dB under the narrator
  same units in final.mp4    -21.4 / -28.7 LUFS against -15.5 around them
  no-vocals stem, per clip   -35 .. -50 dB RMS in most action clips, then
                             -17 dB on top -> 27-42 dB under the voice
  music                      normalised to -23 LUFS, -22 dB, then a ratio-8
                             sidechain on top -> roughly 22-29 dB under the
                             voice, pumping on every syllable

Every gain was a fixed number of dB applied to a source whose own level is
arbitrary. A film's dialogue sits wherever its mixer put it (-35 and -40
LUFS here, an explosion at -13 dB RMS three clips later), so "0 dB, full
level" meant 10-15 dB under the narrator, and "-17 dB under narration" meant
anything from audible to nothing at all. The music had the same problem in a
milder form, plus two ducks stacked on each other.

The rule now: a level in config is "dB relative to the narrator", and this
module turns it into the gain that achieves it for THIS source window.

  voice_ref()     the narrator's loudness - median integrated LUFS of the
                  project's narration files, cached
  window_lufs()   integrated LUFS of one window of a file, cached
  film_gain()     the gain that puts a film window at (narrator + rel_db),
                  clamped, so a near-silent window is not dragged up into
                  separation noise and a blast is not left at full level

Nothing here changes WHERE the film or the music plays; render.py and
music.py still decide that. This only decides how loud.
"""
from __future__ import annotations

import json
import re
import statistics
import subprocess
from pathlib import Path

import config

VERSION = 1
_I = re.compile(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS")
_CTX: dict = {"voice": None, "how": "", "cache": None}


def _fallback() -> float:
    return float(getattr(config, "VOICE_REF_FALLBACK_LUFS", -24.7))


def measure(path: Path, start: float | None = None,
            dur: float | None = None) -> float | None:
    """Integrated LUFS of a file or of one window of it; None when ffmpeg
    gives no reading (unreadable file, window under one gating block)."""
    if dur is not None and float(dur) < 0.4:
        return None
    cmd = [config.ffmpeg(), "-hide_banner", "-nostats"]
    if start is not None:
        cmd += ["-ss", f"{max(0.0, float(start)):.3f}"]
    if dur is not None:
        cmd += ["-t", f"{float(dur):.3f}"]
    cmd += ["-i", str(path), "-vn", "-af", "ebur128", "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    got = _I.findall(r.stderr or "")
    return float(got[-1]) if got else None


def _load(cache: Path | None) -> dict:
    if cache is None:
        return {}
    try:
        return json.loads(Path(cache).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(cache: Path | None, store: dict) -> None:
    if cache is None:
        return
    try:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        Path(cache).write_text(json.dumps(store, indent=1), encoding="utf-8")
    except OSError:
        pass


def narration_files(pdir: Path) -> list:
    nd = Path(pdir) / "narration"
    if not nd.is_dir():
        return []
    return sorted(p for p in nd.iterdir()
                  if p.suffix.lower() in (".mp3", ".wav", ".m4a")
                  and not p.name.startswith("_"))


def voice_ref(pdir: Path, cache: Path | None = None,
              sample: int = 24) -> tuple:
    """(LUFS, how). The median integrated loudness of up to `sample` narration
    files spread evenly through the film. The median, because one shouted or
    whispered line must not move the reference for the whole mix."""
    files = narration_files(pdir)
    if not files:
        return _fallback(), (f"no narration files - assumed "
                             f"{_fallback():.1f} LUFS")
    sig = f"{len(files)}:{sum(p.stat().st_size for p in files)}"
    store = _load(cache)
    hit = store.get("voice")
    if isinstance(hit, dict) and hit.get("sig") == sig:
        return float(hit["lufs"]), f"cached ({hit.get('n')} files)"
    step = max(1, len(files) // sample)
    vals = [v for v in (measure(p) for p in files[::step][:sample])
            if v is not None and v > -70.0]
    if not vals:
        return _fallback(), (f"narration unmeasurable - assumed "
                             f"{_fallback():.1f} LUFS")
    ref = round(statistics.median(vals), 2)
    store["voice"] = {"sig": sig, "lufs": ref, "n": len(vals)}
    _save(cache, store)
    return ref, f"measured on {len(vals)} narration file(s)"


def begin(pdir: Path) -> tuple:
    """Set the reference for one render. Returns (voice LUFS, how)."""
    cache = Path(pdir) / "_cache" / "levels.json"
    v, how = voice_ref(pdir, cache)
    _CTX.update(voice=v, how=how, cache=cache)
    return v, how


def end() -> None:
    _CTX.update(voice=None, how="", cache=None)


def voice() -> float:
    v = _CTX.get("voice")
    return float(v) if v is not None else _fallback()


def window_lufs(path: Path, start: float, dur: float) -> float | None:
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        return None
    key = f"{p.name}|{st.st_size}|{float(start):.2f}|{float(dur):.2f}"
    cache = _CTX.get("cache")
    store = _load(cache)
    win = store.get("win") or {}
    if key in win:
        return win[key]
    v = measure(p, start, dur)
    if cache is not None and v is not None:
        win[key] = v
        store["win"] = win
        _save(cache, store)
    return v


def film_gain(path: Path, start: float, dur: float, rel_db: float,
              lo: float, hi: float) -> tuple:
    """(gain dB, measured LUFS or None) putting this window of the film at
    narrator + rel_db.

    Unmeasurable (no file, no reading) -> rel_db as written, which is what
    the gain used to be. A window quieter than FILM_LEVEL_SILENT_LUFS has
    nothing in it worth hearing - raising it would only raise separation
    noise - so it also keeps rel_db."""
    m = window_lufs(path, start, dur)
    if m is None or m <= float(getattr(config, "FILM_LEVEL_SILENT_LUFS",
                                       -60.0)):
        return float(rel_db), m
    g = voice() + float(rel_db) - float(m)
    return round(min(float(hi), max(float(lo), g)), 2), m


def under_gain(path, start, dur) -> tuple:
    return film_gain(path, start, dur, config.FILM_AUDIO_DB,
                     config.FILM_AUDIO_GAIN_MIN_DB,
                     config.FILM_AUDIO_GAIN_MAX_DB)


def hold_gain(path, start, dur) -> tuple:
    return film_gain(path, start, dur, config.FILM_AUDIO_HOLD_DB,
                     config.FILM_AUDIO_GAIN_MIN_DB,
                     config.FILM_AUDIO_GAIN_MAX_DB)


def speaks_gain(path, start, dur) -> tuple:
    return film_gain(path, start, dur, config.FILM_SPEAKS_DB,
                     config.FILM_SPEAKS_GAIN_MIN_DB,
                     config.FILM_SPEAKS_GAIN_MAX_DB)


def music_target() -> float:
    """The loudness every music file is normalised to before its gains. At
    the narrator's level, so MUSIC_DUCK_DB / MUSIC_CUE_DUCK_DB /
    MUSIC_ENDING_DB read as dB under the voice."""
    if getattr(config, "MUSIC_NORMALIZE_TO_VOICE", True):
        return voice()
    return float(getattr(config, "MUSIC_NORMALIZE_LUFS", -23.0))


def signature() -> str:
    """Everything that changes a film gain, for the clip cache key."""
    return (f"lv{VERSION}:{voice():.2f}:{float(config.FILM_AUDIO_DB):.2f}:"
            f"{float(config.FILM_AUDIO_HOLD_DB):.2f}:"
            f"{float(config.FILM_SPEAKS_DB):.2f}:"
            f"{float(config.FILM_AUDIO_GAIN_MIN_DB):.1f}:"
            f"{float(config.FILM_AUDIO_GAIN_MAX_DB):.1f}:"
            f"{float(config.FILM_SPEAKS_GAIN_MIN_DB):.1f}:"
            f"{float(config.FILM_SPEAKS_GAIN_MAX_DB):.1f}:"
            f"{float(getattr(config, 'FILM_LEVEL_SILENT_LUFS', -60.0)):.1f}")
