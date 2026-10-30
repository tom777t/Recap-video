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
from pipeline import encoder as _encoder

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


# ---- what footage the intro block puts on screen --------------------------
# The intro block (montage + hook + film-intro) is built AFTER the story has
# been rendered, and none of its paths apply a censor filter. Each path records
# the source window it used here, as it uses it, so render.py's censor audit
# sees the intro's footage too instead of only the footage bound to lines.
# Recorded at the moment of choosing (not re-derived afterwards) so the audit
# cannot drift away from what was actually built.
_USED_FOOTAGE: list = []


def reset_footage() -> None:
    _USED_FOOTAGE.clear()


def record_footage(a: float, b: float, label: str,
                   out_a: float | None = None,
                   out_b: float | None = None) -> None:
    """Record a source span the intro puts on screen.

    `out_a`/`out_b` are where it lands on the INTRO BLOCK's own timeline. They
    matter: without them pipeline/motion_check._to_source cannot map a frozen
    stretch in the finished file back to the footage it came from, so every
    freeze inside the intro was reported as "could not be traced" and counted
    against the render. Four of them were, and the trace was the missing half
    of the finding.
    """
    try:
        rec = {"a": float(a), "b": float(b), "label": str(label)}
    except (TypeError, ValueError):
        return
    if out_a is not None and out_b is not None:
        try:
            rec["out_a"], rec["out_b"] = float(out_a), float(out_b)
        except (TypeError, ValueError):
            pass
    _USED_FOOTAGE.append(rec)


def used_footage() -> list:
    """Source windows the intro block showed, unblurred.

    Returns dicts shaped like pipeline.censor.UsedFootage items - with out_a /
    out_b where the builder knew them - so render.py can hand them straight to
    the censor audit and the freeze check.
    """
    out = []
    for r in _USED_FOOTAGE:
        if isinstance(r, dict):
            out.append(dict(r))
        else:                       # legacy 3-tuple
            a, b, label = r
            out.append({"a": a, "b": b, "label": label})
    return out


def extend_limit(project: str, frm: float, src_dur: float = 0.0) -> float:
    """How far past `frm` the montage may keep reading real footage.

    The montage pads a slot when its chosen moment is shorter than the slot.
    The main render's answer to "not enough footage" is MORE FOOTAGE, not a
    cloned frame, so the montage reads on past the moment's end - but only as
    far as it is allowed to go:
      * never to or past the first reveal landing (that is the spoiler rule
        the montage already obeys for its moment choice)
      * never into footage a flagged shot occupies (the montage applies no
        censor filter at all)
      * never into footage the STORY shows (that is repeated footage)
      * never past the source
    """
    import config as _cfg
    from pipeline import censor as _censor
    pdir = _cfg.project_dir(project)
    lim = float(src_dur) if src_dur else float("inf")
    land = first_reveal_land(project)
    if land and land > frm:
        lim = min(lim, land)
    _min_ov = float(getattr(_cfg, "FOOTAGE_REUSE_MIN_OVERLAP_SEC", 0.4))
    for f in _censor.flagged_shots(pdir):
        if f["b"] > frm and f["a"] >= frm:
            lim = min(lim, f["a"])
    for (ta, tb) in bound_windows(project):
        if tb > frm and ta >= frm - _min_ov:
            lim = min(lim, ta)
    return lim if lim != float("inf") else frm


def first_reveal_land(project: str) -> float:
    from pipeline.draft import parse_reveal_map
    r = parse_reveal_map(project)
    if not r:
        return float("inf")
    return min(x["land_sec"] for x in r)


