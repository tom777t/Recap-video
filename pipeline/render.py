

"""
Render step: turn draft.json + narration audio into final.mp4.

Review-phim style upgrades:
  - each clip carries its own narration baked in (perfect A/V sync)
  - clips are chained with xfade dissolves (smooth transitions, no hard cuts)
  - narration speed handled upstream by Edge-TTS rate
  - a continuous background music bed is looped/trimmed, lowered, optionally
    ducked under the voice, faded out at the end, and mixed in
  - captions are timed on the real (xfade-overlapped) timeline

Per line:
  1. cut source clip [clip_start, clip_end]
  2. scale/pad to canvas, fps, time-fit to (narration + small gap)
  3. bake the line's narration onto that clip as its audio
Then:
  4. xfade + acrossfade the clips into one continuous A/V stream
  5. build .ass captions on the overlapped timeline
  6. burn captions, mix music, encode -> final.mp4
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from rich.console import Console

import config
from pipeline import srt as srtmod
from pipeline.draft import parse_ts

console = Console()

XFADE = config.XFADE_DURATION
GAP = config.GAP_BETWEEN_LINES


def _run(cmd: list[str], desc: str):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        console.print(f"[red]ffmpeg failed during: {desc}[/]")
        console.print(proc.stderr[-2500:])
        sys.exit(1)
    return proc


def _audio_dur(ff_probe: str, path: Path) -> float:
    out = subprocess.run(
        [ff_probe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def _censor_boxblur(censor: str) -> int:
    """Map a censor level to an ffmpeg boxblur radius (0 = no blur)."""
    return {
        "none": 0, "blur_light": 15, "blur": 30, "blur_heavy": 60,
    }.get(str(censor or "none"), 0)


def _build_clip(ff: str, source: Path, start: float, end: float,
                narr_audio: Path, narr_dur: float, out: Path, idx: int = 0,
                crop_top: float = 0.0, hold: float = 0.0,
                censor: str = "none", censor_region=None, exposure: float = 0.0):
    """
    Cut from `start`, normalise to canvas, fit to clip_len WITHOUT slowing
    footage:
      - if the source segment is longer than needed -> just trim (-t)
      - if shorter -> extend the cut end / hold last frame via tpad
    Add a subtle Ken Burns zoom (direction alternates per clip) so nothing
    sits still. Bake the narration audio (padded) as the clip's audio.

    `hold` (seconds): play the clip for AT LEAST this long even if the narration
    is shorter. The extra time has NO voiceover (the narration audio is padded
    with silence) so the action breathes under the music bed. Used for big
    action beats (breach, attack, explosion).
    `crop_top` (0..1) crops that fraction off the TOP first.

    Mức 1 binding constraint: the footage window [start, end] (shot_dur) must be
    able to carry the narration. If the narration is LONGER than the window we
    slow the footage down (setpts) up to BINDING_SLOWDOWN_MAX; beyond that we
    RAISE BindingViolation instead of silently cloning the last frame (freeze).
    """
    from pipeline.schemas import BindingViolation, BINDING_SLOWDOWN_MAX
    clip_len = max(narr_dur + GAP, hold)
    w, h, fps = config.OUTPUT_WIDTH, config.OUTPUT_HEIGHT, config.OUTPUT_FPS
    nf = config.NARRATION_FADE

    # ---- Mức 1: fit footage to narration via trim or mild slow-motion -------
    # shot_dur = real footage available in [start, end]. clip_len = how long the
    # clip must play (driven by narration + gap, or an intentional `hold`).
    shot_dur = max(0.0, float(end) - float(start))
    setpts_factor = 1.0           # >1.0 = slow down footage to fill the window
    if shot_dur > 0:
        # only the NARRATION-driven need triggers the contract; an intentional
        # `hold` (action breathing) is allowed to clone frames as before.
        narr_need = narr_dur + GAP
        if narr_need > shot_dur:
            capacity = shot_dur * BINDING_SLOWDOWN_MAX
            if narr_need <= capacity:
                # mild slow-motion: stretch shot_dur up to narr_need
                setpts_factor = narr_need / shot_dur
            else:
                raise BindingViolation(
                    line_id=idx, narration_dur=narr_need,
                    shot_dur=shot_dur, capacity=capacity)

    # optional top crop (hide overlaid text); kept as a capability for future
    # films, though the sharks project no longer needs it.
    crop = ""
    if crop_top and 0.0 < crop_top < 0.5:
        crop = f"crop=iw:ih*{1.0-crop_top:.3f}:0:ih*{crop_top:.3f},"

    # Mức 1 mild slow-motion: stretch the footage (setpts) to fill the window
    # BEFORE the fps resample, so motion stays smooth instead of freezing.
    # Applied only when narration overruns the shot window (setpts_factor > 1).
    slowmo = ""
    if setpts_factor > 1.0001:
        slowmo = f"setpts={setpts_factor:.5f}*PTS,"

    # DARK-scene exposure lift: brighten shadows on flagged dim shots so content
    # stays readable (Joker B35 lesson). `exposure` (0..~0.4) raises brightness +
    # gamma; a touch of saturation keeps the lifted image from looking grey.
    # Applied to the PICTURE (before scale/pad) so the black letterbox bars are
    # never lifted. exposure=0 -> no filter (identical to before).
    expo = ""
    if exposure and exposure > 0.001:
        e = min(0.5, float(exposure))
        expo = f"eq=brightness={e*0.6:.3f}:gamma={1.0+e:.3f}:saturation={1.0+e*0.5:.3f},"

    base = (
        f"{crop}{slowmo}{expo}"
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps}"
    )

    # Ken Burns via zoompan. Alternate zoom-in / zoom-out per clip.
    if config.MOTION_ENABLE and config.MOTION_ZOOM > 0:
        total_frames = max(1, int(round(clip_len * fps)))
        z = config.MOTION_ZOOM
        if idx % 2 == 0:
            # zoom in: 1.0 -> 1+z
            zexpr = f"min(zoom+{z/total_frames:.6f},{1.0+z:.4f})"
        else:
            # zoom out: start zoomed, ease back to 1.0
            zexpr = f"if(eq(on,0),{1.0+z:.4f},max(zoom-{z/total_frames:.6f},1.0))"
        motion = (
            f",zoompan=z='{zexpr}':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={w}x{h}:fps={fps}"
        )
    else:
        motion = ""

    # Censor (Phase A/B = whole frame; Phase C = optional partial region).
    # Each clip is already cut to exactly its [start, end] window, so the whole
    # clip is the censored segment. The original source.mp4 is never modified.
    # See S7 (whole-frame) / S8 (partial region) in TAGGING_GUIDE.md.
    cb = _censor_boxblur(censor)
    censor_f = ""           # inline whole-frame blur appended to the main vf chain
    partial_graph = ""      # extra graph for region blur; consumes [v0] -> [v]
    if cb > 0 and censor_region is None:
        # WHOLE-FRAME blur: blur the entire span inline (Phase A/B behaviour).
        censor_f = f",boxblur={cb}:enable='between(t,0,{clip_len:.3f})'"

    # tpad clones the last frame if the segment is shorter than clip_len,
    # then trim to exact length. This avoids any slow-motion.
    vf = (
        f"{base}{motion},"
        f"tpad=stop_mode=clone:stop_duration={clip_len:.3f},"
        f"trim=duration={clip_len:.3f},setpts=PTS-STARTPTS{censor_f}"
    )

    if cb > 0 and censor_region is not None:
        # PARTIAL blur (Phase C): split the processed frame, crop the region,
        # boxblur just that rectangle, and overlay it back. Coordinates are in
        # OUTPUT-canvas pixels (the frame has already been scaled/padded to
        # OUTPUT_WIDTHxHEIGHT by `base`). The region is clamped to the canvas.
        rx = max(0, min(int(censor_region.x), w - 1))
        ry = max(0, min(int(censor_region.y), h - 1))
        rw = max(1, min(int(censor_region.width), w - rx))
        rh = max(1, min(int(censor_region.height), h - ry))
        partial_graph = (
            f";[v0]split[base][region];"
            f"[region]crop={rw}:{rh}:{rx}:{ry},boxblur={cb}[blurred];"
            f"[base][blurred]overlay={rx}:{ry}[v]"
        )
        v_label = "[v0]"
    else:
        v_label = "[v]"

    af = (
        f"afade=t=in:st=0:d={nf},"
        f"afade=t=out:st={max(0.0, narr_dur - nf):.3f}:d={nf},"
        f"apad=whole_dur={clip_len:.3f},"
        f"aformat=sample_rates=48000:channel_layouts=stereo"
    )
    # When slowing down, bound the SOURCE read to exactly the [start, end]
    # window so setpts stretches the intended footage (not frames past `end`).
    src_in = ["-ss", f"{start:.3f}"]
    if setpts_factor > 1.0001 and shot_dur > 0:
        src_in += ["-t", f"{shot_dur:.3f}"]
    src_in += ["-i", str(source)]
    cmd = [
        ff, "-y",
        *src_in,
        "-i", str(narr_audio),
        "-filter_complex", f"[0:v]{vf}{v_label};[1:a]{af}[a]{partial_graph}",
        "-map", "[v]", "-map", "[a]",
        "-t", f"{clip_len:.3f}",
        "-c:v", "libx264", "-preset", "veryfast",
        "-crf", str(config.VIDEO_CRF), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        str(out),
    ]
    _run(cmd, f"build clip {out.name}")
    return clip_len


def _build_silence_clip(ff: str, source: Path, start: float, end: float,
                        out: Path, silence_dur: float, idx: int = 0,
                        crop_top: float = 0.0,
                        censor: str = "none", censor_region=None,
                        exposure: float = 0.0):
    """
    Gap 3: a SILENCE shot - visual holds for `silence_dur` seconds with NO
    narration (a silent audio track is baked so the downstream xfade/music mix
    stays uniform). Music swells during this window (handled at mix time).
    Mirrors `_build_clip`'s canvas/motion/censor/exposure so the look matches.
    """
    clip_len = float(silence_dur)
    w, h, fps = config.OUTPUT_WIDTH, config.OUTPUT_HEIGHT, config.OUTPUT_FPS

    crop = ""
    if crop_top and 0.0 < crop_top < 0.5:
        crop = f"crop=iw:ih*{1.0-crop_top:.3f}:0:ih*{crop_top:.3f},"
    expo = ""
    if exposure and exposure > 0.001:
        e = min(0.5, float(exposure))
        expo = f"eq=brightness={e*0.6:.3f}:gamma={1.0+e:.3f}:saturation={1.0+e*0.5:.3f},"
    base = (
        f"{crop}{expo}"
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps}"
    )

    if config.MOTION_ENABLE and config.MOTION_ZOOM > 0:
        total_frames = max(1, int(round(clip_len * fps)))
        z = config.MOTION_ZOOM
        if idx % 2 == 0:
            zexpr = f"min(zoom+{z/total_frames:.6f},{1.0+z:.4f})"
        else:
            zexpr = f"if(eq(on,0),{1.0+z:.4f},max(zoom-{z/total_frames:.6f},1.0))"
        motion = (
            f",zoompan=z='{zexpr}':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={w}x{h}:fps={fps}"
        )
    else:
        motion = ""

    cb = _censor_boxblur(censor)
    censor_f = ""
    partial_graph = ""
    if cb > 0 and censor_region is None:
        censor_f = f",boxblur={cb}:enable='between(t,0,{clip_len:.3f})'"

    vf = (
        f"{base}{motion},"
        f"tpad=stop_mode=clone:stop_duration={clip_len:.3f},"
        f"trim=duration={clip_len:.3f},setpts=PTS-STARTPTS{censor_f}"
    )

    if cb > 0 and censor_region is not None:
        rx = max(0, min(int(censor_region.x), w - 1))
        ry = max(0, min(int(censor_region.y), h - 1))
        rw = max(1, min(int(censor_region.width), w - rx))
        rh = max(1, min(int(censor_region.height), h - ry))
        partial_graph = (
            f";[v0]split[base][region];"
            f"[region]crop={rw}:{rh}:{rx}:{ry},boxblur={cb}[blurred];"
            f"[base][blurred]overlay={rx}:{ry}[v]"
        )
        v_label = "[v0]"
    else:
        v_label = "[v]"

    # Silent stereo 48k audio for exactly clip_len (anullsrc input, trimmed by -t).
    cmd = [
        ff, "-y",
        "-ss", f"{start:.3f}", "-i", str(source),
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-filter_complex", f"[0:v]{vf}{v_label}{partial_graph}",
        "-map", "[v]", "-map", "1:a",
        "-t", f"{clip_len:.3f}",
        "-c:v", "libx264", "-preset", "veryfast",
        "-crf", str(config.VIDEO_CRF), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        str(out),
    ]
    _run(cmd, f"build silence clip {out.name}")
    return clip_len


def _build_montage_clip(ff: str, source: Path, segments: list[tuple[float, float]],
                        narr_audio: Path, narr_dur: float, out: Path,
                        hold: float = 0.0, play_durs: list | None = None):
    """
    A 'montage hold': cut through several ACTION sub-shots in one line. The
    narration plays at the start; the rest of the clip is silent action under
    the music. Each sub-shot is filled with MOTION (not a static held frame) —
    keeps attention during long silent action beats.
    `segments`: list of (start, end) source windows.

    Mức 2 `play_durs` (optional): a per-segment list of seconds. When given, each
    shot plays for its OWN duration (None entries fall back to an equal share of
    the LEFTOVER time), and the total clip length is
        max(narration + GAP, sum(play_durs), hold).
    When `play_durs` is None, the legacy behaviour applies: the total length is
    max(narration + GAP, hold) split EQUALLY across the sub-shots.
    """
    w, h, fps = config.OUTPUT_WIDTH, config.OUTPUT_HEIGHT, config.OUTPUT_FPS
    nf = config.NARRATION_FADE
    k = max(1, len(segments))

    if play_durs is not None:
        # Mức 2: explicit per-shot durations. Fill in any None with an equal
        # share of whatever time the narration needs beyond the declared sum.
        declared = [float(p) if p is not None else None for p in play_durs]
        sum_declared = sum(p for p in declared if p is not None)
        n_unset = sum(1 for p in declared if p is None)
        clip_len = max(narr_dur + GAP, sum_declared, hold)
        if n_unset:
            leftover = max(0.0, clip_len - sum_declared)
            share = leftover / n_unset
            seg_durs = [p if p is not None else share for p in declared]
        else:
            seg_durs = list(declared)
            # if narration/hold needs MORE than the declared sum, stretch the
            # LAST shot to absorb the remainder so total == clip_len.
            extra = clip_len - sum_declared
            if extra > 0.001 and seg_durs:
                seg_durs[-1] += extra
    else:
        clip_len = max(narr_dur + GAP, hold)
        seg_durs = [clip_len / k] * k

    inputs = []
    vparts = []
    for i, (s, e) in enumerate(segments):
        seg_len = seg_durs[i]
        inputs += ["-ss", f"{s:.3f}", "-i", str(source)]
        # each input -> normalise + fit to seg_len (hold last frame if short)
        z = config.MOTION_ZOOM
        tf = max(1, int(round(seg_len * fps)))
        zexpr = (f"min(zoom+{z/tf:.6f},{1.0+z:.4f})" if i % 2 == 0
                 else f"if(eq(on,0),{1.0+z:.4f},max(zoom-{z/tf:.6f},1.0))")
        motion = (f",zoompan=z='{zexpr}':d=1:x='iw/2-(iw/zoom/2)':"
                  f"y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}") if config.MOTION_ENABLE else ""
        vparts.append(
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps}{motion},"
            f"tpad=stop_mode=clone:stop_duration={seg_len:.3f},"
            f"trim=duration={seg_len:.3f},setpts=PTS-STARTPTS[v{i}]"
        )
    concat_in = "".join(f"[v{i}]" for i in range(len(segments)))
    vchain = ";".join(vparts) + f";{concat_in}concat=n={len(segments)}:v=1:a=0[v]"

    # narration audio on input k (after the video inputs), padded to clip_len
    inputs += ["-i", str(narr_audio)]
    af = (f"[{len(segments)}:a]afade=t=in:st=0:d={nf},"
          f"afade=t=out:st={max(0.0, narr_dur - nf):.3f}:d={nf},"
          f"apad=whole_dur={clip_len:.3f},"
          f"aformat=sample_rates=48000:channel_layouts=stereo[a]")

    cmd = [
        ff, "-y", *inputs,
        "-filter_complex", f"{vchain};{af}",
        "-map", "[v]", "-map", "[a]",
        "-t", f"{clip_len:.3f}",
        "-c:v", "libx264", "-preset", "veryfast",
        "-crf", str(config.VIDEO_CRF), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        str(out),
    ]
    _run(cmd, f"build montage {out.name}")
    return clip_len


def _xfade_chain(ff: str, clips: list[tuple[Path, float]], out: Path):
    """
    Chain clips with xfade (video) + acrossfade (audio).
    clips: list of (path, duration). Returns total timeline duration.
    Splits into batches to keep the filtergraph manageable, then xfades
    the batch results together.
    """
    # First pass: xfade within batches
    BATCH = 12
    batches = [clips[i:i + BATCH] for i in range(0, len(clips), BATCH)]
    batch_files: list[tuple[Path, float]] = []

    for bi, batch in enumerate(batches):
        bout = out.parent / f"_batch_{bi:03d}.mp4"
        dur = _xfade_single(ff, batch, bout)
        batch_files.append((bout, dur))

    if len(batch_files) == 1:
        batch_files[0][0].replace(out)
        return batch_files[0][1]

    # Second pass: xfade the batch results together
    total = _xfade_single(ff, batch_files, out)
    return total


def _xfade_single(ff: str, clips: list[tuple[Path, float]], out: Path) -> float:
    """xfade a list of (path,dur) into one file. Returns total duration."""
    if len(clips) == 1:
        clips[0][0].replace(out)
        return clips[0][1]

    inputs = []
    for p, _ in clips:
        inputs += ["-i", str(p)]

    vfilters = []
    afilters = []
    # running offset where the next xfade begins
    prev_v = "0:v"
    prev_a = "0:a"
    cumulative = clips[0][1]
    for i in range(1, len(clips)):
        offset = cumulative - XFADE
        vlabel = f"vx{i}"
        alabel = f"ax{i}"
        vfilters.append(
            f"[{prev_v}][{i}:v]xfade=transition=fade:duration={XFADE}:offset={offset:.3f}[{vlabel}]"
        )
        afilters.append(
            f"[{prev_a}][{i}:a]acrossfade=d={XFADE}[{alabel}]"
        )
        prev_v = vlabel
        prev_a = alabel
        cumulative += clips[i][1] - XFADE

    filtergraph = ";".join(vfilters + afilters)
    cmd = [
        ff, "-y", *inputs,
        "-filter_complex", filtergraph,
        "-map", f"[{prev_v}]", "-map", f"[{prev_a}]",
        "-c:v", "libx264", "-preset", "veryfast",
        "-crf", str(config.VIDEO_CRF), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(out),
    ]
    _run(cmd, f"xfade chain -> {out.name}")
    return cumulative


def _clip_signature(source: Path, start: float, end: float, hold: float,
                    idx: int, crop_top: float, narr_dur: float,
                    audio_path: Path, censor: str = "none",
                    censor_region=None, exposure: float = 0.0, silence=None) -> str:
    """Hash everything that determines a clip's pixels+audio, for caching."""
    import hashlib
    try:
        smtime = int(source.stat().st_mtime)
        amtime = int(audio_path.stat().st_mtime)
        asize = audio_path.stat().st_size
    except OSError:
        smtime = amtime = asize = 0
    parts = [
        str(source), str(smtime),
        f"{start:.3f}", f"{end:.3f}", f"{hold:.3f}", str(idx % 2),
        f"{crop_top:.3f}", f"{narr_dur:.3f}",
        str(audio_path.name), str(amtime), str(asize),
        # motion/canvas settings that change pixels:
        str(config.MOTION_ENABLE), str(config.MOTION_ZOOM),
        f"{config.OUTPUT_WIDTH}x{config.OUTPUT_HEIGHT}@{config.OUTPUT_FPS}",
        str(config.VIDEO_CRF), f"{GAP:.3f}",
        # censor level changes pixels -> must bust the cache:
        f"censor={str(censor or 'none')}",
        # censor REGION changes pixels too (partial vs whole-frame, or a moved
        # rectangle) -> part of the signature (None -> whole-frame/no region):
        f"region={_region_sig(censor_region)}",
        # DARK-scene exposure lift changes pixels -> part of the signature.
        f"exposure={float(exposure or 0.0):.3f}",
        # Gap 3: a silence shot has a different duration + silent audio than a
        # narrated build of the same clip -> must bust the cache.
        f"silence={'none' if silence is None else f'{float(silence):.3f}'}",
    ]
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]


