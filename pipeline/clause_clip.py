"""Build one line's picture as hard-cut sub-clips.

WHY NOT _build_montage_clip, which already concatenates segments: it exists
for a silent action montage and applies zoompan motion to every segment,
because there its job is to keep a long wordless stretch alive. A clause-cut
line is an ordinary narrated line - adding a slow zoom to every sub-clip
would change how the whole recap looks, which is not what was asked for.

What this does: extract each sub-clip at its own duration, normalise all of
them identically (same scaler, letterbox, pix_fmt, fps and timebase as every
other clip in the render, or the concat demuxer will refuse them), hard-cut
between them, and lay the line's single narration track over the whole thing.
The crossfade stays where it was - between LINES, handled by assemble.

The result is one file per line, so `assemble.build` and the Phase 1 encoder
see exactly what they saw before and nothing downstream changes.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import config

LEAD_IN = getattr(config, "LEAD_IN", 0.5)
GAP = getattr(config, "GAP", 0.4)


def _norm_chain(seg_len: float) -> str:
    """Scale + pad + fps + pix_fmt, identical to the single-clip path."""
    w, h = config.OUTPUT_WIDTH, config.OUTPUT_HEIGHT
    return (f"scale={w}:{h}:force_original_aspect_ratio=decrease"
            f":flags={config.VIDEO_SCALER},"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={config.OUTPUT_FPS},format={config.VIDEO_PIX_FMT},"
            f"tpad=stop_mode=clone:stop_duration=2,"
            f"trim=duration={seg_len:.3f},setpts=PTS-STARTPTS")


def build(ff: str, source: Path, segments: list, play_durs: list,
          narr_audio: Path | None, narr_dur: float, out: Path) -> float:
    """Hard-cut the segments into one clip. Returns the clip length.

    `segments` [(start, end)] source windows; `play_durs` the seconds each is
    on screen. The clip is exactly LEAD_IN + narr_dur + GAP long, so the
    line's slot in the timeline is unchanged from the single-shot version -
    this changes the PICTURE, not the pacing.
    """
    assert len(segments) == len(play_durs), "a segment per duration"
    # THE VOICE DECIDES THE LENGTH, always. An earlier version took
    # max(LEAD_IN + narr_dur + GAP, sum(play_durs)) and the picture won: a
    # line whose segments summed to its 15.5s window produced a 15.5s clip
    # where the current render gives it 9.97s. That shifts the whole timeline
    # and makes an A/B compare two different durations rather than two
    # pictures. This changes the PICTURE, not the pacing, so the slot is
    # exactly what the single-shot path would have produced.
    clip_len = LEAD_IN + narr_dur + GAP
    # Scale the durations so they total the clip exactly; the voice decides
    # the length and the picture fits inside it.
    tot = sum(play_durs) or 1.0
    durs = [d * clip_len / tot for d in play_durs]

    inputs: list = []
    chains: list = []
    for i, ((s, _e), d) in enumerate(zip(segments, durs)):
        inputs += ["-ss", f"{s:.3f}", "-i", str(source)]
        chains.append(f"[{i}:v]{_norm_chain(d)}[v{i}]")
    concat = "".join(f"[v{i}]" for i in range(len(segments)))
    chains.append(f"{concat}concat=n={len(segments)}:v=1:a=0[vout]")

    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error"]
    cmd += inputs
    amap: list = []
    if narr_audio and Path(narr_audio).exists():
        cmd += ["-i", str(narr_audio)]
        ai = len(segments)
        chains.append(
            f"[{ai}:a]adelay={int(LEAD_IN*1000)}|{int(LEAD_IN*1000)},"
            f"apad,atrim=duration={clip_len:.3f}[aout]")
        amap = ["-map", "[aout]"]
    else:
        chains.append(
            f"anullsrc=r=48000:cl=stereo,atrim=duration={clip_len:.3f}[aout]")
        amap = ["-map", "[aout]"]

    cmd += ["-filter_complex", ";".join(chains), "-map", "[vout]"] + amap
    from pipeline import encoder
    cmd += encoder.video_args("final") + encoder.audio_args()
    cmd += ["-t", f"{clip_len:.3f}", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(
            f"clause clip failed for {out.name}: "
            f"{(r.stderr or '')[-400:]}")
    return clip_len
