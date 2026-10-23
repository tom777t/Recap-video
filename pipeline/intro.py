# -*- coding: utf-8 -*-
"""intro.py - 2g: a beat-cut music montage before the recap starts.

    projects/<name>/intro_music.mp3   ->  intro_preview.mp4

Shape of the thing:
  - the music plays from zero at full level;
  - the picture cuts on the music's own beats;
  - at the DROP the <hook> line enters and the music ducks under it;
  - every frame used comes from BEFORE the first reveal lands.

That last rule is the one with teeth. A montage is the most spoiler-prone part
of a recap: it is the one place where pictures are chosen for being striking
rather than for where they sit in the story, and the most striking frames in
any film are the ones after the twist. `[INTRO-MONTAGE]` fails the build if a
single chosen clip touches the first reveal's land time.

The hook line is READ FROM THE DRAFT at build time, never baked in - the draft
gets rewritten and the montage has to follow it.

Missing `intro_music.mp3` is not an error. It prints a notice and skips.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

from rich.console import Console

import config

console = Console()

SR = 22050            # mono rate for onset analysis
HOP = 512             # ~23ms frames
MIN_CUT_SEC = 0.55    # no shot shorter than this, however dense the beats
MIN_SHOT_SEC = 1.2    # a catalogued moment must be at least this long to use


# ---------------------------------------------------------------- audio ----
def _decode_mono(path: Path) -> "object":
    """Decode to mono float32 at SR using ffmpeg. Returns a numpy array."""
    import numpy as np
    cmd = [config.ffmpeg(), "-v", "error", "-i", str(path),
           "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    out = subprocess.run(cmd, capture_output=True)
    if out.returncode != 0 or not out.stdout:
        raise RuntimeError(f"could not decode {path.name}")
    return np.frombuffer(out.stdout, dtype="<f4")


def _flux(x) -> "object":
    """Spectral flux onset envelope, one value per HOP."""
    import numpy as np
    n = 1024
    frames = 1 + max(0, (len(x) - n) // HOP)
    win = np.hanning(n).astype("float32")
    prev = None
    env = np.zeros(frames, dtype="float32")
    for i in range(frames):
        seg = x[i * HOP: i * HOP + n]
        if len(seg) < n:
            break
        mag = np.abs(np.fft.rfft(seg * win))
        if prev is not None:
            d = mag - prev
            env[i] = float(np.sum(d[d > 0]))     # half-wave rectified
        prev = mag
    return env


def detect_beats(path: Path, max_sec: float = 60.0) -> list:
    """Onset times in seconds, at least MIN_CUT_SEC apart.

    Peak-picked against a LOCAL median rather than a global threshold: music
    that gets louder would otherwise put every detected beat in the loud half.
    """
    import numpy as np
    x = _decode_mono(path)
    x = x[: int(max_sec * SR)]
    env = _flux(x)
    if env.size < 8:
        return []
    # local median baseline over ~1.5s, plus a fraction of the local spread
    w = max(3, int(1.5 * SR / HOP))
    pad = np.pad(env, (w, w), mode="edge")
    base = np.array([np.median(pad[i: i + 2 * w + 1]) for i in range(len(env))])
    spread = np.array([np.std(pad[i: i + 2 * w + 1]) for i in range(len(env))])
    thr = base + 0.6 * spread
    cand = [i for i in range(1, len(env) - 1)
            if env[i] > thr[i] and env[i] >= env[i - 1] and env[i] > env[i + 1]]
    times, last = [], -1e9
    for i in cand:
        t = i * HOP / SR
        if t - last >= MIN_CUT_SEC:
            times.append(round(t, 3))
            last = t
    return times


def detect_drop(path: Path, max_sec: float = 60.0) -> float:
    """The biggest sustained energy rise - where the hook should enter.

    Measured as the largest (mean energy of the next 2s) minus (mean energy of
    the previous 2s). That is deliberately about SUSTAINED level, not a single
    transient: a drum hit is a beat, a drop is the moment the track changes
    gear and stays there.
    """
    import numpy as np
    x = _decode_mono(path)
    x = x[: int(max_sec * SR)]
    fr = max(1, int(0.05 * SR))                    # 50ms energy frames
    n = len(x) // fr
    e = np.array([float(np.sqrt(np.mean(x[i * fr:(i + 1) * fr] ** 2) + 1e-12))
                  for i in range(n)])
    k = int(2.0 / 0.05)                            # 2 second window
    best_i, best_d = -1, -1.0
    for i in range(k, n - k):
        d = float(np.mean(e[i:i + k]) - np.mean(e[i - k:i]))
        if d > best_d:
            best_d, best_i = d, i
    if best_i < 0:
        return 0.0
    return round(best_i * 0.05, 3)


# ---------------------------------------------------------------- shots ----
def _pt(ts) -> float:
    p = [float(v) for v in str(ts).split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def first_reveal_land(project: str) -> float:
    from pipeline.draft import parse_reveal_map
    r = parse_reveal_map(project)
    if not r:
        return float("inf")
    return min(x["land_sec"] for x in r)


def pick_moments(project: str, limit_sec: float, n: int) -> list:
    """`n` catalogued moments spread across [0, limit_sec), none touching it.

    Spread rather than "best", because there is no measure of best here and
    picking by eye is what puts the twist in the montage.
    """
    pdir = config.project_dir(project)
    src = None
    for cand in ("shots.json", "shots_machine.json"):
        if (pdir / cand).exists():
            src = pdir / cand
            break
    if src is None:
        return []
    shots = json.loads(src.read_text(encoding="utf-8-sig"))["shots"]
    usable = []
    for s in shots:
        try:
            a, b = _pt(s["clip_start"]), _pt(s["clip_end"])
        except Exception:
            continue
        if b - a < MIN_SHOT_SEC:
            continue
        if b > limit_sec:            # strictly before the land, end included
            continue
        usable.append((a, b))
    if not usable:
        return []
    usable.sort()
    out, used = [], set()
    for i in range(n):
        target = (limit_sec * (i + 0.5)) / n
        best = min((u for u in usable if u not in used),
                   key=lambda u: abs(u[0] - target), default=None)
        if best is None:
            break
        used.add(best)
        out.append(best)
    out.sort()
    return out


# ----------------------------------------------------------------- gate ----
class IntroSpoiler(Exception):
    pass


def hook_line(project: str) -> dict | None:
    """The <hook> line, READ FROM THE DRAFT every time.

    Never cached or baked in: the draft is rewritten whenever the writing loop
    runs, and a montage that still opens on the previous draft's hook is the
    kind of staleness nothing downstream would catch.
    """
    pdir = config.project_dir(project)
    df = pdir / "draft.json"
    if not df.exists():
        return None
    d = json.loads(df.read_text(encoding="utf-8-sig"))
    for ln in d.get("lines", []):
        if ln.get("delivery") == "hook" and str(ln.get("narration", "")).strip():
            return ln
    return None


def _tts_hook(project: str, ln: dict, out: Path) -> float:
    """Synthesize the hook with its own delivery preset. Returns duration."""
    import asyncio
    import edge_tts
    from pipeline.tts import _delivery_for, _audio_duration
    d = _delivery_for(ln, config.DEFAULT_TTS_RATE)

    async def go():
        await edge_tts.Communicate(
            str(ln["narration"]), voice=config.DEFAULT_TTS_VOICE,
            rate=d["rate"], pitch=d["pitch"], volume=d["volume"]).save(str(out))
    last = None
    for _ in range(4):
        try:
            asyncio.run(go())
            if out.exists() and out.stat().st_size > 0:
                return _audio_duration(out)
        except Exception as e:                            # transient edge-tts
            last = e
    raise RuntimeError(f"hook TTS failed: {last}")


def build_intro(project: str, out_name: str = "intro_preview.mp4",
                max_total: float = 30.0) -> Path | None:
    """Build the beat-cut intro montage + hook. None if there is no music."""
    pdir = config.project_dir(project)
    music = None
    for ext in (".mp3", ".m4a", ".wav", ".ogg"):
        p = pdir / f"intro_music{ext}"
        if p.exists():
            music = p
            break
    if music is None:
        console.print(
            f"[yellow]Intro montage:[/] no intro_music.(mp3|m4a|wav|ogg) in "
            f"{pdir.name}/ - skipping. This is a notice, not an error: a film "
            f"with no intro track simply opens on its hook.")
        return None

    ff = config.ffmpeg()
    land = first_reveal_land(project)
    beats = detect_beats(music, max_total + 5)
    drop = detect_drop(music, max_total + 5)
    hook = hook_line(project)
    if hook is None:
        console.print("[red]Intro montage:[/] the draft has no <hook> line "
                      "with narration. Nothing to enter on the drop.")
        return None

    work = pdir / "_work"
    work.mkdir(exist_ok=True)
    hook_mp3 = work / "intro_hook.mp3"
    hook_dur = _tts_hook(project, hook, hook_mp3)
    total = min(max_total, drop + hook_dur + 0.8)

    # cut points: the music's own beats, bounded to `total`
    cuts = [0.0] + [b for b in beats if 0.2 < b < total - 0.3] + [total]
    slots = [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)
             if cuts[i + 1] - cuts[i] >= 0.25]
    moments = pick_moments(project, land, len(slots))
    if not moments:
        console.print("[red]Intro montage:[/] no catalogued moment ends before "
                      f"the first reveal lands ({land:.0f}s).")
        return None
    gate_moments(moments, land)      # raises IntroSpoiler

    console.print(
        f"[cyan]Intro montage:[/] {music.name}, drop at {drop:.2f}s, "
        f"{len(slots)} beat cuts over {total:.1f}s, hook enters on the drop "
        f"({hook_dur:.1f}s of narration)")
    console.print(f"[dim]  every clip ends before the first reveal at "
                  f"{land:.0f}s - latest used is "
                  f"{max(b for _, b in moments):.0f}s[/]")

    w, h, fps = config.OUTPUT_WIDTH, config.OUTPUT_HEIGHT, config.OUTPUT_FPS
    inputs, parts, labels = [], [], []
    for i, (a, b) in enumerate(slots):
        dur = b - a
        ms, me = moments[i % len(moments)]
        # read a touch more than needed so tpad never has to clone
        inputs += ["-ss", f"{ms:.3f}", "-t", f"{min(me - ms, dur + 0.4):.3f}",
                   "-i", str(config.project_dir(project) / 'source.mp4')]
        z = config.MOTION_ZOOM if config.MOTION_ENABLE else 0.0
        motion = ""
        if z > 0:
            tf = max(1, int(round(dur * fps)))
            ze = (f"min(zoom+{z/tf:.6f},{1.0+z:.4f})" if i % 2 == 0
                  else f"if(eq(on,0),{1.0+z:.4f},max(zoom-{z/tf:.6f},1.0))")
            motion = (f",zoompan=z='{ze}':d=1:x='iw/2-(iw/zoom/2)':"
                      f"y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}")
        parts.append(
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps}{motion},"
            f"tpad=stop_mode=clone:stop_duration={dur:.3f},"
            f"trim=duration={dur:.3f},setpts=PTS-STARTPTS[v{i}]")
        labels.append(f"[v{i}]")
    nm, nh = len(slots), len(slots) + 1
    inputs += ["-i", str(music), "-i", str(hook_mp3)]

    duck = 10.0 ** (float(getattr(config, "MUSIC_DUCK_DB", -22.0)) / 20.0)
    # full level until the drop, ducked under the hook from the drop on
    vexpr = (f"volume='if(lt(t,{drop:.3f}),1,{duck:.4f})':eval=frame")
    graph = (
        ";".join(parts) + ";" + "".join(labels) +
        f"concat=n={len(slots)}:v=1:a=0[v];"
        f"[{nm}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
        f"atrim=duration={total:.3f},{vexpr},"
        f"afade=t=out:st={max(0.0, total-0.6):.3f}:d=0.6[mus];"
        f"[{nh}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
        f"adelay={int(drop*1000)}:all=1,apad=whole_dur={total:.3f}[nar];"
        f"[mus][nar]amix=inputs=2:duration=first:dropout_transition=0:"
        f"normalize=0,alimiter=limit=0.891:level=disabled[a]"
    )
    out = pdir / out_name
    cmd = [ff, "-y", *inputs, "-filter_complex", graph,
           "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
           "-c:v", "libx264", "-preset", config.VIDEO_PRESET,
           "-crf", str(config.VIDEO_CRF), "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        console.print("[red]Intro montage: ffmpeg failed[/]")
        console.print((r.stderr or "")[-1200:])
        raise RuntimeError("intro build failed")
    console.print(f"[green]Intro preview written:[/] {out}")
    return out


def gate_moments(moments: list, land: float) -> None:
    """[INTRO-MONTAGE]: nothing in the montage may touch the first land."""
    bad = [(a, b) for a, b in moments if b > land or a >= land]
    if bad:
        raise IntroSpoiler(
            "[INTRO-MONTAGE] %d montage clip(s) sit at or after the first "
            "reveal's land (%.0fs): %s. The montage is the most spoiler-prone "
            "part of a recap - it picks frames for being striking, and the "
            "most striking frames in any film are the ones after the twist."
            % (len(bad), land,
               ", ".join(f"{a:.0f}-{b:.0f}s" for a, b in bad[:5])))