def _region_sig(censor_region) -> str:
    """Stable cache token for a censor region (None -> 'none')."""
    if censor_region is None:
        return "none"
    return "%d,%d,%d,%d" % (
        int(censor_region.x), int(censor_region.y),
        int(censor_region.width), int(censor_region.height))


def render(project: str, draft: dict,
           narration: list[tuple[int, Path, float]],
           music: Path | None = None,
           captions: bool = True,
           keep_temp: bool = False,
           force_clips: bool = False) -> Path:
    pdir = config.project_dir(project)
    source = pdir / "source.mp4"
    work = pdir / "_work"
    work.mkdir(exist_ok=True)
    cache_dir = pdir / "_clipcache"
    cache_dir.mkdir(exist_ok=True)
    ff = config.ffmpeg()
    ffp = config.ffprobe()

    by_id = {n[0]: n for n in narration}
    # Last line of defence before anything is baked into an mp4. draft-stage
    # gates validate draft.json; this checks what the RENDER actually holds.
    # If two lines share an id, `narration` has two entries and this dict has
    # one - both lines then play the same audio, and no earlier gate can see it
    # because the draft text was in the right order all along.
    if len(by_id) != len(narration):
        _seen, _dupes = set(), []
        for _n in narration:
            (_dupes.append(_n[0]) if _n[0] in _seen else _seen.add(_n[0]))
        console.print(f"[red]Duplicate line id(s) in narration: {sorted(set(_dupes))}. "
                      f"{len(narration)} lines but only {len(by_id)} audio files - "
                      f"the duplicates would share one voiceover. Renumber and "
                      f"re-run `draft` before rendering.[/]")
        sys.exit(1)

    # load the action B-roll pool (if any) so lines can use "pool": "A4"
    from pipeline import broll as brollmod
    pool = brollmod.load(project)

    # load shots.json censor flags, keyed by (clip_start, clip_end) and by id.
    # A draft line bound to clip_start/clip_end inherits its shot's censor level
    # AND (Phase C) its optional partial-blur region.
    censor_by_clip: dict = {}
    region_by_clip: dict = {}
    silence_by_clip: dict = {}      # Gap 3: (clip_start, clip_end) -> seconds
    exposure_by_clip: dict = {}     # DARK shots: (clip_start, clip_end) -> lift amount
    n_partial = 0
    try:
        import json as _json
        try:
            from schemas import CensorRegion as _CensorRegion, _drop_unknown as _du
        except ImportError:
            from pipeline.schemas import CensorRegion as _CensorRegion, _drop_unknown as _du
        sp = pdir / "shots.json"
        if sp.exists():
            sd = _json.loads(sp.read_text(encoding="utf-8-sig"))
            for s in sd.get("shots", []):
                key = (s.get("clip_start"), s.get("clip_end"))
                cz = str(s.get("censor", "none") or "none")
                if cz != "none":
                    if s.get("clip_start") and s.get("clip_end"):
                        censor_by_clip[key] = cz
                        reg = s.get("censor_region")
                        if isinstance(reg, dict):
                            region_by_clip[key] = _CensorRegion(**_du(_CensorRegion, reg))
                            n_partial += 1
                sil = s.get("narration_silence_seconds")
                if sil is not None and s.get("clip_start") and s.get("clip_end"):
                    sv = float(sil)
                    if sv > 0:
                        silence_by_clip[key] = min(sv, 30.0)
                # DARK-scene exposure lift (optional). exposure_lift is a small
                # positive float (0.0 = none). Catalogue may flag it explicitly,
                # or we auto-derive it from a 'DARK' tag in the shot's action so
                # dim scenes (bunker/flood/aftermath) stay readable - per the
                # Joker B35 lesson (do NOT darken already-dark footage).
                ev = s.get("exposure_lift")
                if ev is None and "DARK" in str(s.get("action", "")):
                    ev = config.DARK_EXPOSURE_LIFT if hasattr(config, "DARK_EXPOSURE_LIFT") else 0.18
                if ev and s.get("clip_start") and s.get("clip_end"):
                    exposure_by_clip[key] = float(ev)
    except Exception as e:
        console.print(f"[yellow]Could not read shots.json censor/silence flags: {e}[/]")
    if censor_by_clip:
        extra = f" ({n_partial} partial-region)" if n_partial else ""
        console.print(f"[cyan]Censor:[/] {len(censor_by_clip)} shot(s) flagged for blur{extra}")
    if silence_by_clip:
        console.print(f"[cyan]Silence:[/] {len(silence_by_clip)} silent shot(s) "
                      f"(music swells to {int(config.SILENCE_MUSIC_VOLUME*100)}%)")
    if exposure_by_clip:
        console.print(f"[cyan]Exposure:[/] {len(exposure_by_clip)} dark shot(s) "
                      f"lifted for visibility")

    # absolute (start, end) windows on the timeline where music should swell.
    silence_windows: list[tuple[float, float]] = []

    console.print("[cyan]Building clips (with baked narration)...[/]")
    clips: list[tuple[Path, float]] = []
    timeline: list[dict] = []
    boundaries: list[float] = []
    cursor = 0.0  # start time of current clip on the overlapped timeline
    n_pool = 0
    n_cached = 0

    for idx, ln in enumerate(draft["lines"]):
        lid = ln["id"]

        # ---- Gap 3 SILENCE line: the LINE itself carries the silence ---------
        # A silence line has narration_silence_seconds (set on the draft line,
        # mirroring its silence shot) and no narration. Build a visual-only hold
        # and record the timeline window so music can swell. NOTE: detection is
        # per-LINE, not per-clip - a normal framing line may bind the SAME clip
        # as a silence shot (e.g. a lead-in held just before the silence) and
        # must keep its narration.
        _skey = (ln.get("clip_start"), ln.get("clip_end"))
        sil_secs = ln.get("narration_silence_seconds")
        if sil_secs is None:
            sil_secs = silence_by_clip.get(_skey) if not ln.get("narration", "").strip() else None
        if sil_secs is not None and not ln.get("montage"):
            sil_secs = float(sil_secs)
            crop_top = 0.0
            cout = work / f"clip_{lid:03d}.mp4"
            start = parse_ts(ln["clip_start"])
            end = parse_ts(ln["clip_end"])
            censor = censor_by_clip.get(_skey, "none")
            censor_region = region_by_clip.get(_skey)
            exposure = exposure_by_clip.get(_skey, 0.0)
            sig = _clip_signature(source, start, end, 0.0, idx, crop_top,
                                  0.0, source, censor, censor_region,
                                  exposure=exposure, silence=sil_secs)
            cached = cache_dir / f"{sig}.mp4"
            reused = False
            if not force_clips and cached.exists():
                import shutil
                shutil.copy2(cached, cout)
                clip_len = float(sil_secs)
                reused = True
                n_cached += 1
            else:
                clip_len = _build_silence_clip(ff, source, start, end, cout,
                                               sil_secs, idx, crop_top,
                                               censor, censor_region, exposure)
                try:
                    import shutil
                    shutil.copy2(cout, cached)
                except Exception:
                    pass
            clips.append((cout, clip_len))
            boundaries.append(cursor)
            silence_windows.append((cursor, cursor + clip_len))
            # no caption text for a silence shot
            cursor += clip_len - XFADE
            tag = " [dim](cached)[/]" if reused else ""
            console.print(f"  line {lid:>3}: [silen] -> {clip_len:4.1f}s "
                          f"(no narration, music swell){tag}")
            continue

        if lid not in by_id:
            console.print(f"[red]No narration audio for line {lid}.[/]")
            sys.exit(1)
        _, audio_path, narr_dur = by_id[lid]
        narr_dur = max(0.4, narr_dur)
        hold = float(ln.get("hold", 0.0))
        need = max(narr_dur + GAP, hold)

        crop_top = 0.0
        src_label = "scene"
        cout = work / f"clip_{lid:03d}.mp4"

        # ---- MONTAGE HOLD: cut through several action shots in one line -----
        if ln.get("montage"):
            segs = []
            play_durs = []          # Mức 2: per-segment play_duration (or None)
            inline = False
            for lab in ln["montage"]:
                # Mức 1: a montage entry may be an INLINE timestamp segment
                # (dict {clip_start, clip_end} or [start, end] list) for projects
                # with no broll.json (e.g. joker2019 - explicit bindings only).
                # This cuts a real rapid-cut sequence across its hard cuts instead
                # of freezing one short shot.
                # Mức 2: a dict segment may carry an optional `play_duration` so
                # each shot plays for its OWN length instead of an equal split.
                if isinstance(lab, dict) and lab.get("clip_start"):
                    segs.append((parse_ts(lab["clip_start"]), parse_ts(lab["clip_end"])))
                    play_durs.append(lab.get("play_duration"))
                    inline = True
                elif isinstance(lab, (list, tuple)) and len(lab) == 2:
                    segs.append((parse_ts(lab[0]), parse_ts(lab[1])))
                    play_durs.append(None)
                    inline = True
                else:
                    r = brollmod.resolve(pool, lab, 2.0, seed=lid + hash(lab) % 97)
                    if r is None:
                        console.print(f"[red]line {lid}: montage label '{lab}' unknown.[/]")
                        sys.exit(1)
                    segs.append((r["start"], r["end"]))
                    play_durs.append(None)
            # inline montage = narration-fit (no forced action hold); label
            # montage keeps the SHOWCASE_HOLD breathing behaviour.
            mh = hold if inline else (hold or config.SHOWCASE_HOLD)
            # Only pass play_durs if ANY segment declared one (Mức 2); else None
            # so _build_montage_clip uses the legacy equal-split (backward compat).
            pd_arg = play_durs if any(p is not None for p in play_durs) else None
            clip_len = _build_montage_clip(ff, source, segs, audio_path,
                                           narr_dur, cout, mh, play_durs=pd_arg)
            n_pool += 1
            clips.append((cout, clip_len))
            boundaries.append(cursor)
            timeline.append({"start": cursor, "end": cursor + narr_dur, "text": ln["narration"]})
            cursor += clip_len - XFADE
            _m2 = " m2" if pd_arg else ""
            console.print(f"  line {lid:>3}: [montg] -> {clip_len:4.1f}s "
                          f"(+{len(segs)} shots{' inline' if inline else ''}{_m2}, hold {mh:.0f}s)")
            continue

        if ln.get("pool"):
            r = brollmod.resolve(pool, ln["pool"], need, seed=lid)
            if r is None:
                console.print(f"[red]line {lid}: unknown pool label '{ln['pool']}'. "
                              f"Add it to broll.json or use clip_start/clip_end.[/]")
                sys.exit(1)
            start, end = r["start"], r["end"]
            crop_top = r["crop_top"]
            src_label = ln["pool"]
            n_pool += 1
        else:
            start = parse_ts(ln["clip_start"])
            end = parse_ts(ln["clip_end"])
            # ---- Mức 1 defensive capacity gate (also catches cache hits) -----
            # _build_clip raises on a cache MISS, but a cached clip would bypass
            # it; enforce the same contract here so an overrun never slips
            # through silently on a re-render.
            from pipeline.schemas import BindingViolation, BINDING_SLOWDOWN_MAX
            _shot_dur = max(0.0, end - start)
            _narr_need = narr_dur + GAP
            if _shot_dur > 0 and _narr_need > _shot_dur * BINDING_SLOWDOWN_MAX:
                raise BindingViolation(
                    line_id=lid, narration_dur=_narr_need,
                    shot_dur=_shot_dur, capacity=_shot_dur * BINDING_SLOWDOWN_MAX)

        # censor level for this clip (from shots.json; default "none"). Pool/
        # montage clips are not censored here (no shots.json mapping for them).
        _ckey = (ln.get("clip_start"), ln.get("clip_end"))
        censor = censor_by_clip.get(_ckey, "none")
        censor_region = region_by_clip.get(_ckey)  # None -> whole-frame blur
        exposure = exposure_by_clip.get(_ckey, 0.0)  # DARK-scene lift (0 = none)

        # ---- clip cache: reuse an identical previously-built clip -----------
        sig = _clip_signature(source, start, end, hold, idx, crop_top,
                              narr_dur, audio_path, censor, censor_region, exposure)
        cached = cache_dir / f"{sig}.mp4"
        reused = False
        if not force_clips and cached.exists():
            import shutil
            shutil.copy2(cached, cout)
            clip_len = max(narr_dur + GAP, hold)
            reused = True
            n_cached += 1
        else:
            clip_len = _build_clip(ff, source, start, end, audio_path, narr_dur,
                                   cout, idx, crop_top, hold, censor, censor_region,
                                   exposure)
            try:
                import shutil
                shutil.copy2(cout, cached)
            except Exception:
                pass
        clips.append((cout, clip_len))
        boundaries.append(cursor)  # absolute start time of this clip

        # caption window: narration starts at clip start, lasts narr_dur
        # `id` / `clip_*` are carried for timeline.json (see below); build_ass
        # ignores the extra keys.
        timeline.append({"start": cursor, "end": cursor + narr_dur,
                         "text": ln["narration"], "id": lid,
                         "clip_start": ln.get("clip_start"),
                         "clip_end": ln.get("clip_end")})
        cursor += clip_len - XFADE

        held = f" +hold{hold:.0f}s" if hold else ""
        tag = " [dim](cached)[/]" if reused else ""
        console.print(f"  line {lid:>3}: [{src_label:<5}] -> {clip_len:4.1f}s{held}{tag}")

    if clips:
        pct = 100.0 * n_pool / len(clips)
        console.print(f"  [bold]action B-roll: {n_pool}/{len(clips)} clips "
                      f"({pct:.0f}%)[/]")
        if n_cached:
            console.print(f"  [dim]reused {n_cached}/{len(clips)} cached clips "
                          f"(only changed lines were rebuilt)[/]")

    # ----- xfade everything into one continuous stream -----------------------
    console.print("[cyan]Crossfading clips into one smooth stream...[/]")
    av = work / "av_xfade.mp4"
    total_dur = _xfade_chain(ff, clips, av)
    console.print(f"  timeline length: {total_dur/60:.1f} min")

    # ----- captions ----------------------------------------------------------
    ass_for_filter = None
    if captions:
        console.print("[cyan]Building captions...[/]")
        ass_path = pdir / "captions.ass"
        srtmod.build_ass(timeline, ass_path)
        ass_for_filter = ass_path.as_posix().replace(":", "\\:")
    else:
        console.print("[yellow]Captions disabled (--no-captions).[/]")

    # ----- sound design events ----------------------------------------------
    sfx_events = []
    if getattr(config, "SFX_ENABLE", False):
        from pipeline import sfx as sfxmod
        sfxmod.ensure_sfx()
        sfx_events = sfxmod.plan_events(draft, boundaries)
        if sfx_events:
            console.print(f"[cyan]Sound design:[/] {len(sfx_events)} SFX hits "
                          "(whoosh/boom/riser/sting)")

    # ----- final: (optional captions), mix music, encode --------------------
    label = ("Burning captions + " if captions else "") + ("mixing music " if music else "") + "encoding..."
    console.print(f"[cyan]{label}[/]")
    final = pdir / "final.mp4"

    if music and music.exists():
        _render_with_music(ff, av, music, ass_for_filter, total_dur, final,
                           sfx_events, silence_windows)
    else:
        vf = f"subtitles='{ass_for_filter}'" if ass_for_filter else None
        cmd = [ff, "-y", "-i", str(av)]
        if vf:
            cmd += ["-vf", vf]
        af = _loudnorm_filter()
        if af:
            cmd += ["-af", af]
        cmd += [
            "-c:v", "libx264", "-preset", config.VIDEO_PRESET,
            "-crf", str(config.VIDEO_CRF), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            str(final),
        ]
        _run(cmd, "final encode")

    # Clean up intermediate render artifacts in _work/ (clip_*.mp4, _batch_*.mp4,
    # av_xfade.mp4). These are throwaway and can total hundreds of MB. We never
    # touch source.mp4 here.
    if not keep_temp and work.exists():
        import shutil as _shutil
        try:
            freed = sum(f.stat().st_size for f in work.rglob("*") if f.is_file())
            _shutil.rmtree(work)
            console.print(f"[dim]Removed temp {work.name}/ (freed "
                          f"{freed/(1024*1024):.0f} MB). Use --keep-temp to keep it.[/]")
        except OSError as e:
            console.print(f"[yellow]Could not remove {work.name}/: {e}[/]")

    # ----- timeline.json + post-render checks --------------------------------
    # Written on EVERY render, captions on or off. Until now the only record of
    # where a line lands in the finished video was the .ass file, which stores
    # caption TEXT and no line id - so a QA note could only ever say "something
    # is off around minute 7" instead of "line 36 drifts".
    try:
        tl = [{"id": t.get("id"),
               "out_start": round(t["start"], 3),
               "out_end": round(t["end"], 3),
               "clip_start": t.get("clip_start"),
               "clip_end": t.get("clip_end")} for t in timeline]
        (pdir / "timeline.json").write_text(
            json.dumps({"project": project, "total_duration": round(total_dur, 3),
                        "lines": tl}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        console.print(f"[dim]Wrote timeline.json ({len(tl)} lines) - "
                      f"maps each line id to its position in final.mp4.[/]")
    except Exception as e:
        console.print(f"[yellow]Could not write timeline.json: {e}[/]")

    # Every gate in this pipeline validates draft.json. None of them look at what
    # the render actually produced. That gap let a duplicate line id put a
    # late-film voiceover over an early scene while every gate stayed green.
    # These three counts are cheap and cover the whole class.
    problems = []
    if len(clips) != len(narration):
        problems.append(f"{len(narration)} narration line(s) but {len(clips)} clip(s) built")
    if len(timeline) != len(clips):
        problems.append(f"{len(clips)} clip(s) but {len(timeline)} timeline entr(ies)")
    est = sum(d for _f, d in clips) - XFADE * max(0, len(clips) - 1)
    if est > 0 and abs(total_dur - est) / est > 0.05:
        problems.append(f"runtime {total_dur/60:.1f} min is >5% off the "
                        f"expected {est/60:.1f} min from the clip durations")
    if problems:
        console.print("[red][RENDER-CHECK][/] the render does not match the draft:")
        for pr in problems:
            console.print(f"    {pr}")
        console.print("[red]  final.mp4 was still written - inspect it before publishing.[/]")
    else:
        console.print(f"[dim][RENDER-CHECK] {len(clips)} lines in, {len(clips)} clips out, "
                      f"runtime within 5% of expected.[/]")

    console.print(f"\n[bold green]Done![/] Final video: {final}")
    return final


def _loudnorm_filter() -> str:
    """Return a loudnorm audio-filter string, or '' if disabled."""
    if not config.LOUDNORM_ENABLE:
        return ""
    return (f"loudnorm=I={config.LOUDNORM_I}:TP={config.LOUDNORM_TP}:"
            f"LRA={config.LOUDNORM_LRA}")


def _music_volume_expr(base_vol: float, silence_windows: list) -> str:
    """
    Build an ffmpeg `volume` filter string for the music bed.

    No silence windows -> a plain static `volume={base_vol}`.
    With windows -> a time-expression `volume=...:eval=frame` that ramps from
    base_vol up to SILENCE_MUSIC_VOLUME over SILENCE_FADE at each window start,
    holds, then ramps back down over SILENCE_FADE at the window end.
    Windows are expressed as a trapezoid; the final level is max(base, swells).
    """
    if not silence_windows:
        return f"volume={base_vol}"
    swell = float(getattr(config, "SILENCE_MUSIC_VOLUME", 0.35))
    f = max(0.05, float(getattr(config, "SILENCE_FADE", 0.5)))
    amp = swell - base_vol
    terms = []
    for (s, e) in silence_windows:
        s = float(s); e = float(e)
        if e <= s:
            continue
        # rising ramp:   clip((t-s)/f, 0, 1) for t in [s, ...]
        rise = f"clip((t-{s:.3f})/{f:.3f}\\,0\\,1)"
        # falling ramp:  clip((e-t)/f, 0, 1) for t up to e (0 outside window)
        fall = f"clip(({e:.3f}-t)/{f:.3f}\\,0\\,1)"
        # trapezoid for this window = amp * min(rise, fall), zero outside [s,e]
        trap = (f"if(between(t\\,{s:.3f}\\,{e:.3f})\\,"
                f"{amp:.4f}*min({rise}\\,{fall})\\,0)")
        terms.append(trap)
    # total = base + sum of trapezoids (windows do not overlap by construction)
    expr = f"{base_vol}+" + "+".join(terms) if terms else f"{base_vol}"
    return f"volume='{expr}':eval=frame"


def _render_with_music(ff: str, av: Path, music: Path, ass_filter: str | None,
                       total_dur: float, final: Path,
                       sfx_events: list[dict] | None = None,
                       silence_windows: list[tuple[float, float]] | None = None):
    """Burn captions (optional), mix ducked music + timed SFX, master loudness.

    Gap 3: during each (start, end) silence window the music swells from the
    ducked narration level (MUSIC_VOLUME) up to SILENCE_MUSIC_VOLUME with a
    SILENCE_FADE-second rise/fall, then returns to the narration level.
    """
    vol = config.MUSIC_VOLUME
    fade = config.MUSIC_FADEOUT
    fade_start = max(0.0, total_dur - fade)
    sfx_events = sfx_events or []
    silence_windows = silence_windows or []

    # Base music volume is `vol`. For silence windows, build a piecewise volume
    # expression that ramps up to SILENCE_MUSIC_VOLUME over SILENCE_FADE and back.
    vol_expr = _music_volume_expr(vol, silence_windows)

    # music: loop to cover total_dur, set volume (static or swelling), fade out.
    music_chain = (
        f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,"
        f"{vol_expr},afade=t=out:st={fade_start:.2f}:d={fade:.2f}[mus]"
    )

    if config.MUSIC_DUCK:
        mix = (
            f"{music_chain};"
            f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo[narr];"
            f"[narr]asplit=2[narr_out][sc];"
            f"[mus][sc]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400[mducked];"
            f"[narr_out][mducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[premix]"
        )
    else:
        mix = (
            f"{music_chain};"
            f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo[narr];"
            f"[narr][mus]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[premix]"
        )

    # --- SFX: each event becomes an extra input, delayed to its timestamp ----
    from pipeline import sfx as sfxmod
    sfx_inputs: list[str] = []
    sfx_labels: list[str] = []
    base_idx = 2  # inputs 0=av, 1=music
    for k, ev in enumerate(sfx_events):
        wav = sfxmod.SFX_DIR / f"{ev['sfx']}.wav"
        if not wav.exists():
            continue
        sfx_inputs += ["-i", str(wav)]
        ii = base_idx + len(sfx_labels)
        delay_ms = int(max(0.0, ev["at"]) * 1000)
        gain = ev.get("gain", -14.0)
        lbl = f"sfx{k}"
        mix += (f";[{ii}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                f"volume={gain}dB,adelay={delay_ms}|{delay_ms}[{lbl}]")
        sfx_labels.append(lbl)

    if sfx_labels:
        amix_in = "[premix]" + "".join(f"[{l}]" for l in sfx_labels)
        mix += (f";{amix_in}amix=inputs={1+len(sfx_labels)}:duration=first:"
                f"dropout_transition=0:normalize=0[mixed]")
        last = "mixed"
    else:
        last = "premix"

    lnf = _loudnorm_filter()
    if lnf:
        mix += f";[{last}]{lnf}[aout]"
    else:
        mix += f";[{last}]anull[aout]"

    if ass_filter:
        vmap = "[v]"
        graph = f"[0:v]subtitles='{ass_filter}'[v];{mix}"
    else:
        vmap = "0:v"
        graph = mix

    cmd = [
        ff, "-y",
        "-i", str(av),
        "-stream_loop", "-1", "-i", str(music),
        *sfx_inputs,
        "-filter_complex", graph,
        "-map", vmap, "-map", "[aout]",
        "-t", f"{total_dur:.3f}",
        "-c:v", "libx264", "-preset", config.VIDEO_PRESET,
        "-crf", str(config.VIDEO_CRF), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(final),
    ]
    _run(cmd, "final encode with music")