def bound_windows(project: str) -> list:
    """Source windows the STORY already shows, as [(a, b)].

    The intro montage must not replay footage a line is bound to: the same shot
    appearing in the teaser and again in the body is the "repeated footage"
    defect, and it is the montage that should move, because it is the one with
    a free choice of material.
    """
    import json as _j
    from pipeline.draft import parse_ts
    pdir = config.project_dir(project)
    try:
        d = _j.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    out = []
    for ln in d.get("lines") or []:
        cs, ce = ln.get("clip_start"), ln.get("clip_end")
        if cs and ce:
            try:
                a, b = parse_ts(cs), parse_ts(ce)
            except Exception:
                continue
            hold = (ln.get("narration_silence_seconds")
                    or ln.get("film_speaks_seconds"))
            if hold:
                b = max(b, a + float(hold))
            out.append((a, b))
        for seg in (ln.get("montage") or []):
            if isinstance(seg, dict) and seg.get("clip_start"):
                try:
                    out.append((parse_ts(seg["clip_start"]),
                                parse_ts(seg["clip_end"])))
                except Exception:
                    pass
    return sorted(out)


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

    # The montage picks its own footage from the whole catalogue, so it must not
    # pick footage flagged for blur: _build_montage_clip applies no censor
    # filter, so a flagged shot cut into the montage played CLEAR in the opening
    # ten seconds of the video. There is always another shot to use.
    from pipeline import censor as _censor
    usable = _censor.avoid_windows(_censor.flagged_shots(pdir), usable,
                                   "the intro montage")
    if not usable:
        return []

    # ...and it must not replay footage the STORY already shows. The montage is
    # the element with free choice of material, so it is the one that moves.
    import config as _cfg
    _min_ov = float(getattr(_cfg, "FOOTAGE_REUSE_MIN_OVERLAP_SEC", 0.4))
    _taken = bound_windows(project)
    _free = [(a, b) for a, b in usable
             if not any(min(b, tb) - max(a, ta) > _min_ov
                        for ta, tb in _taken)]
    if len(_free) < len(usable):
        console.print(f"[dim]Intro montage: {len(usable) - len(_free)} "
                      f"catalogued moment(s) skipped - the story already "
                      f"shows them.[/]")
    if not _free:
        console.print(
            "[yellow]Intro montage:[/] every catalogued moment before the "
            "first reveal is already shown by the story, so a montage built "
            "from them would repeat footage. Catalogue more early shots, or "
            "accept no montage.")
        return []
    usable = _free
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


def _tts_line(project: str, ln: dict, out: Path) -> float:
    """Synthesize one opening line (hook or film-intro) through the PRODUCTION
    provider, so the intro block speaks in the same voice as the body.

    Uses the same provider-selection + caching as the main narration path
    (Inworld 'Warren' by default, Edge fallback). Returns the duration.
    """
    from pipeline.tts import _select_provider
    from pipeline.tts_providers import synthesize_cached
    provider, _is_fallback = _select_provider()
    tag = str(ln.get("delivery") or "normal")
    _was_cached, dur = synthesize_cached(
        provider, str(ln["narration"]), tag, out, out.parent)
    if dur <= 0:
        raise RuntimeError(f"intro line TTS produced no audio ({out.name})")
    return dur


def film_intro_lines(project: str) -> list[dict]:
    """The film-intro block lines, READ FROM THE DRAFT every time (like the
    hook). These carry film_intro: true and play after the montage+hook."""
    pdir = config.project_dir(project)
    df = pdir / "draft.json"
    if not df.exists():
        return []
    d = json.loads(df.read_text(encoding="utf-8-sig"))
    return [ln for ln in d.get("lines", [])
            if ln.get("film_intro") and str(ln.get("narration", "")).strip()]


