"""
One place that decides how video gets encoded.

WHY
`libx264` was hardcoded at ten call sites with two quality tiers chosen by
copy-paste (`VIDEO_PRESET` / `VIDEO_PRESET_INTERMEDIATE`). Adding hardware
encoding to ten call sites independently is how the intro ended up encoded
differently from the story. So: one module, one answer per tier, and the
tier is named at the call site rather than spelled out.

TIERS
  final       - what ships. Every clip is now encoded at this quality ONCE.
  transition  - the 0.28s crossfades. Same quality as final; a separate tier
                only because it must NOT force keyframes mid-piece.
  draft       - 540p preview. Same TIMING as final, lower resolution.

HARDWARE
Intel Quick Sync (`h264_qsv`) when it genuinely works, `libx264` otherwise.
"Genuinely works" is decided by ENCODING SOMETHING, not by reading
`-encoders`: the encoder is listed on machines where it then fails at runtime
because the driver or the GPU will not have it. The probe result is cached in
memory for the process and reported once, out loud.

QUALITY PARITY IS MEASURED, NOT ASSUMED
QSV's `global_quality` is not CRF. The number used here comes from
tools/calibrate_encoder.py, which VMAFs a real 60s sample of the actual film
against libx264 CRF 20 and picks the `global_quality` whose VMAF matches. The
calibrated value lives in docs/stage2/encoder_calibration.json; if that file
is missing we FALL BACK TO libx264 rather than guess a quality number, because
silently shipping a different quality is exactly the class of defect this
repo keeps finding.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import config

CALIBRATION = Path("docs/stage2/encoder_calibration.json")

_probe_cache: dict | None = None


# --------------------------------------------------------------------------- #
# Capability probe
# --------------------------------------------------------------------------- #
def _listed(ff: str) -> bool:
    r = subprocess.run([ff, "-hide_banner", "-encoders"],
                       capture_output=True, text=True)
    return "h264_qsv" in (r.stdout or "")


def probe_qsv(ff: str | None = None, force: bool = False) -> dict:
    """Can this machine actually encode h264_qsv? Decided by doing it.

    Returns {"ok": bool, "why": str, "listed": bool}.
    """
    global _probe_cache
    if _probe_cache is not None and not force:
        return _probe_cache
    ff = ff or config.ffmpeg()
    listed = _listed(ff)
    if not listed:
        _probe_cache = {"ok": False, "listed": False,
                        "why": "h264_qsv not in this ffmpeg's encoder list"}
        return _probe_cache
    # The real test: encode 10 frames of colour bars and require a non-empty
    # file AND exit 0. Listing is not capability.
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "probe.mp4"
        r = subprocess.run(
            [ff, "-hide_banner", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=0.34",
             "-c:v", "h264_qsv", "-global_quality", "25",
             str(out)], capture_output=True, text=True)
        ok = r.returncode == 0 and out.exists() and out.stat().st_size > 0
        why = ("probe encode succeeded" if ok else
               f"probe encode failed: {(r.stderr or '').strip()[-200:]}")
    _probe_cache = {"ok": ok, "listed": True, "why": why}
    return _probe_cache


def calibrated_quality() -> int | None:
    """The VMAF-matched `global_quality`, or None if never calibrated."""
    try:
        d = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    except Exception:
        return None
    q = d.get("chosen_global_quality")
    return int(q) if q is not None else None


def active() -> dict:
    """Which encoder will be used, and why. Safe to call repeatedly."""
    p = probe_qsv()
    q = calibrated_quality()
    if p["ok"] and q is not None:
        return {"codec": "h264_qsv", "global_quality": q,
                "why": f"QSV probe ok, VMAF-calibrated global_quality={q}"}
    if p["ok"] and q is None:
        return {"codec": "libx264", "global_quality": None,
                "why": ("QSV works but is UNCALIBRATED - run "
                        "tools/calibrate_encoder.py. Using libx264 rather "
                        "than guessing a quality number.")}
    return {"codec": "libx264", "global_quality": None, "why": p["why"]}


# --------------------------------------------------------------------------- #
# Tier -> ffmpeg args
# --------------------------------------------------------------------------- #
def output_size(tier: str) -> tuple[int, int]:
    if tier == "draft":
        return (int(config.DRAFT_WIDTH), int(config.DRAFT_HEIGHT))
    return (int(config.OUTPUT_WIDTH), int(config.OUTPUT_HEIGHT))


def video_args(tier: str, keyframe_frames: list[int] | None = None) -> list[str]:
    """Encoder arguments for one tier.

    `keyframe_frames` forces an IDR at those FRAME NUMBERS, which is what
    makes the stream-copy assembly exact: a copy can only start on a keyframe.

    TWO MEASURED FACTS SHAPE THIS, both found by testing on real film rather
    than on colour bars:

    1. KEYFRAMES ARE FORCED BY FRAME NUMBER, never by timestamp. A clip
       written with `-ss <t> -i source` can carry a non-zero start PTS, so a
       time threshold lands on a different frame depending on where in the
       film it was cut. `-force_key_frames 0.266667` put the keyframe on
       frame 8 when seeking to 3127s and on frame 9 when seeking to 0s or
       600.5s. `expr:eq(n,8)` put it on frame 8 at all three. Measured, three
       seek points, both forms.

    2. h264_qsv CANNOT FORCE KEYFRAMES AT ALL on this hardware. Every form -
       a time list, `expr:gte(t,...)`, `expr:eq(n,...)` - produced a single
       keyframe at frame 0 and nothing else, at all three seek points. A
       synthetic testsrc2 clip appeared to work, which cost a long detour:
       testsrc2 changes so violently that the encoder inserts keyframes on
       its own, and that looked like obedience. It was not.

    So when a caller needs forced keyframes, this returns libx264 EVEN IF QSV
    is available and calibrated. That is not a fallback for safety's sake, it
    is the only encoder here that can do the job. QSV is still used wherever
    no copy-cut depends on the result: the crossfade pieces, a caption burn,
    and draft mode.
    """
    if tier not in ("final", "transition", "draft"):
        raise ValueError(f"unknown encode tier {tier!r}")

    a = active()
    args: list[str] = []

    if keyframe_frames:
        # Plain comma. The backslash escape a filtergraph needs is WRONG here
        # - `-force_key_frames` is its own expression parser, not a filter
        # argument, and `eq(n\,8)` fails with "Missing ')' or too many args".
        expr = "+".join(f"eq(n,{int(k)})" for k in keyframe_frames)
        args += ["-force_key_frames", f"expr:{expr}"]
        # QSV cannot honour the above. Silently accepting it would produce a
        # clip with no keyframe where the assembler needs one - the assembler
        # would then refuse to build, which is at least loud, but it is
        # better to not create the situation.
        crf = int(config.VIDEO_CRF)
        preset = config.VIDEO_PRESET
        if tier == "draft":
            crf, preset = int(config.VIDEO_CRF) + 6, "veryfast"
        return args + ["-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                       "-pix_fmt", config.VIDEO_PIX_FMT]

    if a["codec"] == "h264_qsv":
        gq = a["global_quality"]
        if tier == "draft":
            gq = min(51, gq + 6)   # preview: visibly cheaper, same timing
        args += ["-c:v", "h264_qsv",
                 "-global_quality", str(gq),
                 "-look_ahead", "0",
                 "-async_depth", "4",
                 "-pix_fmt", "nv12" if tier != "draft" else "nv12"]
    else:
        crf = int(config.VIDEO_CRF)
        preset = config.VIDEO_PRESET
        if tier == "draft":
            crf, preset = int(config.VIDEO_CRF) + 6, "veryfast"
        args += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                 "-pix_fmt", config.VIDEO_PIX_FMT]
    return args


def audio_args() -> list[str]:
    """One answer for clip audio too.

    `-ar 48000 -ac 2` was present on the story clips and the film-intro block
    but MISSING on the intro montage, which is the kind of mismatch that makes
    a concat-demuxer stream copy refuse the join.
    """
    return ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def describe() -> str:
    a = active()
    p = probe_qsv()
    bits = [f"encoder: {a['codec']}"]
    if a.get("global_quality") is not None:
        bits.append(f"global_quality={a['global_quality']}")
    else:
        bits.append(f"crf={config.VIDEO_CRF} preset={config.VIDEO_PRESET}")
    bits.append(a["why"])
    if not p["ok"] and p["listed"]:
        bits.append("(QSV listed but failed its runtime probe)")
    return " | ".join(bits)
