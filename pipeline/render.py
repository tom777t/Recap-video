

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
# Seconds of picture BEFORE the voice starts, per narrated line. See
# config.NARRATION_LEAD_IN - it is a genre parameter, not a constant.
# GAP stays at the END of the clip; LEAD_IN is added at the FRONT.
LEAD_IN = float(getattr(config, "NARRATION_LEAD_IN", 0.0))

# Line flags whose picture is built by pipeline.intro, NOT by the clip loop.
# Such a line has NO clip window at all (draft.py REJECTS a clip_start on one),
# so every loop that reads ln["clip_start"] must skip it first.
#
# This is a LIST, not two if-statements, because that is how the bug happened:
# `over_montage` was skipped and `film_intro` - added later, same category - was
# not, and `parse_ts(ln["clip_start"])` raised KeyError on the first full
# render. A new intro-owned flag is now one entry here, and tools/
# test_render_smoke.py asserts every flag in this set survives a real render.
INTRO_OWNED = ("over_montage", "film_intro")


def intro_owned(ln: dict) -> bool:
    """True if this line's picture comes from the intro builder (no clip window)."""
    return any(ln.get(k) for k in INTRO_OWNED)


def _lead_for(narr_dur: float, shot_dur: float, extra: float = 0.0) -> float:
    """Per-line lead-in, CLAMPED to what the shot can actually carry.

    `extra` is additional front silence for this line specifically - currently
    config.PRE_REVEAL_PAUSE on a <reveal> line, so the reveal arrives out of a
    gap instead of on the heels of the previous sentence. It is added BEFORE
    the clamp, deliberately: the clamp is the thing that stops a comfort
    feature turning a rendering project into a BindingViolation, and a second
    source of front-padding that skipped it would walk straight into the bug
    this function exists to prevent.

    The lead-in is a comfort feature; the binding contract is a correctness one.
    A flat LEAD_IN added to every line pushes any line already near its shot's
    slow-motion ceiling over it, turning a rendering project into a
    BindingViolation. Measured when this was first written flat at 0.5s:
    interstellar2014_linear 0 -> 8 violations, parasite2019 0 -> 12,
    gonegirl2014 49 -> 52. Those films render today and must keep rendering.

    So the lead shrinks to fit and, on a line with no room at all, becomes 0 -
    the line simply behaves as it did before. Lines with spare footage (the
    normal case, and the whole reason this exists) get the full value.
    """
    want = LEAD_IN + max(0.0, float(extra or 0.0))
    if want <= 0.0:
        return 0.0
    if shot_dur <= 0.0:          # pool/unknown window: nothing to clamp against
        return want
    from pipeline.schemas import BINDING_SLOWDOWN_MAX
    capacity = shot_dur * BINDING_SLOWDOWN_MAX
    # 1ms of slack: without it a line whose room is EXACTLY the lead lands on
    # `narr_need == capacity` and float error tips the `>` comparison into a
    # BindingViolation. Measured at shot_dur=7.3s in the clamp test.
    room = capacity - (narr_dur + GAP) - 1e-3
    return max(0.0, min(want, room))


def _run(cmd: list[str], desc: str):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        console.print(f"[red]ffmpeg failed during: {desc}[/]")
        console.print(proc.stderr[-2500:])
        sys.exit(1)
    return proc


def _verify_clip(out: Path, clip_len: float, what: str) -> None:
    """A built clip must really be as long as it claims, in BOTH streams.

    THE DEFECT THIS CATCHES: nine clips in the Tokyo Drift cache have a video
    stream shorter than their audio - the worst by 3.0s. `-t clip_len` is on
    the OUTPUT, so it can only trim; if the video filter chain produces less
    than clip_len, the clip is simply written short and ffmpeg exits 0. The
    clip loop then reports `clip_len` to the xfade chain, every xfade offset
    downstream is computed from a number that is not true, and `xfade` stops
    advancing the picture - which is how a 17-minute film ended up with 4
    minutes of video and 17 minutes of audio.

    So every clip is measured the moment it is written. This is the cheapest
    possible place to catch it: one ffprobe against a file already on disk,
    and it names the line instead of leaving a silent hole in the film.
    """
    from pipeline import probe as _probe
    if not Path(out).exists():
        # `_run` exits the process when ffmpeg fails, so in a real render the
        # file is always here by now. Absence means the caller stubbed the
        # runner to inspect the filtergraph without encoding - which is how
        # test_stems checks that the audio chain reads the no-vocals stem.
        # Nothing to measure, and nothing to complain about.
        return
    st = _probe.streams(out)
    v, a = st.get("video"), st.get("audio")
    tol = 2.0 / float(config.OUTPUT_FPS or 30)     # two frames
    if v is None:
        console.print(f"[red]{what}: the clip has no video stream.[/]")
        sys.exit(1)
    if v["duration"] + tol < float(clip_len):
        console.print(
            f"[red]{what}: the clip is SHORT. It claims {clip_len:.3f}s but "
            f"its video stream is {v['duration']:.3f}s "
            f"({v['duration'] - float(clip_len):+.3f}s).[/]")
        console.print(
            "[red]  A short clip silently truncates the whole film: the "
            "xfade chain lays the next clip at an offset past the end of "
            "this one, and the picture stops advancing there while the "
            "soundtrack plays on. Widen the window or shorten the hold.[/]")
        sys.exit(1)
    if a is not None and abs(a["duration"] - v["duration"]) > 0.25:
        console.print(
            f"[red]{what}: video is {v['duration']:.3f}s but audio is "
            f"{a['duration']:.3f}s - the streams disagree by "
            f"{a['duration'] - v['duration']:+.3f}s.[/]")
        sys.exit(1)


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
                censor: str = "none", censor_region=None, exposure: float = 0.0,
                lead_in: float | None = None,
                film_audio: bool = False, pre_reveal: bool = False,
                split_segments: list | None = None,
                film_src: Path | None = None,
                src_wh: tuple | None = None):
    # `film_audio` / `pre_reveal` / `split_segments` / `film_src` are LAST on
    # purpose - see the note in _build_silence_clip. This function is called
    # positionally.
    #
    # `film_src` is the audio the film is heard THROUGH: the Demucs no-vocals
    # stem, so engines and impacts survive but the characters do not talk over
    # the narrator. None means read the audio from `source` itself, which is
    # the un-separated mix and must only happen inside a <film_speaks> unit.
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
    # `lead` seconds of picture first, then the narration, then GAP. The
    # narration audio is delayed by `lead` below (adelay), so the voice no
    # longer lands on the clip's first frame. `lead` is clamped per line by
    # _lead_for(); the caller passes the same value it used for the timeline.
    lead = _lead_for(narr_dur, max(0.0, float(end) - float(start))) \
        if lead_in is None else float(lead_in)
    clip_len = max(lead + narr_dur + GAP, hold)
    w, h, fps = config.OUTPUT_WIDTH, config.OUTPUT_HEIGHT, config.OUTPUT_FPS
    _SCALER = config.VIDEO_SCALER
    nf = config.NARRATION_FADE

    # ---- Mức 1: fit footage to narration via trim or mild slow-motion -------
    # shot_dur = real footage available in [start, end]. clip_len = how long the
    # clip must play (driven by narration + gap, or an intentional `hold`).
    shot_dur = max(0.0, float(end) - float(start))
    setpts_factor = 1.0           # >1.0 = slow down footage to fill the window
    if shot_dur > 0:
        # only the NARRATION-driven need triggers the contract; an intentional
        # `hold` (action breathing) is allowed to clone frames as before.
        # the (clamped) lead counts: the clip must carry that much extra
        # picture. Because _lead_for() already shrank it to fit capacity, this
        # can no longer turn a rendering line into a violation.
        narr_need = lead + narr_dur + GAP
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
        f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags={_SCALER},"
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
    # then trim to exact length.
    # CAPPED at config.MAX_FREEZE_SEC. This used to be stop_duration=clip_len,
    # i.e. no ceiling at all: a short window under a long line became a STILL
    # IMAGE for seconds. A clone this brief reads as a held beat; past it, it
    # reads as a bug. If a clip needs more picture than this, the window has to
    # be widened (across the following cuts) - which is what the capacity
    # pre-flight and tools/fit_narration.py now enforce.
    _freeze_cap = min(float(clip_len), float(config.MAX_FREEZE_SEC))
    vf = (
        f"{base}{motion},"
        f"tpad=stop_mode=clone:stop_duration={_freeze_cap:.3f},"
        f"trim=duration={clip_len:.3f},setpts=PTS-STARTPTS{censor_f}"
    )

    if cb > 0 and censor_region is not None:
        # PARTIAL blur (Phase C): split the processed frame, crop the region,
        # boxblur just that rectangle, and overlay it back.
        # The region is authored in SOURCE pixels (that is what whoever drew
        # the box was looking at) and the crop happens AFTER scale+pad, so it
        # must be transformed - see region_to_output. These two units used to
        # be conflated, which placed every partial blur wrong.
        rx, ry, rw, rh = region_to_output(censor_region, *(src_wh or (0, 0)))
        partial_graph = (
            f";[v0]split[base][region];"
            f"[region]crop={rw}:{rh}:{rx}:{ry},boxblur={cb}[blurred];"
            f"[base][blurred]overlay={rx}:{ry}[v]"
        )
        v_label = "[v0]"
    else:
        v_label = "[v]"

    # Fades are applied to the RAW narration (still relative to its own t=0),
    # THEN the whole thing is shifted right by LEAD_IN, THEN padded out to
    # clip_len. Order matters: delaying before the fades would fade the silence.
    # `all=1` applies the delay to every channel whatever the mp3's layout is.
    lead_ms = int(round(lead * 1000))
    delay_f = f"adelay={lead_ms}:all=1," if lead_ms > 0 else ""
    af = (
        f"afade=t=in:st=0:d={nf},"
        f"afade=t=out:st={max(0.0, narr_dur - nf):.3f}:d={nf},"
        f"{delay_f}"
        f"apad=whole_dur={clip_len:.3f},"
        f"aformat=sample_rates=48000:channel_layouts=stereo"
    )
    # When slowing down, bound the SOURCE read to exactly the [start, end]
    # window so setpts stretches the intended footage (not frames past `end`).
    # ---- 2f: split a long line's picture across 2-3 cuts -----------------
    # A twelve-second line on ONE shot is twelve seconds of the same frame
    # drifting under a Ken Burns zoom; the genre's own floor is clips under 8
    # seconds. `split_segments` is a list of CONTIGUOUS sub-windows of
    # [start, end], chosen by the caller at real cut points, so the picture
    # cuts while the film's audio keeps running underneath without a seam.
    # Contiguity is the whole reason this is safe: the audio is still read as
    # one continuous stretch from `start`, so it stays in sync with the
    # pictures as long as each sub-window plays for about its own real length.
    _segs = [(float(a), float(b)) for a, b in (split_segments or [])
             if float(b) > float(a)]
    if len(_segs) < 2:
        _segs = []

    src_in = ["-ss", f"{start:.3f}"]
    if setpts_factor > 1.0001 and shot_dur > 0:
        # READ ENOUGH SOURCE TO FILL clip_len. This used to be `-t shot_dur`,
        # which reads exactly the window and therefore produces
        # shot_dur*setpts_factor = narr_need seconds of picture. When clip_len
        # is LARGER than narr_need (a narrated line that also carries a `hold`)
        # the picture ran out, and nothing could put it back: `tpad` is capped
        # at MAX_FREEZE_SEC and `trim` only truncates, it cannot extend. The
        # clip was written with a video stream shorter than its audio, which
        # then truncated the whole film in the xfade chain.
        #
        # The answer is the same as everywhere else in this renderer: when
        # there is not enough picture, read MORE PICTURE. Output video length
        # is input_len * setpts_factor, so clip_len needs clip_len/factor of
        # source.
        _need_src = max(float(shot_dur), float(clip_len) / setpts_factor)
        src_in += ["-t", f"{_need_src:.3f}"]
    src_in += ["-i", str(source)]

    # ---- FILM AUDIO under the voice (2026-10-20) -------------------------
    # The clip's audio used to be the narration and nothing else, so every
    # engine, gunshot and line of dialogue in the film was thrown away. Mix the
    # source audio in underneath.
    # Two things have to track the picture:
    #   - when the footage is slowed (setpts_factor > 1) the audio is stretched
    #     by the same ratio with atempo, or it drifts out of sync. The ratio is
    #     bounded by BINDING_SLOWDOWN_MAX (1.4), so 1/1.4 = 0.714 stays inside
    #     atempo's legal 0.5-100 range.
    #   - `pre_reveal` raises the bed over the tail of the clip that sits
    #     immediately before a <reveal> line, so the reveal arrives out of the
    #     film's own sound instead of out of nothing.
    use_film = (film_audio and config.FILM_AUDIO_ENABLE
                and float(config.FILM_AUDIO_DB) > -60.0)
    # Where the film's audio is read from. A stem is a separate full-length
    # file, so it is a separate input seeked to the same `start`; the narration
    # occupies input index {NA}, so the stem lands at {NA}+1. Without a stem the
    # audio comes off the video input, which is the un-separated mix.
    _film_label = "[0:a]"
    _film_extra: list = []
    if use_film and film_src is not None:
        _film_extra = ["-ss", f"{start:.3f}",
                       "-t", f"{max(shot_dur, clip_len) + 0.5:.3f}",
                       "-i", str(film_src)]
    if use_film:
        _atempo = ""
        if setpts_factor > 1.0001:
            _atempo = f"atempo={1.0/setpts_factor:.5f},"
        _base_db = float(config.FILM_AUDIO_DB)
        if pre_reveal:
            _hi = float(config.FILM_AUDIO_PRE_REVEAL_DB)
            _sec = max(0.2, float(config.FILM_AUDIO_PRE_REVEAL_SEC))
            _from = max(0.0, clip_len - _sec)
            # linear ramp in dB over the last _sec seconds of the clip
            _vol = (f"volume='{_base_db}+({_hi - _base_db})"
                    f"*clip((t-{_from:.3f})/{_sec:.3f}\\,0\\,1)':"
                    f"eval=frame:precision=float")
        else:
            _vol = f"volume={_base_db}dB"
        film_af = (
            f"{_atempo}{_vol},"
            f"apad=whole_dur={clip_len:.3f},"
            f"atrim=duration={clip_len:.3f},asetpts=PTS-STARTPTS,"
            f"aformat=sample_rates=48000:channel_layouts=stereo"
        )
        # amix with normalize=0 SUMS the two tracks, so voice near full scale
        # plus film audio raised to FILM_AUDIO_PRE_REVEAL_DB can exceed 1.0 and
        # clip. Measured: the pre-reveal clip came out at max_volume 0.0 dB -
        # samples pinned at full scale, distortion baked into the clip file
        # where loudnorm (which runs later, on the mix) cannot undo it.
        # A limiter at -1 dBFS costs nothing audible and makes that impossible.
        graph = (f"{{VCHAIN}};[{{NA}}:a]{af}[narrv];{{FILMA}}{film_af}[filmv];"
                 f"[narrv][filmv]amix=inputs=2:duration=first:"
                 f"dropout_transition=0:normalize=0,"
                 f"alimiter=limit=0.891:level=disabled[a]{partial_graph}")
    else:
        graph = f"{{VCHAIN}};[{{NA}}:a]{af}[a]{partial_graph}"

    if _segs:
        # One input per sub-window, each normalised and trimmed to its share of
        # clip_len in proportion to its real length, then concatenated.
        # EQUAL screen time per sub-shot, not time proportional to how long the
        # source shot happens to run. Proportional shares were tried first, to
        # keep the continuously-read film audio in sync - but the audio is read
        # from `start` for the whole clip and never follows the segments, so
        # there was no sync to protect. What proportional shares DID do was
        # give one sub-shot 1.4 seconds of an 8.8-second clip, which is too
        # short to register as a shot at all and defeats the point of splitting.
        vin, vparts, labels = [], [], []
        for _i, (_a, _b) in enumerate(_segs):
            _share = clip_len / len(_segs)
            vin += ["-ss", f"{_a:.3f}", "-t", f"{_b - _a + 0.5:.3f}",
                    "-i", str(source)]
            _m = ""
            if config.MOTION_ENABLE and config.MOTION_ZOOM > 0:
                _tf = max(1, int(round(_share * fps)))
                _z = config.MOTION_ZOOM
                _ze = (f"min(zoom+{_z/_tf:.6f},{1.0+_z:.4f})" if _i % 2 == 0
                       else f"if(eq(on,0),{1.0+_z:.4f},max(zoom-{_z/_tf:.6f},1.0))")
                _m = (f",zoompan=z='{_ze}':d=1:x='iw/2-(iw/zoom/2)':"
                      f"y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}")
            vparts.append(
                f"[{_i}:v]{crop}{expo}scale={w}:{h}:flags={_SCALER}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps}{_m},"
                f"tpad=stop_mode=clone:stop_duration="
                f"{min(_share, float(config.MAX_FREEZE_SEC)):.3f},"
                f"trim=duration={_share:.3f},setpts=PTS-STARTPTS[s{_i}]")
            labels.append(f"[s{_i}]")
        # A split clip concatenates 2-3 DIFFERENT sub-windows, so a partial
        # censor_region (coordinates measured on the host shot's framing) is
        # meaningless for the other segments.
        #
        # This branch has now been wrong twice in opposite directions. First it
        # read `censor_region is None`, so a region-censored line that got
        # split rendered with NO BLUR AT ALL. Then it blurred the WHOLE frame,
        # which config.CENSOR_ALLOW_FULL_FRAME now forbids - a full-frame blur
        # is indistinguishable from losing the shot while still costing the
        # runtime.
        #
        # The right answer is not to choose between those: it is to NOT SPLIT a
        # region-censored clip. _split_points refuses to, so reaching here with
        # a region means that guard was bypassed, and the only safe thing left
        # is to refuse rather than ship either wrong picture.
        if cb > 0 and censor_region is not None:
            raise ValueError(
                f"{out.name}: a region-censored clip was split into "
                f"{len(_segs)} sub-windows. The region's coordinates only "
                f"describe the host shot, and full-frame blur is disallowed "
                f"(config.CENSOR_ALLOW_FULL_FRAME). _split_points should have "
                f"refused this clip - that guard has been bypassed.")
        _censor_tail = (f",boxblur={cb}:enable='between(t,0,{clip_len:.3f})'"
                        if cb > 0 else "")
        vchain = (";".join(vparts) + ";" + "".join(labels)
                  + f"concat=n={len(_segs)}:v=1:a=0"
                  + (f",{_censor_tail[1:]}" if _censor_tail else "")
                  + v_label)
        # film audio still comes from input 0, which is the FIRST sub-window and
        # therefore the start of the contiguous stretch.
        src_in = vin
        na = len(_segs)
    else:
        vchain = f"[0:v]{vf}{v_label}"
        na = 1
    # The stem, when present, is appended AFTER the narration input, so it is
    # input index na+1. Resolved here (not where the graph string is built)
    # because `na` is only known after the split branch has run.
    if _film_extra:
        _film_label = f"[{na + 1}:a]"
    graph = (graph.replace("{VCHAIN}", vchain).replace("{NA}", str(na))
                  .replace("{FILMA}", _film_label))

    cmd = [
        ff, "-y",
        *src_in,
        "-i", str(narr_audio),
        *_film_extra,
        "-filter_complex", graph,
        "-map", "[v]", "-map", "[a]",
        "-t", f"{clip_len:.3f}",
        "-c:v", "libx264", "-preset", config.VIDEO_PRESET_INTERMEDIATE,
        "-crf", str(config.VIDEO_CRF_INTERMEDIATE),
        "-pix_fmt", config.VIDEO_PIX_FMT,
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        str(out),
    ]
    _run(cmd, f"build clip {out.name}")
    _verify_clip(out, clip_len, f"clip {out.name}")
    return clip_len