def _build_film_intro_segment(project: str, work: Path,
                              out_offset: float = 0.0):
    """Render the film-intro lines as a video segment: the 3 lines spoken one
    after another over the film's own calm opening footage, with the music bed
    under them. Returns the segment Path, or None if there are no film-intro
    lines (then the opening is just montage+hook, as before).

    The visual is a slow pan over the first slice of source footage that ends
    BEFORE the first reveal lands (same spoiler rule as the montage). No frame
    is described by the narration, so any calm opening footage is safe.
    """
    lines = film_intro_lines(project)
    if not lines:
        return None
    pdir = config.project_dir(project)
    ff = config.ffmpeg()
    src = pdir / "source.mp4"
    if not src.exists():
        console.print("[yellow]Film-intro:[/] no source.mp4 - skipping the "
                      "intro-facts block.")
        return None

    # 1. synthesize each line (production voice, cached) and concat to one mp3
    parts = []
    for ln in lines:
        p = work / f"intro_fi_{ln['id']}.mp3"
        try:
            _tts_line(project, ln, p)
        except Exception as e:
            console.print(f"[yellow]Film-intro:[/] line {ln['id']} TTS failed "
                          f"({e}); skipping the intro-facts block.")
            return None
        parts.append(p)
    fi_mp3 = work / "intro_fi.mp3"
    _concat_audio(ff, parts, fi_mp3)
    fi_dur = _audio_dur(ff, fi_mp3)
    if fi_dur <= 0:
        return None

    # 2. pick an opening window that is CALM AND ACTUALLY VISIBLE.
    #
    # THE DEFECT: `vis_start` was hardcoded to 0.0, and the only thing that
    # could move it was a flagged shot. So this block played the film's own
    # distributor logo fades. Measured on the source, the first 32s contains
    # 4.50s of black (0.00-2.75 and 23.25-24.75), and that is exactly the
    # 3.00s + 1.50s of black that reached the screen at 16.75s and 40.00s of
    # the finished film - which MOTION-CHECK then reported as frozen, which it
    # was: a run of identical black frames is frozen.
    #
    # The old docstring said "no frame is described by the narration, so any
    # calm opening footage is safe". That is the error in one sentence: a logo
    # fade is calm AND black. The story half never hits this because every
    # story clip is bound to a tagged shot window; this block chooses its own
    # footage, so it has to look at it.
    land = first_reveal_land(project)
    vis_len = fi_dur + 0.4
    _hi = max(1.0, land - 1.0)
    if vis_len > _hi:
        vis_len = max(3.0, _hi)

    from pipeline import censor as _censor
    from pipeline import footage as _footage
    _flagged = _censor.flagged_shots(pdir)
    _avoid = [(float(f["a"]), float(f["b"])) for f in (_flagged or [])]
    # Search the film's opening stretch, not the whole film: this block is "the
    # film's opening" by design. Bounded so the scan stays a few seconds.
    _search_hi = min(_hi, 600.0)
    vis_start, _why = _footage.watchable_start(
        src, vis_len, 0.0, _search_hi, avoid=_avoid)
    if vis_start is None:
        console.print(f"[yellow]Film-intro:[/] {_why} - skipping the "
                      f"intro-facts block rather than opening the film on "
                      f"black or on flagged footage.")
        return None
    console.print(f"[cyan]Film-intro:[/] {_why}")
    # Assert the choice, rather than trusting the search: this is the one
    # number that produced the defect.
    _blk = _footage.has_black(src, vis_start, vis_start + vis_len)
    if _blk:
        console.print(f"[yellow]Film-intro:[/] the chosen window still "
                      f"contains black {_blk} - skipping the block.")
        return None

    w, h, fps = config.OUTPUT_WIDTH, config.OUTPUT_HEIGHT, config.OUTPUT_FPS
    # music bed under the voice, ducked; falls back to no bed if absent
    bed = None
    for cand in ("music/bed.mp3", "music.mp3"):
        if (pdir / cand).exists():
            bed = pdir / cand
            break
    duck = 10.0 ** (float(getattr(config, "MUSIC_DUCK_DB", -22.0)) / 20.0)

    # RECORD IT, with its position on the finished timeline. Without out_a/
    # out_b this block's footage was untraceable, so a freeze inside it could
    # only be REPORTED - motion_check could not map it back to the source span
    # and say whether the film itself was static there. Both reported freezes
    # were in this block.
    record_footage(vis_start, vis_start + vis_len, "film-intro block",
                   out_a=float(out_offset),
                   out_b=float(out_offset) + vis_len)

    out = work / "intro_filmblock.mp4"
    # SAME FRAMING AND SAME SCALER AS THE STORY.
    # This was orce_original_aspect_ratio=increase + crop, i.e. scale to
    # FILL and cut the sides off - so the film-intro block had no letterbox
    # while every other second of the film does, and a 1280x544 source was
    # blown up past 1080 and cropped. The story's clip builder uses
    # decrease + pad (letterbox), and pins the scaler to
    # config.VIDEO_SCALER; intro.py pinned it nowhere, so the whole opening was
    # resampled with ffmpeg's default bicubic while the story used lanczos.
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease:"
          f"flags={config.VIDEO_SCALER},"
          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps}")
    if bed is not None:
        cmd = [ff, "-y",
               "-ss", f"{vis_start:.3f}", "-t", f"{fi_dur+0.3:.3f}", "-i", str(src),
               "-i", str(fi_mp3),
               "-stream_loop", "-1", "-t", f"{fi_dur+0.3:.3f}", "-i", str(bed),
               "-filter_complex",
               f"[0:v]{vf}[v];"
               f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo[nar];"
               f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo,"
               f"volume={duck:.4f}[bed];"
               f"[bed][nar]amix=inputs=2:duration=first:normalize=0,"
               f"alimiter=limit=0.891[a]",
               "-map", "[v]", "-map", "[a]", "-t", f"{fi_dur+0.3:.3f}",
               *_encoder.video_args("final"), *_encoder.audio_args(),
               str(out)]
    else:
        console.print("[yellow]Film-intro:[/] no music bed found "
                      "(music/bed.mp3 or music.mp3); intro facts over footage "
                      "only.")
        cmd = [ff, "-y",
               "-ss", f"{vis_start:.3f}", "-t", f"{fi_dur+0.3:.3f}", "-i", str(src),
               "-i", str(fi_mp3),
               "-filter_complex",
               f"[0:v]{vf}[v];"
               f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo[a]",
               "-map", "[v]", "-map", "[a]", "-t", f"{fi_dur+0.3:.3f}",
               *_encoder.video_args("final"), *_encoder.audio_args(),
               str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        console.print("[yellow]Film-intro:[/] segment build failed; opening "
                      "will be montage+hook only.")
        console.print((r.stderr or "")[-400:])
        return None
    console.print(f"[green]Film-intro block:[/] {len(lines)} line(s), "
                  f"{fi_dur:.1f}s")
    return out


def _concat_audio(ff: str, parts: list, out: Path) -> None:
    """Join mp3s by RE-ENCODING (stream-copy concat doubles AAC duration)."""
    lst = out.parent / f"_{out.stem}_list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts),
                   encoding="utf-8")
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:a", "libmp3lame", "-b:a", "192k", str(out)],
                   capture_output=True, text=True)


def _audio_dur(ff: str, p: Path) -> float:
    r = subprocess.run(
        [config.ffprobe(), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


def prepend_to_final(project: str, final: Path) -> float:
    """Put the intro block in front of the finished film.

    Returns the intro's DURATION in seconds, or 0.0 if nothing was prepended.
    The caller needs that number: every position in timeline.json was measured
    against a film that did not yet have an intro on the front, and captions
    and every downstream timing gate read those positions.

    The two halves are concatenated AFTER each has been mixed, rather than the
    montage being spliced into the main timeline before the music pass. That
    keeps each half's audio treatment intact: the intro has its own track at
    full level ducking under the hook, the story has its mood bed. Mixing them
    in one pass would put the story's bed under the montage.

    Uses the concat DEMUXER, which requires identical codec parameters - both
    files come from this module's own encoder with the same canvas, fps and
    codecs, so that holds. It is also stream-copy, so a 20-minute film is not
    re-encoded to glue 14 seconds onto the front.
    """
    pdir = config.project_dir(project)
    work = pdir / "_work"
    work.mkdir(exist_ok=True)
    block = build_intro(project, out_name="_work/intro_block.mp4",
                        max_total=40.0)
    if block is None:
        return 0.0
    ff = config.ffmpeg()

    def _dur(p):
        _pr = subprocess.run(
            [config.ffprobe(), "-v", "error", "-show_entries",
             "format=duration", "-of", "default=nw=1:nk=1", str(p)],
            capture_output=True, text=True)
        try:
            return float((_pr.stdout or "0").strip())
        except ValueError:
            return 0.0

    # The film-intro block (channel greeting + title/year/director + leads + a
    # fact) is a SECOND segment, after the montage+hook, before the story. It
    # was gated by [FILM-INTRO] but never rendered - build_intro baked only the
    # hook - so a shipped film opened on the montage and cut straight into the
    # story with the greeting silently dropped. Synthesize those lines now and
    # lay them over the film's own calm opening footage.
    # The montage is built first, so its measured length is the film-intro
    # block's offset on the finished timeline.
    _block_dur_for_offset = _dur(block)
    fi_block = _build_film_intro_segment(project, work,
                                         out_offset=_block_dur_for_offset)

    block_dur = _dur(block)
    fi_dur = _dur(fi_block) if fi_block else 0.0

    lst = work / "concat_intro.txt"
    tmp = work / "final_with_intro.mp4"
    _parts = [block] + ([fi_block] if fi_block else []) + [final]
    lst.write_text("".join("file '%s'\n" % Path(p).as_posix()
                           for p in _parts),
                   encoding="utf-8")
    # Video is stream-copied - a 20-minute film must not be re-encoded to glue
    # 14 seconds onto the front. AUDIO IS RE-ENCODED, and that is not
    # optional: with `-c copy` on both, the concat demuxer produced a file
    # whose video stream was a correct 39.63s (1188 packets at 30fps) and
    # whose AUDIO stream was 79.35s - exactly double. AAC priming and the two
    # halves' timestamps do not survive a stream-copy concat, and the result
    # is a film that drifts further out of sync the longer it plays. Measured,
    # not guessed: ffprobe the two streams separately, because the container
    # header reports only one of them and looked fine.
    cmd = [ff, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-ac", "2", str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True)

    # DID THE JOIN ACTUALLY WORK? A non-zero exit is the easy case. The
    # dangerous case is exit 0 with a broken file: the concat demuxer will
    # stream-copy video happily and then stop writing packets when the
    # segments' parameters stop matching, while the re-encoded audio runs to
    # full length. The result is a file whose container duration looks correct
    # (it reports the LONGER stream) and whose picture ends early. An earlier
    # version of this function shipped the mirror-image bug - video 39.63s,
    # audio 79.35s - and its fix was to re-encode the audio, with no check
    # that the output was then correct. So: measure both streams and require
    # them to agree with each other and with the sum of the parts.
    from pipeline import probe as _probe
    _want = block_dur + fi_dur + _dur(final)
    _join_bad = []
    if r.returncode == 0 and tmp.exists():
        _join_bad = _probe.verify(tmp, expect_dur=_want)
        if _join_bad:
            console.print("[yellow]Intro join:[/] the stream-copy produced a "
                          "file that does not measure correctly:")
            for _b in _join_bad:
                console.print(f"[yellow]    {_b['msg']}[/]")
    if r.returncode != 0 or not tmp.exists() or _join_bad:
        # The demuxer needs byte-identical stream parameters and the segments
        # do not always have them - the story half goes through the music mix
        # and loudnorm, the intro segments do not. Fall back to the concat
        # FILTER, which re-encodes and therefore always works. The cost is real:
        # it re-encodes the WHOLE film to put the opening on the front, worth it
        # only because the alternative is shipping a film with no opening.
        console.print("[yellow]Intro join:[/] stream-copy refused or "
                      "mis-measured; re-encoding to concatenate. Slower on a "
                      "long film.")
        _n = len(_parts)
        _ins = []
        for p in _parts:
            _ins += ["-i", str(p)]
        _cat = "".join(f"[{i}:v][{i}:a]" for i in range(_n))
        cmd = [ff, "-y", *_ins, "-filter_complex",
               f"{_cat}concat=n={_n}:v=1:a=1[v][a]",
               "-map", "[v]", "-map", "[a]",
               *_encoder.video_args("final"), *_encoder.audio_args(),
               str(tmp)]
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not tmp.exists():
        console.print("[yellow]Intro block built but could not be joined to "
                      "the film; leaving final.mp4 without it.[/]")
        console.print((r.stderr or "")[-500:])
        return 0.0
    # The re-encode path gets measured too. If BOTH joins produce a broken
    # file, that is a stop - not a thing to paste onto final.mp4 and hope.
    _bad2 = _probe.verify(tmp, expect_dur=_want)
    if _bad2:
        console.print("[red]Intro join:[/] the joined file is still wrong "
                      "after re-encoding:")
        for _b in _bad2:
            console.print(f"[red]    {_b['msg']}[/]")
        console.print("[red]  Refusing to overwrite final.mp4 with it.[/]")
        raise RuntimeError("intro join produced a malformed file")
    tmp.replace(final)
    total_intro = block_dur + fi_dur
    _fi_note = (f" + film-intro {fi_dur:.1f}s" if fi_dur else
                " (no film-intro lines in draft)")
    console.print(f"[green]Intro block prepended:[/] final.mp4 now opens on the "
                  f"montage ({block_dur:.1f}s){_fi_note} = {total_intro:.1f}s")
    return total_intro


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
    hook_dur = _tts_line(project, hook, hook_mp3)
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
    _src_dur = 0.0
    try:
        import subprocess as _sp
        _r = _sp.run([config.ffprobe(), "-v", "error", "-show_entries",
                      "format=duration", "-of", "default=nw=1:nk=1",
                      str(config.project_dir(project) / "source.mp4")],
                     capture_output=True, text=True)
        _src_dur = float((_r.stdout or "0").strip())
    except Exception:
        _src_dur = 0.0

    inputs, parts, labels = [], [], []
    _cursor = 0.0           # where this slot lands on the intro's own timeline
    _slot_durs = []
    for i, (a, b) in enumerate(slots):
        dur = b - a
        ms, me = moments[i % len(moments)]
        # EXTEND, DO NOT PAD. `_read` used to be min(moment length, slot+0.4),
        # so a moment SHORTER than its slot left tpad cloning the difference
        # with no ceiling - four frozen stretches of 0.93-1.83s in the finished
        # intro, every one of them a still frame. The main render's answer to
        # "not enough footage" is more footage, so read on past the moment's
        # end, as far as extend_limit() allows.
        want = dur + 0.4
        avail_end = min(max(me, ms + want), extend_limit(project, ms, _src_dur))
        _read = max(0.1, avail_end - ms)
        if _read + 1e-6 < dur:
            # Still short even after extending: SHORTEN THE SLOT rather than
            # freeze into it. A montage cut that is a tenth of a second quicker
            # is invisible; a frozen frame is not.
            dur = _read
        _slot_durs.append(dur)
        # No censor filter is applied anywhere in this graph - record the exact
        # window that reaches the screen, WITH its position on the intro
        # timeline, so the render's censor audit and freeze trace can use it.
        record_footage(ms, ms + _read, f"intro montage slot {i+1}",
                       out_a=_cursor, out_b=_cursor + dur)
        _cursor += dur
        inputs += ["-ss", f"{ms:.3f}", "-t", f"{_read:.3f}",
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
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease:"
            f"flags={config.VIDEO_SCALER},"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps}{motion},"
            # CAPPED, like every tpad in render.py. This is a backstop only -
            # the extension above is what should make it unnecessary - but an
            # uncapped clone is how a still frame got into the first 50
            # seconds of the video, so the ceiling is enforced here too.
            f"tpad=stop_mode=clone:stop_duration="
            f"{min(dur, float(config.MAX_FREEZE_SEC)):.3f},"
            f"trim=duration={dur:.3f},setpts=PTS-STARTPTS[v{i}]")
        labels.append(f"[v{i}]")
    # The slots may have been SHORTENED to avoid freezing (see the loop
    # above), so the video is as long as the slots really are - not as long as
    # the beat cuts suggested. The audio has to be trimmed to the same number
    # or the block ends on a hanging music tail.
    vid_total = sum(_slot_durs) if _slot_durs else total
    if abs(vid_total - total) > 0.05:
        console.print(f"[dim]Intro montage: {vid_total:.2f}s of real footage "
                      f"(beat cuts implied {total:.2f}s) - slots were "
                      f"shortened rather than padded with a frozen frame.[/]")
    total = vid_total

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
           *_encoder.video_args("final"), *_encoder.audio_args(), str(out)]
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