def _build_silence_clip(ff: str, source: Path, start: float, end: float,
                        out: Path, silence_dur: float, idx: int = 0,
                        crop_top: float = 0.0,
                        censor: str = "none", censor_region=None,
                        exposure: float = 0.0,
                        film_audio: bool = False,
                        film_speaks: bool = False,
                        film_src: Path | None = None,
                        src_wh: tuple | None = None):
    # NOTE: `film_audio` is LAST on purpose. It was briefly added after `idx`,
    # which silently shifted every positional argument at the call site -
    # crop_top became film_audio, censor became crop_top. New parameters go on
    # the end of a function that is called positionally.
    """
    Gap 3: a SILENCE shot - visual holds for `silence_dur` seconds with NO
    narration (a silent audio track is baked so the downstream xfade/music mix
    stays uniform). Music swells during this window (handled at mix time).
    Mirrors `_build_clip`'s canvas/motion/censor/exposure so the look matches.

    NARRATION_LEAD_IN deliberately does NOT apply here (checked 2026-08-26).
    There is no narration to delay: the audio is anullsrc for the whole clip and
    clip_len is the authored hold, not a function of speech. Adding a lead-in
    would silently lengthen every silence beat beyond what the draft asked for.
    """
    clip_len = float(silence_dur)
    w, h, fps = config.OUTPUT_WIDTH, config.OUTPUT_HEIGHT, config.OUTPUT_FPS
    _SCALER = config.VIDEO_SCALER

    crop = ""
    if crop_top and 0.0 < crop_top < 0.5:
        crop = f"crop=iw:ih*{1.0-crop_top:.3f}:0:ih*{crop_top:.3f},"
    expo = ""
    if exposure and exposure > 0.001:
        e = min(0.5, float(exposure))
        expo = f"eq=brightness={e*0.6:.3f}:gamma={1.0+e:.3f}:saturation={1.0+e*0.5:.3f},"
    base = (
        f"{crop}{expo}"
        f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags={_SCALER},"
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
        f"tpad=stop_mode=clone:stop_duration="
        f"{min(float(clip_len), float(config.MAX_FREEZE_SEC)):.3f},"
        f"trim=duration={clip_len:.3f},setpts=PTS-STARTPTS{censor_f}"
    )

    if cb > 0 and censor_region is not None:
        # source pixels -> output pixels; see region_to_output
        rx, ry, rw, rh = region_to_output(censor_region, *(src_wh or (0, 0)))
        partial_graph = (
            f";[v0]split[base][region];"
            f"[region]crop={rw}:{rh}:{rx}:{ry},boxblur={cb}[blurred];"
            f"[base][blurred]overlay={rx}:{ry}[v]"
        )
        v_label = "[v0]"
    else:
        v_label = "[v]"

    # 2026-10-20: this used to be `anullsrc` - a hold was literally a hole in
    # the soundtrack. A hold is the one moment the FILM should be loudest: the
    # narrator has stopped on purpose and the picture is carrying the beat. So
    # the source audio plays here, well above its level under narration
    # (FILM_AUDIO_HOLD_DB vs FILM_AUDIO_DB), and the music swells over it as it
    # already did.
    _use_film = (film_audio and config.FILM_AUDIO_ENABLE
                 and float(config.FILM_AUDIO_HOLD_DB) > -60.0)
    if _use_film:
        # A hold keeps the film under a music swell; a <film_speaks> unit hands
        # the moment over entirely, so its audio sits at full level.
        _lvl = (float(getattr(config, "FILM_SPEAKS_DB", 0.0)) if film_speaks
                else float(config.FILM_AUDIO_HOLD_DB))
        _hold_af = (
            f"volume={_lvl}dB,"
            f"apad=whole_dur={clip_len:.3f},"
            f"atrim=duration={clip_len:.3f},asetpts=PTS-STARTPTS,"
            f"aformat=sample_rates=48000:channel_layouts=stereo"
        )
        # A HOLD uses the no-vocals stem: the narrator stopped on purpose and
        # the picture is carrying the beat, so the film should be LOUD - which
        # at -6 dB made its dialogue the clearest thing in the recap. Engines
        # and impacts carry a hold; characters talking do not.
        # A <film_speaks> unit is the deliberate exception: it hands the moment
        # over to the film, so it reads the ORIGINAL mix. That is the only place
        # in the whole render where the un-separated audio is used.
        _use_stem = (film_src is not None) and not film_speaks
        if _use_stem:
            a_in = ["-ss", f"{start:.3f}", "-t", f"{clip_len + 0.5:.3f}",
                    "-i", str(film_src)]
            _src_a = "[1:a]"
        else:
            a_in = []
            _src_a = "[0:a]"
        graph = f"[0:v]{vf}{v_label}{partial_graph};{_src_a}{_hold_af}[a]"
        a_map = "[a]"
    else:
        a_in = ["-f", "lavfi",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        graph = f"[0:v]{vf}{v_label}{partial_graph}"
        a_map = "1:a"
    cmd = [
        ff, "-y",
        "-ss", f"{start:.3f}", "-i", str(source),
        *a_in,
        "-filter_complex", graph,
        "-map", "[v]", "-map", a_map,
        "-t", f"{clip_len:.3f}",
        "-c:v", "libx264", "-preset", config.VIDEO_PRESET_INTERMEDIATE,
        "-crf", str(config.VIDEO_CRF_INTERMEDIATE),
        "-pix_fmt", config.VIDEO_PIX_FMT,
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        str(out),
    ]
    _run(cmd, f"build silence clip {out.name}")
    _verify_clip(out, clip_len, f"hold clip {out.name}")
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
    _SCALER = config.VIDEO_SCALER
    nf = config.NARRATION_FADE
    k = max(1, len(segments))

    if play_durs is not None:
        # Mức 2: explicit per-shot durations. Fill in any None with an equal
        # share of whatever time the narration needs beyond the declared sum.
        declared = [float(p) if p is not None else None for p in play_durs]
        sum_declared = sum(p for p in declared if p is not None)
        n_unset = sum(1 for p in declared if p is None)
        clip_len = max(LEAD_IN + narr_dur + GAP, sum_declared, hold)
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
        clip_len = max(LEAD_IN + narr_dur + GAP, hold)
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
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease:flags={_SCALER},"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps}{motion},"
            f"tpad=stop_mode=clone:stop_duration="
            f"{min(seg_len, float(config.MAX_FREEZE_SEC)):.3f},"
            f"trim=duration={seg_len:.3f},setpts=PTS-STARTPTS[v{i}]"
        )
    concat_in = "".join(f"[v{i}]" for i in range(len(segments)))
    vchain = ";".join(vparts) + f";{concat_in}concat=n={len(segments)}:v=1:a=0[v]"

    # narration audio on input k (after the video inputs), padded to clip_len
    inputs += ["-i", str(narr_audio)]
    # Same lead-in as _build_clip: fade the raw narration, shift it right by
    # LEAD_IN, then pad to clip_len. A montage line opens on its first sub-shot,
    # so it needs the beat just as much as a single-shot line does.
    _lead_ms = int(round(LEAD_IN * 1000))
    _delay_f = f"adelay={_lead_ms}:all=1," if _lead_ms > 0 else ""
    af = (f"[{len(segments)}:a]afade=t=in:st=0:d={nf},"
          f"afade=t=out:st={max(0.0, narr_dur - nf):.3f}:d={nf},"
          f"{_delay_f}"
          f"apad=whole_dur={clip_len:.3f},"
          f"aformat=sample_rates=48000:channel_layouts=stereo[a]")

    cmd = [
        ff, "-y", *inputs,
        "-filter_complex", f"{vchain};{af}",
        "-map", "[v]", "-map", "[a]",
        "-t", f"{clip_len:.3f}",
        "-c:v", "libx264", "-preset", config.VIDEO_PRESET_INTERMEDIATE,
        "-crf", str(config.VIDEO_CRF_INTERMEDIATE),
        "-pix_fmt", config.VIDEO_PIX_FMT,
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
        from pipeline import probe as _probe
        _v = _probe.streams(out).get("video")
        return float(_v["duration"]) if _v else float(batch_files[0][1])

    # Second pass: xfade the batch results together
    total = _xfade_single(ff, batch_files, out)
    return total


def _xfade_single(ff: str, clips: list[tuple[Path, float]], out: Path) -> float:
    """xfade a list of (path,dur) into one file. Returns total duration."""
    if len(clips) == 1:
        clips[0][0].replace(out)
        # measured, not claimed - this path moves a file and used to pass the
        # plan's number straight through
        from pipeline import probe as _probe
        _v = _probe.streams(out).get("video")
        return float(_v["duration"]) if _v else float(clips[0][1])

    # MEASURE EVERY INPUT. The offsets below are absolute positions on the
    # output timeline, and `xfade` cannot place a transition past the end of
    # its left-hand input: when the offset overshoots, the chain STOPS
    # ADVANCING THE PICTURE and every later clip is dropped, while
    # `acrossfade` - which takes no offset and chains on whatever the decoder
    # hands it - keeps the full soundtrack. Reproduced exactly: six 5.0s clips
    # declared as 6.0s returned 34.600s and wrote a file with 5.03s of video
    # and 34.600s of audio. That is the Tokyo Drift defect in miniature (255s
    # of video under 1054s of audio).
    #
    # The claimed durations came from the clip loop's cursor arithmetic, so
    # the one thing the offsets must NOT be computed from is the plan.
    from pipeline import probe as _probe
    real: list[float] = []
    for p, claimed in clips:
        st = _probe.streams(Path(p))
        v = st.get("video")
        rd = float(v["duration"]) if v else 0.0
        if rd <= 0:
            console.print(f"[red]xfade: {Path(p).name} has no measurable "
                          f"video stream.[/]")
            sys.exit(1)
        if abs(rd - float(claimed)) > 0.05:
            console.print(
                f"[yellow]xfade: {Path(p).name} claims "
                f"{float(claimed):.3f}s but measures {rd:.3f}s "
                f"({rd - float(claimed):+.3f}s) - using the MEASURED "
                f"length.[/]")
        real.append(rd)
    clips = [(p, real[i]) for i, (p, _c) in enumerate(clips)]

    inputs = []
    for p, _ in clips:
        inputs += ["-i", str(p)]

    vfilters = []
    afilters = []

    # Pin every audio input to the SAME clock the video uses.
    #
    # xfade takes an explicit `offset=`, so the picture lands exactly where the
    # cursor arithmetic says. acrossfade has no offset parameter - it chains on
    # whatever the decoder hands it, and an AAC clip decodes to slightly MORE
    # than its container duration (encoder priming). That surplus is invisible
    # to ffprobe (stream metadata agrees with the video to under a millisecond)
    # but real inside the filtergraph, so every junction leaked ~12-18ms of
    # audio while the picture stayed put. It compounds: Superbad's narration
    # finished 1.7s behind its own footage over 143 junctions, and the shorter
    # films carry the same defect at ~0.7s - present in every render, hidden
    # only by line count. apad+atrim forces each input to exactly the duration
    # the cursor already assumed, so audio and video advance together.
    apre = []
    for i, (_p, d) in enumerate(clips):
        apre.append(f"[{i}:a]apad=whole_dur={d:.3f},atrim=0:{d:.3f},"
                    f"asetpts=PTS-STARTPTS[at{i}]")

    # running offset where the next xfade begins
    prev_v = "0:v"
    prev_a = "at0"
    cumulative = clips[0][1]
    for i in range(1, len(clips)):
        offset = cumulative - XFADE
        vlabel = f"vx{i}"
        alabel = f"ax{i}"
        vfilters.append(
            f"[{prev_v}][{i}:v]xfade=transition=fade:duration={XFADE}:offset={offset:.3f}[{vlabel}]"
        )
        afilters.append(
            f"[{prev_a}][at{i}]acrossfade=d={XFADE}[{alabel}]"
        )
        prev_v = vlabel
        prev_a = alabel
        cumulative += clips[i][1] - XFADE

    filtergraph = ";".join(apre + vfilters + afilters)
    cmd = [
        ff, "-y", *inputs,
        "-filter_complex", filtergraph,
        "-map", f"[{prev_v}]", "-map", f"[{prev_a}]",
        "-c:v", "libx264", "-preset", config.VIDEO_PRESET_INTERMEDIATE,
        "-crf", str(config.VIDEO_CRF_INTERMEDIATE),
        "-pix_fmt", config.VIDEO_PIX_FMT,
        "-c:a", "aac", "-b:a", "192k",
        str(out),
    ]
    _run(cmd, f"xfade chain -> {out.name}")

    # RETURN WHAT THE FILE IS, NOT WHAT THE ARITHMETIC SAID. This used to
    # `return cumulative`, and that single line is why a truncated film could
    # be reported as 17.6 minutes long: every downstream consumer - the
    # caption clock, the music track length, the position gate, the final
    # `-t` - was handed a number computed in this loop rather than measured
    # off the result. _position_offsets' own docstring records the same lesson
    # about the check it replaced: "Both sides came from clips[]; neither
    # looked at the rendered file."
    st = _probe.streams(out)
    v, a = st.get("video"), st.get("audio")
    if v is None:
        console.print(f"[red]xfade: {out.name} has no video stream.[/]")
        sys.exit(1)
    measured = float(v["duration"])
    if abs(measured - cumulative) > 0.25:
        console.print(
            f"[red]xfade: {out.name} should be {cumulative:.3f}s but its "
            f"video stream is {measured:.3f}s ({measured - cumulative:+.3f}s)."
            f"[/]")
        console.print("[red]  The picture was dropped somewhere in the "
                      "chain. Refusing to build a film on it.[/]")
        sys.exit(1)
    if a is not None and abs(a["duration"] - measured) > 0.25:
        console.print(
            f"[red]xfade: {out.name} video is {measured:.3f}s but audio is "
            f"{a['duration']:.3f}s "
            f"({a['duration'] - measured:+.3f}s).[/]")
        sys.exit(1)
    return measured


POSITION_TOLERANCE = 0.25   # seconds a line may sit off its timeline slot


def _position_offsets(ff: str, final: Path, timeline: list, narration: list,
                      n_probe: int = 3, intro_offset: float = 0.0) -> list:
    """Does the narration actually LAND where timeline.json says it does?

    Cross-correlates a line's own TTS audio against the finished mix, near the
    position timeline.json claims for it. Returns [(line_id, want, measured,
    delta)] for the sampled lines, or [] if the check could not run.

    `intro_offset` is the length of the beat-cut intro block prepended to
    `final` AFTER the in-memory `timeline` was built. The timeline's `start`
    values are measured against a film with nothing on the front, but `final`
    has the intro on it, so each line actually sits `intro_offset` seconds
    later in the file. The search is centred on `want + intro_offset` so the
    check measures REAL drift (audio vs video chains) rather than re-reporting
    the constant intro shift as drift. When no intro is prepended this is 0.0
    and the behaviour is unchanged. `want` returned to the caller stays the
    unshifted slot, so the reported delta is drift about zero, not about the
    offset.

    This replaced a duration comparison that could never fail. The old check
    computed `sum(clip durations) - XFADE*(n-1)` and compared it to the total
    returned by _xfade_chain - which is that same expression, accumulated in a
    loop. Both sides came from clips[]; neither looked at the rendered file, so
    the 5% tolerance was decorative. It stayed green while narration drifted
    1.7s out of step with its own footage.

    A duration check is the wrong instrument regardless of where it reads from:
    in that same broken render the audio stream measured 1031.056s against a
    predicted 1031.056s. The total was right the whole time - the surplus was
    absorbed at the tail while the interior slid. Only POSITION shows it.

    Deliberately not ASR: this decodes waveforms and correlates energy
    envelopes, so it is deterministic, needs no model, and costs a few seconds.
    """
    try:
        import numpy as np
    except ImportError:
        return []

    sr = 160000 // 10          # 16 kHz
    win, pad, probe = 160, 6.0, 2.5

    def decode(path, t=None):
        cmd = [ff, "-v", "error", "-i", str(path)]
        if t is not None:
            cmd += ["-t", f"{t:.3f}"]
        cmd += ["-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
        raw = subprocess.run(cmd, capture_output=True).stdout
        return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0

    def envelope(x):
        n = len(x) // win * win
        if n < win * 4:
            return None
        e = np.abs(x[:n]).reshape(-1, win).mean(axis=1)
        return (e - e.mean()) / (e.std() + 1e-9)

    # The in-memory timeline uses "start"; timeline.json renames it "out_start"
    # on the way to disk. Accept either so this helper also works standalone
    # against a written timeline.json.
    def _slot(t):
        v = t.get("start", t.get("out_start"))
        return None if v is None else float(v)

    audio_by_id = {lid: p for lid, p, _d in narration}
    # Montage entries carry no id and are skipped - they have no single
    # narration file to correlate against.
    usable = [t for t in timeline
              if t.get("id") in audio_by_id and _slot(t) is not None]
    if len(usable) < 2:
        return []

    # head, middle and tail: accumulation is invisible at the head by
    # definition, so the tail sample is the one that matters.
    idxs = sorted({0, len(usable) // 2, len(usable) - 1})
    if n_probe > 3 and len(usable) > n_probe:
        step = max(1, len(usable) // n_probe)
        idxs = sorted({*idxs, *range(0, len(usable), step)})

    try:
        full = decode(final)
    except Exception:
        return []
    if len(full) < sr:
        return []

    out = []
    for i in idxs:
        t = usable[i]
        want = _slot(t)
        # Where the line actually sits in `final`: the timeline slot plus the
        # prepended intro's length. Search is centred here; the reported delta
        # is still (measured - here), i.e. drift about the position the render
        # honours, so a correct render reads ~0 and real drift still shows.
        want_in_file = want + intro_offset
        ref = envelope(decode(audio_by_id[t["id"]], t=probe))
        if ref is None:
            continue
        lo = max(0.0, want_in_file - pad)
        seg = full[int(lo * sr): int((want_in_file + pad + probe) * sr)]
        hay = envelope(seg)
        if hay is None or len(hay) <= len(ref) + 2:
            continue
        c = np.correlate(hay, ref - ref.mean(), mode="valid")
        measured = lo + int(np.argmax(c)) * win / sr
        out.append((t["id"], want, measured, measured - want_in_file))
    return out


def _split_points(window_dur: float, clip_len: float, cuts: list,
                  start: float = 0.0, end: float = 0.0,
                  censor_region=None) -> list:
    """Wrapper that refuses to split a REGION-CENSORED clip.

    A censor region describes one shot's framing. Split the clip across other
    shots and the box no longer covers the content - and the alternatives are
    both unacceptable: no blur at all, or a full-frame blur that loses the
    footage. So a region-censored clip simply does not get split; it renders as
    one shot, with its region blurred, which is what the region was drawn for.
    """
    if censor_region is not None:
        return []
    return _split_points_impl(window_dur, clip_len, cuts, start, end)


def _split_points_impl(window_dur: float, clip_len: float, cuts: list,
                  start: float, end: float) -> list:
    """2f: pick 2-3 CONTIGUOUS sub-windows of [start, end] at real cut points.

    Only splits when the clip will play longer than SPLIT_CLIP_SEC. The genre's
    own floor is clips under 8 seconds; a 12-second line on one shot is twelve
    seconds of the same frame drifting under a zoom.

    Splits only at timestamps that are ACTUAL CUTS in the source, so the result
    is a real shot change rather than a jump cut inside one continuous take.
    If the window contains no usable interior cut, this returns [] and the line
    renders as a single clip - a missing cut is a reason not to split, not a
    reason to invent a boundary.
    """
    thr = float(getattr(config, "SPLIT_CLIP_SEC", 8.0))
    if clip_len <= thr or window_dur <= 0.5 or not cuts:
        return []
    inner = [c for c in cuts if start + 1.2 < c < end - 1.2]
    if not inner:
        return []

    # EVERY SUB-SHOT MUST BE ABLE TO FILL ITS OWN SHARE OF THE SCREEN TIME.
    #
    # THE DEFECT: each sub-shot gets an EQUAL share, clip_len/n, but this
    # function used to pick the cut NEAREST the ideal boundary without asking
    # whether the resulting sub-shot had that much footage in it. On line 24 it
    # chose a cut 2.173s into a 13.583s window, so a 2.173s sub-shot was asked
    # for 4.363s of screen time. The builder can reach 2.173 + 0.5 read-ahead
    # + 0.3 of capped clone = 2.973s and `trim` cannot extend, so the clip was
    # written 1.39s short - and a short clip truncates the whole film in the
    # xfade chain. Five lines in this draft were affected.
    #
    # The guarantee is made against the segment's OWN footage, not against
    # footage + read-ahead + clone: relying on cloned frames to meet a
    # duration is how the freeze defects happened in the first place.
    #
    # Feasible whenever window_dur >= clip_len, which is exactly when the line
    # is not being slowed - and a slowed line is never split, because
    # clip_len > window_dur there leaves no room for n shares.
    for want in (3, 2) if clip_len > thr * 2 else (2,):
        share = clip_len / want
        bounds = [start]
        ok = True
        for i in range(1, want):
            remaining = want - i          # segments still to come after this
            lo = bounds[-1] + share       # this segment must cover its share
            hi = end - share * remaining  # ...and leave room for the rest
            feasible = [c for c in inner if lo - 1e-6 <= c <= hi + 1e-6]
            if not feasible:
                ok = False
                break
            ideal = start + window_dur * i / want
            bounds.append(min(feasible, key=lambda c: abs(c - ideal)))
        if not ok:
            continue
        bounds.append(end)
        segs = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
        if len(segs) == want and all(b - a >= max(1.2, share) - 1e-6
                                     for a, b in segs):
            return segs
    # No set of real cuts can carry equal shares - so do not split. A single
    # clip is the old behaviour and is always correct; an under-fed sub-shot is
    # not.
    return []


def _clip_signature(source: Path, start: float, end: float, hold: float,
                    idx: int, crop_top: float, narr_dur: float,
                    audio_path: Path, censor: str = "none",
                    censor_region=None, exposure: float = 0.0, silence=None,
                    lead_in: float = 0.0, film_audio: bool = False,
                    pre_reveal: bool = False,
                    split_segments: list | None = None,
                    film_src: Path | None = None,
                    film_speaks: bool = False) -> str:
    """Hash everything that determines a clip's pixels+audio, for caching.

    `film_src` is in the key because switching to (or from) the no-vocals stem
    changes every clip's AUDIO while leaving its pixels identical. Without it,
    turning stems on would serve the whole film from cache with the dialogue
    still in it - the fix would appear to do nothing.
    """
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
        # Lead-in changes both the clip's LENGTH and where the voice sits in it,
        # so every clip cached before 2026-08-26 must be rebuilt, not reused.
        f"leadin={float(lead_in):.3f}",
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
        # WHICH audio the film is heard through. The no-vocals stem leaves the
        # pixels untouched and changes every clip's sound, so it has to be here
        # or enabling stems serves the old dialogue-laden audio from cache.
        f"filmsrc={'none' if film_src is None else Path(film_src).name}",
        f"filmspeaks={bool(film_speaks)}",
        # Also pinned: the scaler and intermediate CRF both change pixels.
        f"scaler={config.VIDEO_SCALER}",
        f"crfi={config.VIDEO_CRF_INTERMEDIATE}",
        # 2026-10-20 FILM AUDIO. The clip's audio track now contains the film's
        # own sound as well as the voice, so every level here changes the
        # rendered audio. Without these in the signature, a cached clip from
        # before this change would be reused silently and the render would come
        # out with narration-only audio while the log claimed success.
        f"film={bool(film_audio)}:{bool(config.FILM_AUDIO_ENABLE)}:"
        f"{float(config.FILM_AUDIO_DB):.2f}:"
        f"{float(config.FILM_AUDIO_HOLD_DB):.2f}",
        f"prerev={bool(pre_reveal)}:"
        f"{float(config.FILM_AUDIO_PRE_REVEAL_DB):.2f}:"
        f"{float(config.FILM_AUDIO_PRE_REVEAL_SEC):.2f}",
        # 2f: the sub-windows change the PICTURE, so a cached one-shot clip
        # must not be reused for a split line.
        "split=" + ("|".join(f"{a:.2f}-{b:.2f}" for a, b in (split_segments or []))
                    or "none"),
    ]
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]


def region_to_output(censor_region, src_w: int, src_h: int):
    """Map a censor region from SOURCE pixels to OUTPUT pixels.

    CensorRegion is documented as "pixel coordinates in the ORIGINAL source
    frame" - which is the only sensible contract, because whoever draws the box
    is looking at a source frame. But the filter graph applies the crop AFTER
    the scale+pad to the output canvas, and clamped against OUTPUT_WIDTH /
    OUTPUT_HEIGHT. So the documented units and the implemented units disagreed,
    and every partial blur was placed wrong.

    On tokyodrift2006 the error is gross, not subtle: the source is 1280x544,
    scaled by 1.5 to 1920x816 and padded with 132px bars. A region authored at
    source y=25 was being applied at output y=25 - inside the top black bar,
    blurring nothing and leaving the content clear.

    Returns (x, y, w, h) in output pixels, clamped to the canvas.
    """
    import config as _c
    W, H = int(_c.OUTPUT_WIDTH), int(_c.OUTPUT_HEIGHT)
    try:
        sw, sh = int(src_w), int(src_h)
    except (TypeError, ValueError):
        sw = sh = 0
    if sw <= 0 or sh <= 0:
        # Unknown source size: assume the coordinates are already in output
        # space (legacy behaviour) rather than guessing a transform.
        x, y = int(censor_region.x), int(censor_region.y)
        w, h = int(censor_region.width), int(censor_region.height)
    else:
        f = min(W / sw, H / sh)
        ox = (W - sw * f) / 2.0
        oy = (H - sh * f) / 2.0
        x = int(round(int(censor_region.x) * f + ox))
        y = int(round(int(censor_region.y) * f + oy))
        w = int(round(int(censor_region.width) * f))
        h = int(round(int(censor_region.height) * f))
    x = max(0, min(x, W - 1))
    y = max(0, min(y, H - 1))
    w = max(1, min(w, W - x))
    h = max(1, min(h, H - y))
    return x, y, w, h


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

    # Source pixel dimensions. Needed to place a censor region: the box is
    # authored against a SOURCE frame while the blur is applied after
    # scale+pad, so the two spaces have to be reconciled (region_to_output).
    # Resolved HERE, at the top, because the censor policy check runs long
    # before the quality report does - defining it next to that report left it
    # unbound on every render with a flagged shot.
    from pipeline import quality as _q0
    _hd0 = _q0.source_headroom(ffp, source)
    src_wh = ((_hd0.get("src_w"), _hd0.get("src_h"))
              if _hd0.get("src_w") else None)

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

    # ---- resolve a line to the catalogued shot its footage came from ---------
    # RULE A3 anchors a line's clip_start to the NARRATED MOMENT, not to the
    # shot start, so a correctly anchored line's (clip_start, clip_end) is not a
    # key in shots.json at all. Exact-key lookup therefore returned "none" and
    # the line rendered UNCENSORED, silently: measured on superbad2007, 11 shots
    # carried a censor flag, 9 had lines bound to them, and exactly 1 rendered
    # blurred. This is the same defect as the binding_audit exact-key lookup -
    # same cause, second location - so it takes the same containment fallback.
    _shot_windows: list = []
    _shot_keys: set = set()
    try:
        sp = pdir / "shots.json"
        if sp.exists():
            import json as _json2
            for s in _json2.loads(sp.read_text(encoding="utf-8-sig")).get("shots", []):
                cs, ce = s.get("clip_start"), s.get("clip_end")
                if cs and ce:
                    _shot_keys.add((cs, ce))
                    try:
                        _shot_windows.append((parse_ts(cs), parse_ts(ce), (cs, ce)))
                    except Exception:
                        pass
            _shot_windows.sort()
    except Exception:
        pass

    def _host_key(cs, ce):
        """Exact shot key if it exists, else the shot window containing cs."""
        k = (cs, ce)
        if k in _shot_keys or not cs:
            return k
        try:
            t = parse_ts(cs)
        except Exception:
            return k
        for a, b, kk in _shot_windows:
            if a - 0.6 <= t < b:
                return kk
        return k

    # ---- whole-video censor coverage ----------------------------------------
    # Every footage path records what it puts on screen into `used_footage`,
    # and the audit below compares that against the flagged set. "No line
    # bound" is NOT an all-clear: the intro montage, the film-intro block and
    # pool/montage windows all put footage in the video that no line owns.
    from pipeline import censor as _censor
    _flagged = _censor.flagged_shots(pdir)
    used_footage = _censor.UsedFootage()
    # Policy on the flags themselves, before anything is built: a flag with no
    # region would blur the whole frame, which loses the shot while still
    # costing the runtime. Swap the shot instead.
    _cen_policy = _censor.criteria_problems(
        pdir, *(src_wh or (0, 0)))
    if _cen_policy:
        console.print(f"[red][CENSOR-POLICY][/] {len(_cen_policy)} flag(s) "
                      f"break the blur policy:")
        for _p in _cen_policy:
            console.print(f"[red]    {_p}[/]")
        console.print(f"[yellow]  Criteria: blur only "
                      f"{', '.join(getattr(config, 'CENSOR_CRITERIA', ()))} - "
                      f"not crashes, ordinary violence, clothed kissing or "
                      f"revealing clothing.[/]")
        sys.exit(1)

    # ---- census: how many LINES will actually render censored ---------------
    # The old line counted entries in shots.json, i.e. INTENT. It printed
    # "11 shot(s) flagged for blur" on a render that blurred one of them, which
    # is precisely the reassurance you do not want from a content gate.
    _cen_lines, _cen_shots_hit, _cen_unresolved = 0, set(), []
    for _ln in draft["lines"]:
        _cs, _ce = _ln.get("clip_start"), _ln.get("clip_end")
        if not _cs:
            continue
        _hk = _host_key(_cs, _ce)
        if censor_by_clip.get(_hk, "none") != "none":
            _cen_lines += 1
            _cen_shots_hit.add(_hk)
        else:
            # A line sitting inside a flagged shot's window that still resolves
            # to "none" would mean the fallback failed - report, never swallow.
            try:
                _t = parse_ts(_cs)
                for _a, _b, _kk in _shot_windows:
                    if _a - 0.6 <= _t < _b and censor_by_clip.get(_kk, "none") != "none":
                        _cen_unresolved.append((_ln.get("id"), _kk))
                        break
            except Exception:
                pass

    if censor_by_clip:
        extra = f" ({n_partial} partial-region)" if n_partial else ""
        console.print(f"[cyan]Censor:[/] {_cen_lines} line(s) will render blurred"
                      f"{extra}, from {len(_cen_shots_hit)}/{len(censor_by_clip)} "
                      f"flagged shot(s)")
        # NOTE: the "no line bound" list used to be printed here as a warning.
        # It is now resolved by the whole-video censor audit at the end of the
        # render, which can tell "not in the video" (fine) from "in the video
        # and unblurred" (a stop) - a distinction this message could not make
        # and which made it read like an all-clear.
        if _cen_unresolved:
            console.print(f"[red]  {len(_cen_unresolved)} line(s) sit inside a "
                          f"flagged shot but resolved to no censor - this is a "
                          f"resolver failure, do not publish:[/]")
            for _lid, _kk in _cen_unresolved[:8]:
                console.print(f"[red]      line {_lid} -> shot {_kk[0]}[/]")
    if silence_by_clip:
        console.print(f"[cyan]Silence:[/] {len(silence_by_clip)} silent shot(s) "
                      f"(music swells to {int(config.SILENCE_MUSIC_VOLUME*100)}%)")
    if exposure_by_clip:
        console.print(f"[cyan]Exposure:[/] {len(exposure_by_clip)} dark shot(s) "
                      f"lifted for visibility")

    # absolute (start, end) windows on the timeline where music should swell.
    silence_windows: list[tuple[float, float]] = []
    # A <film_speaks> unit is NOT a music swell. Both kinds of unit carry no
    # narration, so both used to land in silence_windows - and a hold SWELLS
    # the music to SILENCE_MUSIC_VOLUME. That made the one moment the film is
    # given the floor the loudest the music ever gets, which is why both units
    # were inaudible. They are tracked separately and ducked, not swelled.
    film_speaks_windows: list[tuple[float, float]] = []
    # absolute timeline positions of <reveal> lines, for the music drop.
    reveal_positions: list[float] = []

    # ---- does the source actually HAVE an audio stream? ------------------
    # FILM_AUDIO_ENABLE is an intention; this is the fact. A source with no
    # audio track would make every clip's filter graph reference a stream that
    # does not exist and ffmpeg would fail on clip 1 - so ask once, say the
    # answer out loud, and fall back to narration-only if there is nothing to
    # mix. D-GREEN: an audit missing an input has to say so.
    # ---- STEMS: the film without its dialogue -------------------------------
    # Separated once per project and cached. Used everywhere the narrator is
    # speaking and inside every hold; the original mix is read only inside a
    # <film_speaks> unit. A missing separation is a STOP, not a silent fallback
    # to the un-separated mix - see config.FILM_AUDIO_REQUIRE_STEMS.
    film_stem = None
    if config.FILM_AUDIO_ENABLE and getattr(config, "FILM_AUDIO_USE_STEMS", False):
        from pipeline import stems as _stems
        film_stem, _snote = _stems.resolve(project)
        if film_stem is None:
            _ok, _why = _stems.available()
            if getattr(config, "FILM_AUDIO_REQUIRE_STEMS", True):
                console.print(
                    f"[red]Film audio: no no-vocals stem ({_why}).[/]\n"
                    f"  Without separation the film's DIALOGUE plays under "
                    f"every line of narration, which is the defect stems exist "
                    f"to remove.\n"
                    f"  Install:  {_stems.install_hint()}\n"
                    f"  Or set config.FILM_AUDIO_REQUIRE_STEMS = False to "
                    f"render with the film audio MUTED instead (no dialogue, "
                    f"but no engines either).")
                sys.exit(1)
            console.print(
                "[yellow]Film audio: MUTED[/] - no no-vocals stem available "
                "and FILM_AUDIO_REQUIRE_STEMS is False. The engines and "
                "impacts are lost along with the dialogue.")

    has_film_audio = False
    _fa_ids: set = set()
    if config.FILM_AUDIO_ENABLE:
        try:
            _pr = subprocess.run(
                [ffp, "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "stream=codec_type",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(source)],
                capture_output=True, text=True)
            has_film_audio = ("audio" in (_pr.stdout or ""))
        except Exception as _e:                            # pragma: no cover
            has_film_audio = False
        if has_film_audio:
            # WHICH LINES. `has_film_audio` is a capability ("the source has a
            # track"), not a decision - it used to be treated as both, so the
            # stem played under all 111 lines. Separation artefacts under a
            # dialogue scene buy nothing: the dialogue is exactly what was
            # removed, so what is left is smeared room tone under the
            # narrator. Under a race they sit beneath the engines that are the
            # point of the shot.
            from pipeline import stems as _stemsmod
            _fa_ids = _stemsmod.film_audio_lines(draft)
            console.print(
                f"[cyan]Film audio:[/] restricted to "
                f"{'/'.join(config.FILM_AUDIO_TAGS)} runs of "
                f"{config.FILM_AUDIO_MIN_RUN}+ lines - "
                f"{len(_fa_ids)} of {len(draft.get('lines') or [])} line(s). "
                f"Everywhere else the mix is narration + music only.")
            # Say WHICH audio. This line used to read "source audio mixed
            # under the voice", which was true before stems existed and
            # actively misleading afterwards: a reader checking whether the
            # dialogue fix had taken effect saw a message describing the
            # behaviour it replaced. Verified by capturing the real ffmpeg
            # command - with a stem the film-audio chain reads [N:a] (the stem
            # input), not [0:a] (the source's own track).
            _src_label = ("the NO-VOCALS stem" if film_stem is not None
                          else f"{source.name}'s own track (UN-SEPARATED: "
                               f"dialogue will be audible)")
            console.print(
                f"[cyan]Film audio:[/] {_src_label} mixed under the voice at "
                f"{config.FILM_AUDIO_DB:.0f} dB "
                f"({config.FILM_AUDIO_HOLD_DB:.0f} dB inside holds, "
                f"{config.FILM_AUDIO_PRE_REVEAL_DB:.0f} dB for "
                f"{config.FILM_AUDIO_PRE_REVEAL_SEC:.1f}s before a reveal)")
            if film_stem is not None:
                console.print(
                    "[dim]    the original mix is read ONLY inside a "
                    "<film_speaks> unit - everywhere else the characters are "
                    "silent and the engines are not.[/]")
        else:
            console.print(
                "[yellow]Film audio:[/] FILM_AUDIO_ENABLE is on but "
                f"{source.name} has NO audio stream - clips will carry "
                "narration only. This is the condition every render before "
                "2026-10-20 shipped in silently.")
    else:
        console.print("[dim]Film audio: disabled in config.[/]")

    # ---- CAPACITY PRE-FLIGHT, before a single clip is built -----------------
    # The binding contract used to be enforced inside the clip loop, so the
    # FIRST overrunning line raised BindingViolation and the rest stayed
    # invisible - a 19-line problem presented as one line, nineteen times. All
    # the narration exists by now, so the question can be answered exactly, for
    # every line, here. The in-loop check stays as a backstop (a cached clip
    # could otherwise bypass this), but it should never be the thing that fires.
    # ---- what the source can actually fill, said out loud -------------------
    from pipeline import quality as _q
    _q.report_source(ffp, source)

    from pipeline import preflight as _pf
    # If any line's audio no longer matches its text, this render is being run
    # against a draft whose narration was regenerated - judging the old audio
    # would report overruns that no longer exist. In a normal render the TTS
    # pass has already re-synthesized them, so this is a safety net for a
    # render driven from pre-existing files.
    _stale = _pf.stale_audio(draft, pdir)
    if _stale:
        console.print(f"[yellow]Pre-flight:[/] {len(_stale)} line(s) have audio "
                      f"that does not match their current text "
                      f"({_stale[:10]}{'...' if len(_stale) > 10 else ''}) - "
                      f"not judging those; they re-synthesize on this run.")
    _pf_find = _pf.capacity_findings(draft, narration, ffp, skip_ids=_stale)
    if not _pf.report(_pf_find, project):
        sys.exit(1)

    _cutlist: list = []
    try:
        from pipeline import cuts as _cutsmod
        _cutlist = sorted(float(c) for c in (_cutsmod.load_cuts(project) or []))
    except Exception as _e:
        _cutlist = []
    if _cutlist:
        console.print(f"[cyan]Clip splitting:[/] lines over "
                      f"{float(getattr(config, 'SPLIT_CLIP_SEC', 8.0)):.0f}s "
                      f"are cut across 2-3 shots ({len(_cutlist)} cuts available)")
    else:
        console.print("[yellow]Clip splitting:[/] no cut list - long lines stay "
                      "on one shot. Splitting without real cut points would "
                      "make jump cuts inside a single take.")

    # ---- SHORT-CLIP PRE-FLIGHT: dry-compute every clip, before encoding -----
    # "Does the narration fit the window" and "can the PICTURE supply the clip"
    # are different questions, and only the first was being asked. clip_024
    # claimed 8.726s and its video stream was 7.367s: the builder splits a long
    # line across cuts and gives each sub-shot an EQUAL share of screen time,
    # and the splitter had picked a cut 2.173s into the window, so a 2.173s
    # sub-shot was asked for 4.363s. `trim` cannot extend and the clone is
    # capped, so the clip came out short - and a short clip truncates the whole
    # film in the xfade chain.
    #
    # The per-clip verification in _verify_clip catches this, but it stops at
    # the FIRST offender after however many minutes of encoding it took to
    # reach it. Five lines in this draft were short, which is five sequential
    # renders to find them one at a time. So compute every clip's real reach
    # here, from the same shared formula the builder uses, and list all of them
    # in one pass before a single frame is encoded.
    from pipeline import footprint as _fpmod
    _sc_durs = {lid: d for lid, _p, d in narration}
    # A region-censored clip is never split (the box describes one shot's
    # framing), so the reach calculation has to know which lines carry one or
    # it will model a split that will not happen.
    _sc_regions = {}
    for _ln in draft["lines"]:
        _k = (_ln.get("clip_start"), _ln.get("clip_end"))
        if _k in region_by_clip:
            _sc_regions[_ln.get("id")] = region_by_clip[_k]
    _sc_bad = _fpmod.short_clips(draft, _sc_durs, _cutlist,
                                 regions=_sc_regions)
    if _sc_bad:
        console.print(
            f"[red][SHORT-CLIP][/] {len(_sc_bad)} line(s) would be built with "
            f"a video stream shorter than the clip asks for:")
        console.print(f"[red]  {'line':>5} {'needs':>8} {'reach':>8} "
                      f"{'short':>7}  why[/]")
        for _b in _sc_bad:
            console.print(
                f"[red]  {_b['line_id']:>5} {_b['required']:>8.3f} "
                f"{_b['reach']:>8.3f} {_b['short_by']:>7.3f}  {_b['why']}[/]")
        console.print("[red]  A short clip is invisible until the picture "
                      "stops: the xfade chain lays the next clip past the end "
                      "of this one and the film loses everything after it. "
                      "Widen the window, or re-point the line so its cuts can "
                      "carry equal shares.[/]")
        sys.exit(1)
    console.print(f"[dim][SHORT-CLIP] all {len(_sc_durs)} narrated clip(s) "
                  f"can supply their full length.[/]")

    # ---- ONE NARRATOR: measure the real audio before building anything ------
    # Steering is a request to a model, not a knob on a waveform, so the only
    # honest check that the voice is consistent is to measure what came back.
    # Runs here, next to the capacity pre-flight, because both answer questions
    # about the narration that only become answerable once it exists.
    from pipeline import voice_check as _vc
    _vc_cue_bad = []
    try:
        from pipeline.tts import DEFAULT_PROVIDER
        from pipeline.tts_providers import all_providers
        _prov = all_providers().get(DEFAULT_PROVIDER)
        if _prov is not None:
            _vc_cue_bad = _vc.audit_cues(_prov) + _vc.rate_band_violations(_prov)
    except Exception:
        _vc_cue_bad = []
    if _vc_cue_bad:
        console.print("[red][VOICE-CUES][/] the delivery mapping breaks the "
                      "one-narrator contract:")
        for _b in _vc_cue_bad:
            console.print(f"[red]    {_b}[/]")
        sys.exit(1)

    # ---- [VOICE-RATE-DRIFT] the voice must still hit the target pace -------
    # The word budget everywhere assumes config.TARGET_WPM. If the voice has
    # drifted off it - or has never been measured - every budget in the
    # pipeline is fiction, which is exactly how a 17-minute recap became a
    # 22-minute one without anything reporting a problem.
    _rd_ok, _rd_msg = _vc.rate_drift()
    if _rd_ok:
        console.print(f"[cyan]Voice rate:[/] {_rd_msg}")
    else:
        console.print(f"[red][VOICE-RATE-DRIFT][/] {_rd_msg}")
        sys.exit(1)
    if not _vc.report(_vc.analyse(_vc.measure(draft, narration, ffp,
                                              skip_ids=_stale)), project):
        sys.exit(1)

    # ---- cut list, for 2f picture splitting ------------------------------
    # Splitting only ever happens AT A REAL CUT. With no cut data, long lines
    # render as single clips - which is the old behaviour, and is correct: a
    # missing cut list is a reason not to split, not a reason to invent a
    # boundary inside a continuous take.
    # ---- which clip sits immediately BEFORE a <reveal> line? -------------
    # That clip's tail gets the film audio raised, so the reveal lands out of
    # the film's own sound rather than out of nothing.
    _rev_prev_ids = set()
    _prev_id = None
    for _ln in draft["lines"]:
        if _ln.get("delivery") == "reveal" and _prev_id is not None:
            _rev_prev_ids.add(_prev_id)
        _prev_id = _ln.get("id")

    console.print("[cyan]Building clips (with baked narration)...[/]")
    clips: list[tuple[Path, float]] = []
    timeline: list[dict] = []
    boundaries: list[float] = []
    cursor = 0.0  # start time of current clip on the overlapped timeline
    n_pool = 0
    n_cached = 0
    n_over_montage = 0
    # Gap 3 SILENCE lines build a clip but carry no narration audio and no
    # caption window, so they are deliberately absent from BOTH `narration` and
    # `timeline`. RENDER-CHECK has to know how many there were, or it reports
    # every silence beat as a count mismatch (it fired on Superbad's two).
    n_silence = 0

    for idx, ln in enumerate(draft["lines"]):
        lid = ln["id"]

        # A line spoken OVER THE MONTAGE has no clip window and is not a clip
        # here - it is baked into the intro block, which gets prepended to the
        # finished film below. Rendering it in this loop would need a shot to
        # bind to, which is exactly what the no-frame-description rule forbids
        # it from having.
        #
        # film_intro lines are the SAME CASE and were missing from this test:
        # they are spoken over the prepended intro block, carry no clip window
        # by schema rule (draft.py rejects a film_intro line WITH one), and are
        # baked by intro._build_film_intro_segment. Falling through here reached
        # `parse_ts(ln["clip_start"])` below and crashed the first full render
        # with KeyError 'clip_start'. Any line type that is rendered by the
        # intro builder must be skipped here - see INTRO_OWNED.
        if any(ln.get(k) for k in INTRO_OWNED):
            n_over_montage += 1
            continue

        # ---- Gap 3 SILENCE line: the LINE itself carries the silence ---------
        # A silence line has narration_silence_seconds (set on the draft line,
        # mirroring its silence shot) and no narration. Build a visual-only hold
        # and record the timeline window so music can swell. NOTE: detection is
        # per-LINE, not per-clip - a normal framing line may bind the SAME clip
        # as a silence shot (e.g. a lead-in held just before the silence) and
        # must keep its narration.
        _skey = (ln.get("clip_start"), ln.get("clip_end"))
        # <film_speaks>: same wordless clip as a silence hold, but the film's
        # audio plays at FULL level instead of being held under a music swell.
        # Handled here rather than as a separate branch because everything
        # except the audio level is identical - and a second near-copy of the
        # silence path is how the two would drift apart.
        _fs_secs = ln.get("film_speaks_seconds")
        sil_secs = ln.get("narration_silence_seconds")
        if _fs_secs is not None:
            sil_secs = float(_fs_secs)
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
                                  exposure=exposure, silence=sil_secs,
                                  film_audio=(has_film_audio and lid in _fa_ids),
                                  film_src=film_stem,
                                  film_speaks=(_fs_secs is not None))
            cached = cache_dir / f"{sig}.mp4"
            reused = False
            if not force_clips and cached.exists():
                import shutil
                shutil.copy2(cached, cout)
                clip_len = float(sil_secs)
                reused = True
                n_cached += 1
                # VERIFY THE CACHE HIT. A cached clip is copied in and its
                # length is taken from the formula, never from the file - so a
                # clip built short under older rules is served silently
                # forever. Nine such clips are in this project's cache, the
                # worst with 3.0s less video than audio.
                _verify_clip(cout, clip_len, f"cached hold clip (line {lid})")
            else:
                clip_len = _build_silence_clip(ff, source, start, end, cout,
                                               sil_secs, idx, crop_top,
                                               censor, censor_region, exposure,
                                               film_audio=(has_film_audio
                                                           and (lid in _fa_ids
                                                                or _fs_secs is not None)),
                                               film_speaks=(_fs_secs is not None),
                                               film_src=film_stem, src_wh=src_wh)
                try:
                    import shutil
                    shutil.copy2(cout, cached)
                except Exception:
                    pass
            clips.append((cout, clip_len))
            boundaries.append(cursor)
            # A hold shows [start, start+clip_len) - NOT [start, end).
            # _build_silence_clip ignores its `end` argument: it reads `-ss
            # start -t clip_len`, so a hold whose authored duration exceeds its
            # window keeps playing into the FOLLOWING shots. Recording [start,
            # end) here meant the censor audit never looked at the footage a
            # long hold actually reaches, so a flagged shot just after a hold's
            # window could play unblurred. Record what is really on screen.
            _hold_end = max(float(end), float(start) + float(clip_len))
            used_footage.add(start, _hold_end, "hold/film_speaks clip",
                             blurred=(censor != "none"), line_id=lid,
                             out_a=cursor, out_b=cursor + clip_len)
            if _fs_secs is not None:
                film_speaks_windows.append((cursor, cursor + clip_len))
            else:
                silence_windows.append((cursor, cursor + clip_len))
            n_silence += 1
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
        # how much footage this line needs; includes the lead-in so a pool
        # window is long enough to cover the picture-before-voice beat too.
        need = max(LEAD_IN + narr_dur + GAP, hold)

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
            # _build_montage_clip takes NO censor argument: every segment in a
            # montage renders clear. Record them as unblurred so the audit
            # catches a flagged shot that was cut into a montage - the clip
            # loop's (clip_start, clip_end) lookup never saw these windows.
            for _si, (_sa, _sb) in enumerate(segs):
                # each segment plays for its share of the montage clip
                _share = clip_len / max(1, len(segs))
                used_footage.add(_sa, _sb, "montage segment",
                                 blurred=False, line_id=lid,
                                 out_a=cursor + _si * _share,
                                 out_b=cursor + (_si + 1) * _share)
            # narration now starts LEAD_IN after the clip does (see adelay).
            timeline.append({"start": cursor + LEAD_IN,
                             "end": cursor + LEAD_IN + narr_dur,
                             "text": ln["narration"]})
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
            _narr_need = _lead_for(narr_dur, _shot_dur) + narr_dur + GAP
            if _shot_dur > 0 and _narr_need > _shot_dur * BINDING_SLOWDOWN_MAX:
                raise BindingViolation(
                    line_id=lid, narration_dur=_narr_need,
                    shot_dur=_shot_dur, capacity=_shot_dur * BINDING_SLOWDOWN_MAX)

        # censor level for this clip (from shots.json; default "none"). Pool/
        # montage clips are not censored here (no shots.json mapping for them).
        _ckey = (ln.get("clip_start"), ln.get("clip_end"))
        # Censor resolves through the host shot (see _host_key): an A3-anchored
        # line has no exact key, and defaulting to "none" is a silent failure
        # that ships uncensored footage.
        _hkey = _host_key(ln.get("clip_start"), ln.get("clip_end"))
        censor = censor_by_clip.get(_hkey, "none")
        censor_region = region_by_clip.get(_hkey)  # None -> whole-frame blur
        # NOTE: exposure_lift still resolves by EXACT key and carries the same
        # defect - an A3-anchored line inside a DARK shot does not get lifted.
        # Left unchanged here deliberately: it alters the picture of every dark
        # scene and invalidates their clip cache, which is a separate decision
        # from restoring censorship. Measured impact reported alongside this fix.
        exposure = exposure_by_clip.get(_ckey, 0.0)  # DARK-scene lift (0 = none)

        # per-line lead-in, clamped to what this shot can carry. The SAME value
        # is used for the clip, the cache key and the timeline entry - if they
        # ever disagree the captions and the positional gate drift.
        # A <reveal> gets PRE_REVEAL_PAUSE of extra front silence so the line
        # lands out of a gap. Clamped by _lead_for like every other lead, so a
        # tight shot loses the pause rather than failing the binding contract.
        _is_reveal = (ln.get("delivery") == "reveal")
        _extra = float(getattr(config, "PRE_REVEAL_PAUSE", 0.0)) if _is_reveal else 0.0
        lead = _lead_for(narr_dur, max(0.0, end - start), extra=_extra)

        # ---- clip cache: reuse an identical previously-built clip -----------
        _is_pre_reveal = lid in _rev_prev_ids
        # ---- 2f: does this line's picture need splitting? ----------------
        _split = _split_points(end - start, lead + narr_dur + GAP, _cutlist,
                               start, end, censor_region=censor_region)
        sig = _clip_signature(source, start, end, hold, idx, crop_top,
                              narr_dur, audio_path, censor, censor_region, exposure,
                              lead_in=lead, film_audio=(has_film_audio and lid in _fa_ids),
                              pre_reveal=_is_pre_reveal, split_segments=_split,
                              film_src=film_stem)
        cached = cache_dir / f"{sig}.mp4"
        reused = False
        if not force_clips and cached.exists():
            import shutil
            shutil.copy2(cached, cout)
            # must match _build_clip's formula exactly, or a cache hit reports a
            # different length than the file actually is and the timeline drifts.
            clip_len = max(lead + narr_dur + GAP, hold)
            reused = True
            n_cached += 1
            _verify_clip(cout, clip_len, f"cached clip (line {lid})")
        else:
            clip_len = _build_clip(ff, source, start, end, audio_path, narr_dur,
                                   cout, idx, crop_top, hold, censor, censor_region,
                                   exposure, lead_in=lead,
                                   film_audio=(has_film_audio and lid in _fa_ids),
                                   pre_reveal=_is_pre_reveal,
                                   split_segments=_split,
                                   film_src=film_stem, src_wh=src_wh)
            try:
                import shutil
                shutil.copy2(cout, cached)
            except Exception:
                pass
        clips.append((cout, clip_len))
        boundaries.append(cursor)  # absolute start time of this clip
        # Record what this clip actually SHOWS. For a split ("2f") clip that is
        # each sub-window, not the whole [start, end) span - the gaps between
        # sub-windows never reach the screen, so attributing them here would
        # mark flagged footage as "used and blurred" when it was not shown at
        # all. The whole-frame blur is applied after the concat, so when cb > 0
        # every sub-window is covered.
        _blurred = (censor != "none")
        if _split:
            _nsp = len(_split)
            for _si, (_sa, _sb) in enumerate(_split):
                _share = clip_len / max(1, _nsp)
                used_footage.add(_sa, _sb, "clip (split)",
                                 blurred=_blurred, line_id=lid,
                                 out_a=cursor + _si * _share,
                                 out_b=cursor + (_si + 1) * _share)
        else:
            used_footage.add(start, end,
                             "pool clip" if ln.get("pool") else "clip",
                             blurred=_blurred, line_id=lid,
                             out_a=cursor, out_b=cursor + clip_len)

        # caption window: narration starts LEAD_IN after the clip starts (the
        # audio is delayed by adelay in _build_clip), and lasts narr_dur. This
        # is also what _position_offsets checks against, so captions and the
        # positional gate both stay aligned with the voice rather than the cut.
        # `id` / `clip_*` are carried for timeline.json (see below); build_ass
        # ignores the extra keys.
        timeline.append({"start": cursor + lead,
                         "end": cursor + lead + narr_dur,
                         "text": ln["narration"], "id": lid,
                         "clip_start": ln.get("clip_start"),
                         "clip_end": ln.get("clip_end")})
        # Where the reveal's VOICE starts on the finished timeline - the music
        # drop is measured backwards from here, not from the cut.
        if ln.get("delivery") == "reveal":
            reveal_positions.append(cursor + lead)
        cursor += clip_len - XFADE

        held = f" +hold{hold:.0f}s" if hold else ""
        tag = " [dim](cached)[/]" if reused else ""
        # 2f has to be VISIBLE in the log. Scene detection on the finished clip
        # cannot tell my boundary from a cut that was already inside the
        # footage, so the only honest record of what the splitter did is the
        # splitter saying so.
        _sp = ""
        if _split:
            _sp = (" [dim]split %d: %s[/]"
                   % (len(_split),
                      " | ".join(f"{a:.1f}-{b:.1f}" for a, b in _split)))
        console.print(f"  line {lid:>3}: [{src_label:<5}] -> {clip_len:4.1f}s{held}{tag}{_sp}")

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
        # plan_events emits on REVEALS and HOLDS only - the restriction lives
        # there, where the events are decided, not as a screen here.
        sfx_events = sfxmod.plan_events(draft, boundaries)
        if sfx_events:
            _why: dict = {}
            for ev in sfx_events:
                _why[ev.get("why", "?")] = _why.get(ev.get("why", "?"), 0) + 1
            console.print(
                "[cyan]Sound design:[/] "
                + ", ".join(f"{v} on {k}s" for k, v in sorted(_why.items()))
                + " (no whoosh on ordinary cuts)")
        else:
            console.print("[dim]Sound design: no reveals or holds to hit.[/]")

    # ----- CENSOR AUDIT on the story footage, BEFORE anything is encoded -----
    # Every clip/montage/pool/hold window is now recorded, so this can answer
    # the question the old "no line bound" warning could not: is the flagged
    # footage actually IN the video, and is it blurred? Run before the encode
    # so a failure costs nothing and leaves no publishable file behind.
    if _flagged:
        _ca = _censor.audit(_flagged, used_footage)
        if not _censor.report(_ca, used_footage):
            console.print("[red]Render stopped before encoding: flagged "
                          "footage would appear unblurred.[/]")
            sys.exit(1)

    # ----- final: (optional captions), mix music, encode --------------------
    label = ("Burning captions + " if captions else "") + ("mixing music " if music else "") + "encoding..."
    console.print(f"[cyan]{label}[/]")
    final = pdir / "final.mp4"

    # ----- MUSIC: one BED under the whole recap + mood CUES layered on top ---
    # Replaces the per-unit mood-bed switching. pipeline/music.py plans the cues
    # (runs of >=3 same-mood lines, holds after sad/reveal), applies the density
    # caps and rotation, and builds ONE track (bed looped + cues + reveal dips).
    # render.py then sidechains that single track under the voice, exactly as it
    # mixed a mood bed. Every fallback rung is printed by resolve_music.
    from pipeline import music as _music
    # `music` is whatever the CALLER supplied (--music download, or recap.py's
    # auto-discovered music.mp3). It is handed over as the LEGACY candidate
    # only: projects/<name>/music/ takes precedence, and if there is no bed but
    # there are cues, this track is promoted to be the bed so the cues survive.
    _bed_used, _prebuilt, _mnote = _music.resolve_music(
        ff, pdir, work, draft, timeline, total_dur,
        reveal_positions=reveal_positions,
        hold_windows=silence_windows,
        film_speaks_windows=film_speaks_windows,
        legacy=Path(music) if music else None)

    if _bed_used and Path(_bed_used).exists():
        if reveal_positions:
            console.print(
                f"[cyan]Music:[/] dipping the bed to "
                f"{config.MUSIC_PRE_REVEAL_LEVEL:.2f} for "
                f"{config.MUSIC_PRE_REVEAL_DROP_SEC:.1f}s around "
                f"{len(reveal_positions)} reveal(s)")
        _render_with_music(ff, av, Path(_bed_used), ass_for_filter, total_dur,
                           final, sfx_events, silence_windows,
                           film_speaks_windows=film_speaks_windows,
                           reveal_positions=reveal_positions,
                           prebuilt_bed=_prebuilt)
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
            "-crf", str(config.VIDEO_CRF),
        "-pix_fmt", config.VIDEO_PIX_FMT,
            "-c:a", "aac", "-b:a", "192k",
            str(final),
        ]
        _run(cmd, "final encode")

    # ----- prepend the beat-cut intro block ---------------------------------
    # final.mp4 = [montage with the over_montage line(s)] + [film intro block,
    # which is shot-bound and already in the timeline above] + [story].
    intro_offset = 0.0
    if n_over_montage:
        try:
            from pipeline import intro as _intro
            _intro.reset_footage()
            intro_offset = _intro.prepend_to_final(project, final) or 0.0
            # The intro paths apply NO censor filter and choose their own
            # footage, so they avoid flagged shots up front (censor.
            # avoid_windows / safe_window). This proves they did: if any
            # flagged footage still reached the opening block, final.mp4 is
            # unpublishable and is removed rather than left on disk looking
            # finished.
            # Record the intro's footage ALWAYS, not only when something is
            # flagged. The censor audit was the only consumer, so with no
            # flagged shots the intro's segments were never recorded at all -
            # and then every freeze inside the intro block was untraceable and
            # counted against the render. Four were. The spans carry their
            # position on the intro timeline, so motion_check can map a frozen
            # stretch in the finished file back to its source span.
            for _u in _intro.used_footage():
                used_footage.add(_u["a"], _u["b"], _u.get("label", "intro"),
                                 blurred=False,
                                 out_a=_u.get("out_a"), out_b=_u.get("out_b"),
                                 out_abs=True)
            if _flagged:
                _ca2 = _censor.audit(_flagged, used_footage)
                if not _censor.report(_ca2, used_footage):
                    try:
                        final.unlink()
                    except OSError:
                        pass
                    console.print("[red]Flagged footage reached the INTRO "
                                  "block unblurred. final.mp4 deleted.[/]")
                    sys.exit(1)
        except SystemExit:
            raise
        except Exception as _e:
            # A spoiler in the montage must NOT be downgraded to a notice -
            # [INTRO-MONTAGE] exists to stop the twist appearing in the first
            # ten seconds, and swallowing it here would undo that gate.
            from pipeline.intro import IntroSpoiler as _Spoil
            if isinstance(_e, _Spoil):
                console.print(f"[red]{_e}[/]")
                raise
            console.print(f"[yellow]Intro block not prepended: {_e}[/]")
    else:
        console.print("[dim]No over_montage line in the draft - final.mp4 "
                      "opens straight on the story.[/]")

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
        # Every position below is SHIFTED BY THE INTRO. The timeline was built
        # against a film with nothing on the front; prepending the montage
        # moves every line later by its length, and timeline.json is what
        # captions and the positional gate read. Writing unshifted positions
        # would make the whole file quietly wrong by ~14 seconds.
        tl = [{"id": t.get("id"),
               "out_start": round(t["start"] + intro_offset, 3),
               "out_end": round(t["end"] + intro_offset, 3),
               "clip_start": t.get("clip_start"),
               "clip_end": t.get("clip_end")} for t in timeline]
        (pdir / "timeline.json").write_text(
            json.dumps({"project": project,
                        "total_duration": round(total_dur + intro_offset, 3),
                        "intro_offset": round(intro_offset, 3),
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
    # A SILENCE line builds a clip but has no TTS audio and no caption window,
    # so it is absent from `narration` and from `timeline` by design. Count it
    # in, or every film using a silence beat reports a false mismatch.
    # An over_montage line HAS narration audio but builds no clip here - it is
    # baked into the prepended intro block. Counting it as expecting a clip
    # makes every draft with a montage report a false mismatch.
    if len(clips) != len(narration) + n_silence - n_over_montage:
        problems.append(f"{len(narration)} narration line(s) + {n_silence} silence "
                        f"- {n_over_montage} over-montage but {len(clips)} clip(s) built")
    if len(timeline) != len(clips) - n_silence:
        problems.append(f"{len(clips)} clip(s) - {n_silence} silence = "
                        f"{len(clips)-n_silence} expected, but {len(timeline)} "
                        f"timeline entr(ies)")

    # ---- positional gate ----------------------------------------------------
    # The real question is not "is the runtime about right" but "does line N's
    # voice arrive where timeline.json says it does". Drift between the video
    # chain (explicit xfade offsets) and the audio chain compounds per junction
    # and is invisible in any total.
    offsets = _position_offsets(ff, final, timeline, narration,
                                intro_offset=intro_offset)
    if not offsets:
        console.print("[dim][RENDER-CHECK] position check skipped "
                      "(numpy missing, or no narration to sample).[/]")
    else:
        worst = max(abs(d) for _i, _w, _m, d in offsets)
        detail = ", ".join(f"line {i} {d:+.2f}s" for i, _w, _m, d in offsets)
        if worst > POSITION_TOLERANCE:
            problems.append(
                f"narration is out of step with timeline.json by up to "
                f"{worst:.2f}s ({detail}) - audio and video chains have "
                f"diverged; captions and every timing gate downstream are "
                f"reading positions the render does not honour")
        else:
            console.print(f"[dim][RENDER-CHECK] position: {detail} "
                          f"(tolerance {POSITION_TOLERANCE:.2f}s).[/]")

    # ---- picture-quality contract on the FINISHED file ----------------------
    # Every other check here asks whether the render matches the draft. This one
    # asks whether it matches the format it is supposed to be in - resolution,
    # frame rate, pix_fmt, codec, and a bitrate floor that catches an encode
    # that quietly fell back. See pipeline/quality.py for what actually governs
    # picture quality (the source, and how much slow-motion, before any flag).
    # ---- the report every final-file check writes into ----------------------
    # Built here, before the first check, and written in a finally-equivalent
    # below so it survives a FATAL gate. A report emitted only on the happy
    # path tells you nothing about the run you actually need to understand.
    from pipeline import final_report as _fr
    _rep = _fr.Report(project, final)

    def _write_report():
        try:
            _p = _rep.write()
            console.print(f"\n[bold cyan]Full measurements:[/] {_p}")
            return _p
        except Exception as _e:                            # pragma: no cover
            console.print(f"[yellow]Could not write final_report.md: {_e}[/]")
            return None

    _qok, _qbad = _q.check_output(ffp, final)
    if _qok:
        _q.report(ffp, final)
    else:
        for _b in _qbad:
            problems.append(f"quality contract: {_b}")
    try:
        _qp = _q._probe(ffp, final)
        _qn = {"width": _qp.get("width"), "height": _qp.get("height"),
               "fps": _qp.get("fps"), "pix_fmt": _qp.get("pix_fmt"),
               "codec": _qp.get("codec_name") or _qp.get("codec"),
               "bitrate (kbit/s)": round(
                   _q.measured_bitrate_kbps(ffp, final), 1)}
        _qn["contract"] = ", ".join(
            f"{k}={v}" for k, v in sorted(
                (config.RENDER_QUALITY_CONTRACT or {}).items()))
    except Exception:
        _qn = {}
    _rep.add("QUALITY-CONTRACT", _qok,
             ("the finished file matches the format contract"
              if _qok else "; ".join(_qbad)),
             numbers=_qn, findings=list(_qbad), fatal=False,
             why=("resolution, frame rate, pix_fmt, codec and a bitrate floor "
                  "that catches an encode which quietly fell back"))

    # ---- RUNTIME, measured against the film it recaps -----------------------
    _src_dur = 0.0
    try:
        _src_dur = float(subprocess.run(
            [ffp, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(source)],
            capture_output=True, text=True).stdout.strip())
    except (ValueError, AttributeError):
        _src_dur = 0.0
    _out_dur = float(total_dur) + float(intro_offset)
    _pct = (100.0 * _out_dur / _src_dur) if _src_dur > 0 else 0.0
    _lo, _hi = 15.0, 20.0
    _rt_ok = (_lo <= _pct <= _hi) if _src_dur > 0 else None
    _rep.add("RUNTIME-BAND", _rt_ok,
             (f"{_out_dur/60:.1f} min of recap from a {_src_dur/60:.1f} min "
              f"film = {_pct:.1f}%"
              + ("" if _rt_ok else f" (soft band {_lo:.0f}-{_hi:.0f}%)")),
             numbers={"recap duration (s)": round(_out_dur, 2),
                      "recap duration": hms_s(_out_dur),
                      "intro block (s)": round(intro_offset, 2),
                      "story (s)": round(total_dur, 2),
                      "source film (s)": round(_src_dur, 2),
                      "percent of film": round(_pct, 2),
                      "soft band": f"{_lo:.0f}-{_hi:.0f}%"},
             fatal=False,
             why=("a soft, PROVISIONAL band from 4 films - a film may "
                  "honestly want a different length"))

    # ---- VOICE RATE, measured on the audio that was actually used -----------
    try:
        _vw = _vd = 0.0
        _bytag: dict = {}
        _by_id2 = {ln["id"]: ln for ln in draft["lines"]}
        for _lid, _p, _d in narration:
            _ln = _by_id2.get(_lid)
            if not _ln:
                continue
            _txt = str(_ln.get("narration") or "").strip()
            if not _txt or not _d:
                continue
            _w = len(_txt.split())
            _vw += _w
            _vd += float(_d)
            _g = _bytag.setdefault(str(_ln.get("delivery") or "normal"),
                                   [0, 0.0])
            _g[0] += _w
            _g[1] += float(_d)
        _wpm = (60.0 * _vw / _vd) if _vd > 0 else 0.0
        _tgt = float(config.TARGET_WPM)
        _drift = (_wpm - _tgt) / _tgt if _tgt else 0.0
        _vok = abs(_drift) <= float(config.VOICE_RATE_DRIFT_MAX)
        _vrows = []
        for _t, (_w, _dd) in sorted(_bytag.items(),
                                    key=lambda x: -x[1][1]):
            _trate = (60.0 * _w / _dd) if _dd > 0 else 0.0
            _vrows.append({"tag": _t, "words": _w,
                           "speaking (s)": round(_dd, 1),
                           "WPM": round(_trate, 1),
                           "vs aggregate": (f"{(_trate/_wpm - 1):+.1%}"
                                            if _wpm else "-")})
        _rates = [r["WPM"] for r in _vrows if r["WPM"] > 0]
        _rep.add("VOICE-RATE", _vok,
                 (f"{_wpm:.1f} WPM measured on {len(narration)} line(s) "
                  f"against a {_tgt:.0f} target ({_drift:+.1%})"),
                 numbers={"measured WPM": round(_wpm, 1),
                          "TARGET_WPM": _tgt,
                          "drift": f"{_drift:+.1%}",
                          "drift allowed": f"+-{config.VOICE_RATE_DRIFT_MAX:.0%}",
                          "words": int(_vw),
                          "speaking seconds": round(_vd, 1),
                          "narration total": hms_s(_vd),
                          "tag spread": (f"{max(_rates)/min(_rates):.3f}x"
                                         if len(_rates) > 1 else "-")},
                 rows=_vrows, fatal=False,
                 why=("raw duration-based WPM, which is what the word budget "
                      "is built on; articulation rate is a separate measure "
                      "used for voice consistency"))
    except Exception as _ve:                               # pragma: no cover
        _rep.add("VOICE-RATE", None, f"could not measure: {_ve}")

    # ---- THE FILE ITSELF, measured, before any check that reads the plan ----
    # This runs FIRST and it is FATAL, because every other post-render check
    # assumes the file is the length it was asked for, and one of them cannot
    # notice when it is not: freezedetect on a file whose video stream has
    # ENDED scans only the frames that exist, finds nothing, and reports the
    # film clean. That is how a final.mp4 with 255.77s of video under 1054.47s
    # of audio - the picture gone from 4:15.8 to 17:34.5 - passed MOTION-CHECK.
    #
    # `probe` is told one number, the duration the render believes it built,
    # and it checks it rather than trusting it.
    from pipeline import probe as _probe
    console.print(f"[dim][FILE-CHECK] {_probe.describe(final)}[/]")
    _fbad = _probe.verify(final, expect_dur=total_dur + intro_offset)
    _st = _probe.streams(final)
    _sv, _sa = _st.get("video"), _st.get("audio")
    _fnum = {
        "expected duration (s)": round(total_dur + intro_offset, 3),
        "video stream (s)": (round(_sv["duration"], 3) if _sv else None),
        "audio stream (s)": (round(_sa["duration"], 3) if _sa else None),
        "video - audio (s)": (round(_sv["duration"] - _sa["duration"], 3)
                              if _sv and _sa else None),
        "video packets": _probe.packet_count(final, "v"),
        "fps": (round(_sv["fps"], 3) if _sv else None),
        "video codec": (_sv["codec"] if _sv else None),
        "audio codec": (_sa["codec"] if _sa else None),
        "pts holes": len(_probe.pts_gaps(final, "v")),
    }
    _rep.add("FILE-CHECK", not _fbad,
             (_probe.describe(final) if not _fbad
              else "; ".join(b["msg"] for b in _fbad)),
             numbers=_fnum,
             rows=[{"at": g["at"], "hole (s)": g["gap"]}
                   for g in _probe.pts_gaps(final, "v")],
             findings=[{"text": b["msg"]} for b in _fbad],
             fatal=True,
             why=("the STREAMS, never the container header - the header "
                  "reports the longest stream, which is why a file with "
                  "255.77s of video under 1054.47s of audio looked correct"))
    if _fbad:
        console.print("[red][FILE-CHECK][/] final.mp4 is not the file the "
                      "render thinks it built:")
        for _b in _fbad:
            console.print(f"[red]    {_b['msg']}[/]")
        console.print("[red]  This is a publish blocker. A short video stream "
                      "is invisible in every player until the moment the "
                      "picture stops.[/]")
        _rep.note("The render STOPPED here, so no check below this point ran.")
        _write_report()
        sys.exit(1)

    # ---- MUSIC + FILM_SPEAKS, measured on the FINISHED MIX -----------------
    # Both of these were reported from watching the render and neither could
    # have been caught before, because the checks confirmed that a gain was
    # written into a filtergraph and never that the result was audible.
    # READ FROM THE PROJECT DIR, NOT _work. This pointed at `work`, which is
    # rmtree'd ~260 lines above, so BOTH these checks reported SKIPPED on every
    # render that did not pass --keep-temp. The shipped report said "no
    # prebuilt music track (no music/bed.* + music/cues/*)" while the same
    # render's log showed cues being placed from action1.mp3: the message
    # asserted a cause it had never checked, and sent the reader looking for a
    # bed file that was there all along. A gate that is green because its input
    # was deleted is worse than no gate.
    from pipeline import audio_check as _ac
    _mplan = pdir / "music_plan.json"
    _mp = {}
    if _mplan.exists():
        try:
            _mp = json.loads(_mplan.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _mp = {}
    _cues = [{"at": float(c["at"]) + intro_offset, "dur": float(c["dur"]),
              "mood": c.get("mood")} for c in (_mp.get("cues") or [])]
    if not _cues:
        # FOUR different situations used to collapse into one wrong message.
        # Only the first two are legitimate skips.
        if not _bed_used:
            _rep.add("MUSIC-CUE", None,
                     "this render used no music at all, so there are no cues "
                     "to measure")
        elif not _prebuilt:
            # Quote resolve_music's OWN note rather than guessing why. A first
            # version said "no cue files", which was wrong on a project that
            # HAS cue files but whose planner placed none (density caps, or no
            # qualifying run) - the same mistake as the message this whole
            # item is fixing, one layer down.
            _rep.add("MUSIC-CUE", None,
                     f"no bed+cues track was built, so there are no cues to "
                     f"measure - the music design in use is: {_mnote}")
        elif not _mplan.exists():
            _m2 = (f"a bed+cues track WAS built from "
                   f"{Path(_bed_used).name} but {_mplan.name} is missing, so "
                   f"no cue level could be measured. This is a pipeline bug, "
                   f"not an absence of music.")
            _rep.add("MUSIC-CUE", False, _m2, fatal=False,
                     findings=[{"text": _m2}])
            problems.append("music measurement: " + _m2)
        else:
            _rep.add("MUSIC-CUE", None,
                     "a bed+cues track was built but the cue planner placed "
                     "no cues (density caps, or no qualifying run)")
    if _cues:
        _cok, _cfind, _crows = _ac.check_cues_audible(final, _cues)
        for _r in _crows:
            console.print(
                f"[dim][MUSIC-CUE] {str(_r.get('mood')):<8} "
                f"{_r['at']:7.1f}s  {_r['inside_db']:+6.1f} dB vs bed "
                f"{_r['bed_db']:+6.1f} dB  lift {_r['lift_db']:+5.1f} dB"
                + (f"  ({_r['inside_lufs']:.1f} LUFS)"
                   if _r.get("inside_lufs") is not None else "") + "[/]")
        _rep.add("MUSIC-CUE", _cok,
                 (f"{len(_crows)} cue(s); lift above the bed "
                  + ", ".join(f"{r['mood']} {r['lift_db']:+.1f} dB"
                               for r in _crows)
                  if _crows else "no cues placed"),
                 numbers={"minimum lift required (dB)":
                          _ac.CUE_LIFT_MIN_DB,
                          "music normalised to (LUFS)":
                          (config.MUSIC_NORMALIZE_LUFS
                           if getattr(config, 'MUSIC_NORMALIZE', True)
                           else None),
                          "cue level target (dB)":
                          config.MUSIC_CUE_DUCK_DB,
                          "action cue target (dB)":
                          config.MUSIC_CUE_DUCK_ACTION_DB,
                          "bed dip under a cue (dB)":
                          config.MUSIC_CUE_BED_DIP_DB},
                 rows=[{"mood": r.get("mood"),
                        "at": hms_s(r["at"]),
                        "length (s)": round(r["dur"], 1),
                        "cue (dB)": r["inside_db"],
                        "bed (dB)": r["bed_db"],
                        "lift (dB)": r["lift_db"],
                        "cue (LUFS)": r.get("inside_lufs")}
                       for r in _crows],
                 findings=[{"at": r["at"],
                            "text": (f"{r.get('mood')} cue lifts only "
                                     f"{r['lift_db']:+.1f} dB above the "
                                     f"bed (bar "
                                     f"{_ac.CUE_LIFT_MIN_DB:.0f} dB)")}
                           for r in _crows
                           if r["lift_db"] < _ac.CUE_LIFT_MIN_DB],
                 fatal=False,
                 why=("every music file is loudness-normalised before any "
                      "gain, because the cue sources span 9.0 dB of "
                      "integrated loudness - more than the gain "
                      "differences the mix is built on"))
        if not _cok:
            console.print("[red][MUSIC-CUE][/] cue(s) are not audible "
                          "above the bed:")
            for _b in _cfind:
                console.print(f"[red]    {_b}[/]")
            problems.append("music cues: " + "; ".join(_cfind))
    # film_speaks: the film must be the loudest thing in its own unit.
    # Taken from the render's OWN in-memory window list, not read back out of
    # the music plan file. The plan was only ever a convenient carrier, and
    # routing this through a file in _work/ meant a measurement that does not
    # depend on music at all got skipped whenever that file was missing.
    _fsw = list(film_speaks_windows)
    if not _fsw:
        _rep.add("FILM-SPEAKS", None,
                 "this draft has no <film_speaks> units")
    if _fsw:
        _fs_by_pos = []
        _fs_lines = [ln["id"] for ln in draft["lines"]
                     if ln.get("film_speaks_seconds") is not None]
        for _i, (_a, _b) in enumerate(_fsw):
            _fs_by_pos.append({
                "line_id": (_fs_lines[_i] if _i < len(_fs_lines) else None),
                "final_at": float(_a) + intro_offset,
                "dur": float(_b) - float(_a)})
        _sok, _sfind, _srows = _ac.check_film_speaks_audible(
            final, _fs_by_pos)
        for _r in _srows:
            console.print(
                f"[dim][FILM-SPEAKS] line {_r.get('line_id')} "
                f"{_r['final_at']:7.1f}s  film {_r['inside_db']:+6.1f} dB "
                f"vs music {max(_r['before_db'], _r['after_db']):+6.1f} dB"
                f"  margin {_r['margin_db']:+5.1f} dB[/]")
        _rep.add("FILM-SPEAKS", _sok,
                 (f"{len(_srows)} unit(s); margin over the music "
                  + ", ".join(f"line {r.get('line_id')} "
                               f"{r['margin_db']:+.1f} dB"
                               for r in _srows)),
                 numbers={"minimum margin required (dB)":
                          _ac.FILM_SPEAKS_MARGIN_MIN_DB,
                          "music ducked by (dB)":
                          config.FILM_SPEAKS_MUSIC_DB,
                          "duck fade (s)":
                          config.FILM_SPEAKS_MUSIC_FADE_SEC,
                          "film level (dB)": config.FILM_SPEAKS_DB,
                          "audio used": "ORIGINAL mix (dialogue kept)"},
                 rows=[{"line": r.get("line_id"),
                        "at": hms_s(r["final_at"]),
                        "length (s)": round(r["dur"], 2),
                        "film (dB)": r["inside_db"],
                        "music before (dB)": r["before_db"],
                        "music after (dB)": r["after_db"],
                        "margin (dB)": r["margin_db"],
                        "film (LUFS)": r.get("inside_lufs")}
                       for r in _srows],
                 findings=[{"at": r["final_at"],
                            "text": (f"film_speaks line "
                                     f"{r.get('line_id')} is only "
                                     f"{r['margin_db']:+.1f} dB over the "
                                     f"music (bar "
                                     f"{_ac.FILM_SPEAKS_MARGIN_MIN_DB:.0f}"
                                     f" dB)")}
                           for r in _srows
                           if r["margin_db"]
                           < _ac.FILM_SPEAKS_MARGIN_MIN_DB],
                 fatal=False,
                 why=("the shipped render measured +3.2 and +1.5 dB here "
                      "and was described as 'only music', so the bar is "
                      "sited against that, not against a rule of thumb"))
        if not _sok:
            console.print("[red][FILM-SPEAKS][/] the film is not audible "
                          "in its own unit:")
            for _b in _sfind:
                console.print(f"[red]    {_b}[/]")
            problems.append("film_speaks: " + "; ".join(_sfind))

    # ---- FILM AUDIO: is the stem where the rule says, and nowhere else? -----
    # Measured on the finished mix by CORRELATING it against the stem file,
    # not by reading the filtergraph. Level cannot answer this: on a control
    # mix, adding the stem at -17 dB moved the RMS by 0.4 dB but moved the
    # correlation from 0.006 to 0.293.
    if film_stem is None or not _fa_ids:
        _rep.add("FILM-AUDIO", None,
                 ("no no-vocals stem available" if film_stem is None
                  else (f"no line qualifies for film audio "
                        f"({'/'.join(config.FILM_AUDIO_TAGS)} runs of "
                        f"{config.FILM_AUDIO_MIN_RUN}+)")))
    if film_stem is not None and _fa_ids:
        from pipeline import audio_check as _ac
        # ALIGN THE TWO CLOCKS. `_t["start"]` is where the NARRATION starts,
        # which is the clip start plus the lead-in; the stem is addressed from
        # the CLIP start. Comparing one against the other offset them by 0.5s
        # (1.1s on a reveal), far beyond the +-50ms lag search, and crushed
        # every correlation: line 11 measured 0.085 misaligned and 0.794
        # aligned. The window is also bounded to the clip, because a fixed
        # window runs past a short clip into the next one and is then compared
        # against the wrong source span.
        _rows = []
        _by_id = {ln["id"]: ln for ln in draft["lines"]}
        for _t in timeline:
            _lid = _t.get("id")
            _ln = _by_id.get(_lid)
            if not _ln or not _ln.get("clip_start"):
                continue
            if _ln.get("film_speaks_seconds") is not None:
                continue           # original mix, checked separately
            try:
                _sa = parse_ts(_ln["clip_start"])
                _sb = parse_ts(_ln["clip_end"])
            except Exception:
                continue
            _nd = float(_t.get("end", 0.0)) - float(_t.get("start", 0.0))
            _lead, _clen = _fpmod.lead_and_clip(
                _nd, _sb - _sa, float(_ln.get("hold") or 0.0),
                _fpmod.reveal_extra(_ln))
            _rows.append({"line_id": _lid,
                          "final_at": float(_t["start"]) - _lead + intro_offset,
                          "source_at": _sa,
                          "window": max(0.0, _clen - 0.3),
                          "want": _lid in _fa_ids})
        _fok, _ffind, _fgot, _finfo = _ac.check_film_audio_placement(
            final, film_stem, _rows)
        _sep = _finfo.get("separation")
        console.print(
            f"[dim][FILM-AUDIO] separation "
            f"{('%.2fx' % _sep) if _sep else 'n/a'}"
            f"  median on {_finfo.get('median_on')}  p90 off "
            f"{_finfo.get('p90_off')}  "
            f"({_finfo.get('informative_on')} on / "
            f"{_finfo.get('informative_off')} off informative, "
            f"{_finfo.get('uninformative')} uninformative)[/]")
        _rep.add("FILM-AUDIO",
                 (None if _finfo.get("skipped") else _fok),
                 (_finfo["skipped"] if _finfo.get("skipped") else
                  (f"action/tense median {_finfo.get('median_on')} vs p90 "
                   f"{_finfo.get('p90_off')} elsewhere = "
                   f"{_sep:.2f}x separation "
                   f"(bar {_ac.STEM_SEPARATION_MIN:.1f}x)")),
                 numbers={"lines with film audio": len(_fa_ids),
                          "lines total": len(draft.get("lines") or []),
                          "tags allowed": ", ".join(config.FILM_AUDIO_TAGS),
                          "minimum run": config.FILM_AUDIO_MIN_RUN,
                          "median corr on": _finfo.get("median_on"),
                          "p90 corr off": _finfo.get("p90_off"),
                          "separation": _sep,
                          "separation required": _ac.STEM_SEPARATION_MIN,
                          "informative on": _finfo.get("informative_on"),
                          "informative off": _finfo.get("informative_off"),
                          "uninformative windows": _finfo.get("uninformative"),
                          "informative floor (dB)":
                              _ac.STEM_INFORMATIVE_DB,
                          "level under narration (dB)": config.FILM_AUDIO_DB,
                          "stem": Path(film_stem).name},
                 rows=[{"line": r["line_id"],
                        "at": hms_s(r["final_at"]),
                        "rule": ("film audio ON" if r["want"]
                                 else "should be OFF"),
                        "window (s)": r.get("window"),
                        "stem (dB)": r.get("stem_db"),
                        "correlation": r.get("corr"),
                        "informative": r.get("informative"),
                        "note": r.get("why")} for r in _fgot],
                 findings=[{"text": b} for b in _ffind],
                 fatal=False,
                 why=("the finished mix is CORRELATED against the stem file, "
                      "clip-aligned and clip-bounded; judged on the "
                      "distributions because the per-line tails of this "
                      "measurement overlap - claiming per-line precision "
                      "produced six false findings on the shipped render"))
        if not _fok:
            console.print("[red][FILM-AUDIO][/] the film's track is not "
                          "placed by the rule:")
            for _b in _ffind:
                console.print(f"[red]    {_b}[/]")
            problems.append("film audio placement: " + "; ".join(_ffind))

    # ---- FROZEN / REPEATED FOOTAGE on the finished file ---------------------
    # The build rules cap slow-motion and freezes, but a freeze has sources
    # those rules cannot see: static frames in the source itself, a filter
    # graph that stalls, or a cached clip built under older rules. This measures
    # the result. Unlike the checks above it is FATAL - a frozen picture or the
    # same shot twice is not something to inspect and ship anyway.
    from pipeline import motion_check as _mc
    _mok, _mbad = _mc.check(ff, final, draft,
                            shown=used_footage.items,
                            intro_offset=intro_offset,
                            source=source)
    try:
        _frz = _mc.freezes(ff, final)
    except Exception:
        _frz = []
    _rep.add("MOTION-CHECK", _mok,
             ("no freeze over %.2fs and no repeated source footage"
              % float(config.FREEZE_FAIL_SEC) if _mok
              else "; ".join(str(b) for b in _mbad)),
             numbers={"clone cap (s)": config.MAX_FREEZE_SEC,
                      "freeze fails over (s)": config.FREEZE_FAIL_SEC,
                      "freeze noise floor (dB)": config.FREEZE_NOISE_DB,
                      "slow-motion ceiling": "%.2fx" % float(
                          __import__("pipeline.schemas", fromlist=["x"])
                          .BINDING_SLOWDOWN_MAX),
                      "reuse overlap bar (s)":
                      config.FOOTAGE_REUSE_MIN_OVERLAP_SEC,
                      "freezes detected": len(_frz)},
             rows=[{"at": hms_s(f.get("start")),
                    "length (s)": round(float(f.get("dur") or 0), 2)}
                   for f in _frz],
             findings=[{"text": str(b)} for b in _mbad],
             fatal=True,
             why=("freezedetect on the finished file, with every freeze "
                  "traced back to its source span; an untraceable freeze is "
                  "reported, never excused"))
    if not _mok:
        console.print("[red][MOTION-CHECK][/] the finished video has frozen or "
                      "repeated footage:")
        for _b in _mbad:
            console.print(f"[red]    {_b}[/]")
        console.print("[red]  This is a publish blocker. Widen the windows "
                      "that needed a freeze, or re-point the duplicated "
                      "line.[/]")
        _rep.note("The render STOPPED here; checks below this point did not "
                  "run.")
        _write_report()
        sys.exit(1)

    # ---- REPEATED SCENES, judged on the PICTURE ----------------------------
    # motion_check.reuse compares SOURCE windows, which catches literal reuse
    # and cannot catch what a viewer notices: this film is shot/reverse-shot,
    # so two different source windows minutes apart can hold a nearly
    # identical frame. The bookkeeping says "different footage" and is right;
    # the screen says "I have seen this" and is also right.
    #
    # Reported, not fatal. A perceptual hash is a fuzzy measure and a false
    # positive must not block a publish - but it has to be visible, with
    # OUTPUT timestamps, so it can be checked against the finished video.
    try:
        from pipeline import dupe_check as _dup
        _dok, _dfind, _dinfo = _dup.check(final)
        console.print(
            f"[dim][REPEAT-SCENE] {_dinfo.get('sampled', 0)} frame(s) sampled, "
            f"{_dinfo.get('skipped_flat', 0)} flat (fades/black) skipped, "
            f"crop {_dinfo.get('crop')}[/]")
        _dpairs = _dinfo.get("pairs") or []
        _vdur = (_probe.streams(final).get("video") or {}).get("duration", 0)
        _rep.add("REPEAT-SCENE", _dok,
                 (f"{_dinfo.get('sampled', 0)} frame(s) sampled, "
                  f"{len(_dpairs)} near-identical pair(s)"),
                 numbers={"frames sampled": _dinfo.get("sampled"),
                          "flat frames skipped": _dinfo.get("skipped_flat"),
                          "letterbox crop": _dinfo.get("crop"),
                          "sample interval (s)": _dup.SAMPLE_INTERVAL_SEC,
                          "hamming bar (of 64)": _dup.MAX_DISTANCE,
                          "minimum gap (s)": _dup.MIN_GAP_SEC,
                          "variance floor": _dup.MIN_VARIANCE,
                          "video covered (s)": round(float(_vdur or 0), 2)},
                 rows=[{"first": hms_s(d["a"]), "second": hms_s(d["b"]),
                        "hamming": d["distance"],
                        "apart (s)": d["gap"]} for d in _dpairs],
                 findings=[{"at": d["a"],
                            "text": (f"near-identical to {hms_s(d['b'])} "
                                     f"(hamming {d['distance']}/64, "
                                     f"{d['gap']:.0f}s apart)")}
                           for d in _dpairs],
                 fatal=False,
                 why=("a perceptual hash of frames sampled from the finished "
                      "file - source-span bookkeeping cannot catch "
                      "shot/reverse-shot, where two different windows hold "
                      "nearly the same picture"))
        if not _dok:
            console.print("[yellow][REPEAT-SCENE][/] near-identical picture "
                          "at two different times:")
            for _b in _dfind:
                console.print(f"[yellow]    {_b}[/]")
            problems.append("repeated scenes: " + "; ".join(_dfind))
    except Exception as _de:                               # pragma: no cover
        console.print(f"[yellow][REPEAT-SCENE] could not run: {_de}[/]")
        _rep.add("REPEAT-SCENE", None, f"could not run: {_de}")

    _rep.add("RENDER-CHECK", not problems,
             (f"{len(clips)} clip(s) out ({len(narration)} narrated + "
              f"{n_silence} silence), narration lands on its timeline slots"
              if not problems else "; ".join(problems)),
             numbers={"clips built": len(clips),
                      "narrated lines": len(narration),
                      "silence units": n_silence,
                      "over-montage lines": n_over_montage,
                      "timeline entries": len(timeline),
                      "position tolerance (s)": POSITION_TOLERANCE,
                      "worst position drift (s)": (
                          round(max(abs(d) for *_x, d in offsets), 3)
                          if offsets else None)},
             rows=[{"line": _i, "expected": hms_s(_w),
                    "measured": hms_s(_m), "drift (s)": round(_d, 3)}
                   for _i, _w, _m, _d in (offsets or [])],
             findings=[{"text": pr} for pr in problems],
             fatal=False,
             why=("cross-correlates each sampled line's own TTS audio against "
                  "the finished mix near the position timeline.json claims "
                  "for it, so real audio/video drift is measured rather than "
                  "a total being compared with itself"))

    if problems:
        console.print("[red][RENDER-CHECK][/] the render does not match the draft:")
        for pr in problems:
            console.print(f"    {pr}")
        console.print("[red]  final.mp4 was still written - inspect it before publishing.[/]")
    else:
        console.print(f"[dim][RENDER-CHECK] {len(clips)} clips out "
                      f"({len(narration)} narrated + {n_silence} silence), "
                      f"narration lands on its timeline slots.[/]")

    console.print(f"\n[bold green]Done![/] Final video: {final}")
    _write_report()
    return final


def _loudnorm_filter() -> str:
    """Return a loudnorm audio-filter string, or '' if disabled."""
    if not config.LOUDNORM_ENABLE:
        return ""
    return (f"loudnorm=I={config.LOUDNORM_I}:TP={config.LOUDNORM_TP}:"
            f"LRA={config.LOUDNORM_LRA}")


def mood_segments(draft: dict, timeline: list, total_dur: float) -> list:
    """Split the finished timeline into stretches, each with ONE music mood.

    The mood of a stretch comes from the dominant `delivery` tag of the lines
    in it (config.MUSIC_MOOD_FOR_TAG). Consecutive lines that map to the same
    mood merge; any stretch shorter than MUSIC_MOOD_MIN_SEC is absorbed into
    its neighbour, because a bed that changes every fifteen seconds is worse
    than one that never changes.

    Returns [{"start": s, "end": e, "mood": name}] covering 0..total_dur.
    """
    by_id = {ln.get("id"): ln for ln in draft.get("lines", [])}
    tag_map = dict(getattr(config, "MUSIC_MOOD_FOR_TAG", {}) or {})
    runs: list = []
    for t in timeline:
        ln = by_id.get(t.get("id")) or {}
        mood = tag_map.get(str(ln.get("delivery") or "normal"), "neutral")
        if runs and runs[-1]["mood"] == mood:
            runs[-1]["end"] = float(t["end"])
        else:
            runs.append({"start": float(t["start"]), "end": float(t["end"]),
                         "mood": mood})
    if not runs:
        return [{"start": 0.0, "end": float(total_dur), "mood": "neutral"}]

    # absorb stretches that are too short to be heard as a change
    floor = float(getattr(config, "MUSIC_MOOD_MIN_SEC", 25.0))
    merged: list = [runs[0]]
    for r in runs[1:]:
        if (r["end"] - r["start"]) < floor:
            merged[-1]["end"] = r["end"]          # absorb into the one before
        elif merged[-1]["mood"] == r["mood"]:
            merged[-1]["end"] = r["end"]
        else:
            merged.append(r)
    # a too-short FIRST stretch gets absorbed forwards instead
    if len(merged) > 1 and (merged[0]["end"] - merged[0]["start"]) < floor:
        merged[1]["start"] = merged[0]["start"]
        merged.pop(0)
    merged[0]["start"] = 0.0
    merged[-1]["end"] = float(total_dur)
    for a, b in zip(merged, merged[1:]):
        b["start"] = a["end"]
    return merged


def resolve_mood_beds(pdir, segments: list):
    """Find projects/<name>/music/<mood>.mp3 for each mood actually used.

    Returns (beds, missing, usable). `usable` is False when not every mood in
    play has a file - the caller then falls back to the single music.mp3 and
    SAYS SO. A half-populated music/ directory must not produce a render where
    some stretches have a bed and others are silent.
    """
    mdir = pdir / "music"
    moods = []
    for s in segments:
        if s["mood"] not in moods:
            moods.append(s["mood"])
    beds, missing = {}, []
    for m in moods:
        hit = None
        for ext in (".mp3", ".m4a", ".wav", ".ogg"):
            p = mdir / f"{m}{ext}"
            if p.exists():
                hit = p
                break
        if hit:
            beds[m] = hit
        else:
            missing.append(m)
    return beds, missing, (bool(beds) and not missing)


def build_music_bed(ff: str, segments: list, beds: dict, out: Path,
                    total_dur: float) -> Path:
    """Concatenate one continuous bed from the per-mood files.

    Built as a FILE rather than as a branch of the final filter graph. The
    graph version needed one input and one timed volume expression per mood and
    was unreadable; a pre-built bed is inspectable on its own, and if it is
    wrong you can play it.
    """
    parts, inputs, filt = [], [], []
    for i, s in enumerate(segments):
        dur = max(0.05, float(s["end"]) - float(s["start"]))
        src = beds[s["mood"]]
        # `-t` BEFORE `-i` bounds the looped read. Without it every segment is
        # an infinite input and concat sits waiting on the ones it has not
        # reached yet: the first attempt at this failed its own build and left a
        # truncated bed behind.
        inputs += ["-stream_loop", "-1", "-t", f"{dur:.3f}", "-i", str(src)]
        # Duck depth is baked in PER MOOD, relative to the ordinary narration
        # level: the guides say 20-25 dB under the voice while the narrator is
        # talking, but only 8-12 dB in action, where the bed should be felt.
        # The difference is applied here so the final mix stays one simple
        # volume expression instead of a second time-varying one.
        _rel = (float(config.MUSIC_DUCK_ACTION_DB)
                - float(config.MUSIC_DUCK_DB)) if s["mood"] == "action" else 0.0
        _g = f"volume={_rel:+.1f}dB," if abs(_rel) > 0.05 else ""
        filt.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                    f"atrim=duration={dur:.3f},asetpts=PTS-STARTPTS,{_g}"
                    f"afade=t=in:st=0:d=1.0,"
                    f"afade=t=out:st={max(0.0, dur-1.0):.3f}:d=1.0[m{i}]")
        parts.append(f"[m{i}]")
    graph = ";".join(filt) + ";" + "".join(parts) + \
        f"concat=n={len(parts)}:v=0:a=1[bed]"
    cmd = [ff, "-y", *inputs, "-filter_complex", graph,
           "-map", "[bed]", "-t", f"{total_dur:.3f}",
           "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(out)]
    _run(cmd, f"build mood music bed ({len(segments)} stretches)")
    return out


def hms_s(t) -> str:
    """Seconds as m:ss.cc, for logs and the final report."""
    from pipeline.final_report import hms
    return hms(t)


def _music_volume_expr(base_vol: float, silence_windows: list,
                       reveal_positions: list | None = None,
                       film_speaks_windows: list | None = None) -> str:
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

    # ---- drop the bed just BEFORE each reveal ---------------------------
    # "Drop or cut the music briefly before a major reveal" - the line should
    # arrive into a hole. Implemented as a multiplier that dips to
    # MUSIC_PRE_REVEAL_LEVEL over the window [t_reveal - drop, t_reveal] and
    # comes back over the same length afterwards. Near-zero rather than a hard
    # 0 so the bed does not click.
    # A <film_speaks> unit DUCKS the music, faded either side. This is the
    # same rule build_music_track bakes into the prebuilt bed+cues track, done
    # here as well so the bed-only and legacy single-track paths get it too -
    # otherwise the fix would only work on one of the three music designs.
    for (fa, fb) in (film_speaks_windows or []):
        fa, fb = float(fa), float(fb)
        if fb <= fa:
            continue
        lvl = 10.0 ** (float(getattr(config, "FILM_SPEAKS_MUSIC_DB", -20.0))
                       / 20.0)
        fsf = max(0.05, float(getattr(config, "FILM_SPEAKS_MUSIC_FADE_SEC",
                                      0.75)))
        ra, rb = max(0.0, fa - fsf), fb + fsf
        ramp = (f"min(clip((t-{ra:.3f})/{fsf:.3f}\\,0\\,1)\\,"
                f"clip(({rb:.3f}-t)/{fsf:.3f}\\,0\\,1))")
        expr = (f"if(between(t\\,{ra:.3f}\\,{rb:.3f})\\,"
                f"({expr})*(1-(1-{lvl:.5f})*{ramp})\\,({expr}))")

    rp = [float(x) for x in (reveal_positions or [])]
    if rp:
        drop = max(0.3, float(getattr(config, "MUSIC_PRE_REVEAL_DROP_SEC", 1.5)))
        lvl = float(getattr(config, "MUSIC_PRE_REVEAL_LEVEL", 0.02))
        gates = []
        for t0 in rp:
            a = max(0.0, t0 - drop)
            b = t0 + drop
            # dip = 1 outside [a,b]; lvl at t0; linear either side
            gates.append(
                f"if(between(t\\,{a:.3f}\\,{b:.3f})\\,"
                f"{lvl:.4f}+(1-{lvl:.4f})*abs(t-{t0:.3f})/{drop:.3f}\\,1)")
        # several reveals never overlap closely enough to matter; take the min
        dip = gates[0] if len(gates) == 1 else \
            "min(" + "\\,".join(gates) + ")" if len(gates) == 2 else None
        if dip is None:
            # ffmpeg's min() takes two args, so fold
            dip = gates[0]
            for g in gates[1:]:
                dip = f"min({dip}\\,{g})"
        expr = f"({expr})*({dip})"
    return f"volume='{expr}':eval=frame"


def _render_with_music(ff: str, av: Path, music: Path, ass_filter: str | None,
                       total_dur: float, final: Path,
                       sfx_events: list[dict] | None = None,
                       silence_windows: list[tuple[float, float]] | None = None,
                       film_speaks_windows: list | None = None,
                       reveal_positions: list | None = None,
                       prebuilt_bed: bool = False):
    """Burn captions (optional), mix ducked music + timed SFX, master loudness.

    Gap 3: during each (start, end) silence window the music swells from the
    ducked narration level up to SILENCE_MUSIC_VOLUME with a SILENCE_FADE
    rise/fall, then returns to the narration level.

    2026-10-20: the bed level under the voice now comes from MUSIC_DUCK_DB
    (20-25 dB under, per the retention guides) instead of a bare 0.15, and the
    bed dips to near-silence for MUSIC_PRE_REVEAL_DROP_SEC before every
    <reveal> so the line lands into a hole. `prebuilt_bed` means input 1 is
    already a full-length mood bed with its per-mood duck baked in, so it must
    NOT be looped.
    """
    vol = 10.0 ** (float(config.MUSIC_DUCK_DB) / 20.0)
    fade = config.MUSIC_FADEOUT
    fade_start = max(0.0, total_dur - fade)
    sfx_events = sfx_events or []
    silence_windows = silence_windows or []

    # Base music volume is `vol`. Silence windows swell it; reveals dip it.
    vol_expr = _music_volume_expr(vol, silence_windows, reveal_positions,
                                  film_speaks_windows=film_speaks_windows)

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

    # A prebuilt mood bed is already exactly total_dur long with its moods in
    # order - looping it would restart the first mood over the ending.
    _music_in = ["-i", str(music)] if prebuilt_bed else \
        ["-stream_loop", "-1", "-i", str(music)]
    cmd = [
        ff, "-y",
        "-i", str(av),
        *_music_in,
        *sfx_inputs,
        "-filter_complex", graph,
        "-map", vmap, "-map", "[aout]",
        "-t", f"{total_dur:.3f}",
        "-c:v", "libx264", "-preset", config.VIDEO_PRESET,
        "-crf", str(config.VIDEO_CRF),
        "-pix_fmt", config.VIDEO_PIX_FMT,
        "-c:a", "aac", "-b:a", "192k",
        str(final),
    ]
    _run(cmd, "final encode with music")



