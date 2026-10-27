"""Frozen, slowed and REPEATED footage - prevention rules and a post-render check.

THE THREE DEFECTS
-----------------
All three were visible in the Tokyo Drift render and all three were permitted:

 1. SLOW-MOTION. A bound shot could be stretched to 1.40x to cover a long line.
    The stretch is `setpts` - frame duplication, no interpolation - so past
    roughly 1.15x it reads as judder rather than as a slow-motion effect.
    config.BINDING_SLOWDOWN_MAX is 1.15 now, and the remedy for a line that
    needs more picture is MORE PICTURE: widen the window across the following
    cuts, which the 2f splitter renders as real cuts.
 2. FREEZE. `tpad=stop_mode=clone` had stop_duration set to the whole clip
    length, i.e. no ceiling: a short window under a long line became a still
    image for seconds. Capped at config.MAX_FREEZE_SEC (0.30s).
 3. REUSE. Nothing prevented two lines binding overlapping footage, so the same
    shot could appear twice in one video.

Rules 1 and 2 are enforced where the clip is built. This module is the
INDEPENDENT check on the result, because a freeze has sources the build rules
cannot see: the source footage itself may hold a static frame, a filter graph
mistake can stall a stream, and a cache hit can serve a clip built under older
rules. Prevention and detection are different jobs.

WHAT IT DOES
------------
  freezes(final)        ffmpeg freezedetect over the finished file -> the
                        timestamps of every frozen stretch
  reuse(draft)          source windows that overlap between lines
  check(...)            both, with verdicts, failing on a freeze longer than
                        config.FREEZE_FAIL_SEC or on ANY reuse

Timestamps are reported in the FINISHED file's own clock, including the
prepended intro offset, so a finding can be scrubbed to directly.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()


# --------------------------------------------------------------------------- #
# Freeze detection on the finished file
# --------------------------------------------------------------------------- #
def freezes(ff: str, final: Path, noise_db: float | None = None,
            min_sec: float | None = None) -> list[dict]:
    """Frozen stretches in `final`, as [{start, end, dur}].

    Uses ffmpeg's freezedetect, which reports `lavfi.freezedetect.freeze_start`
    and `freeze_duration` through the metadata log. `d` is the MINIMUM duration
    freezedetect will report; it is set below the failure threshold so the
    report can show near-misses rather than only outright failures.
    """
    import config
    if not final.exists():
        return []
    noise = config.FREEZE_NOISE_DB if noise_db is None else noise_db
    # look for anything at or above half the failure threshold
    d = (float(config.FREEZE_FAIL_SEC) / 2.0) if min_sec is None else min_sec
    d = max(0.1, d)
    cmd = [ff, "-hide_banner", "-nostats", "-i", str(final),
           "-vf", f"freezedetect=n={noise}dB:d={d:.3f}",
           "-map", "0:v:0", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = (r.stderr or "")
    out: list[dict] = []
    cur_start = None
    for m in re.finditer(
            r"freeze_(start|duration|end)\s*:\s*(-?[\d.]+)", log):
        kind, val = m.group(1), float(m.group(2))
        if kind == "start":
            cur_start = val
        elif kind == "duration" and cur_start is not None:
            out.append({"start": cur_start, "dur": val,
                        "end": cur_start + val})
            cur_start = None
    return out


# --------------------------------------------------------------------------- #
# Repeated footage
# --------------------------------------------------------------------------- #
def reuse(draft: dict, shown: list | None = None) -> list[dict]:
    """Pairs of lines whose SOURCE footage overlaps.

    `shown` may be a list of {line_id, a, b, source} as recorded by the render
    (pipeline.censor.UsedFootage items), which is the authority on what
    actually reached the screen - a hold plays past its declared window, and a
    split clip plays only its sub-windows. Falls back to the draft's declared
    windows when that is not available, which is what the draft-time gate uses.
    """
    import config
    from pipeline.draft import parse_ts

    min_ov = float(config.FOOTAGE_REUSE_MIN_OVERLAP_SEC)
    spans: list[tuple[float, float, object, str]] = []
    if shown:
        for u in shown:
            try:
                spans.append((float(u["a"]), float(u["b"]),
                              u.get("line_id"), str(u.get("source") or "clip")))
            except (KeyError, TypeError, ValueError):
                continue
    else:
        for ln in draft.get("lines", []):
            cs, ce = ln.get("clip_start"), ln.get("clip_end")
            if not cs or not ce:
                continue
            try:
                spans.append((parse_ts(cs), parse_ts(ce), ln.get("id"), "clip"))
            except Exception:
                continue
            for seg in (ln.get("montage") or []):
                if isinstance(seg, dict) and seg.get("clip_start"):
                    try:
                        spans.append((parse_ts(seg["clip_start"]),
                                      parse_ts(seg["clip_end"]),
                                      ln.get("id"), "montage"))
                    except Exception:
                        pass

    spans.sort()
    hits = []
    for i, (a1, b1, l1, s1) in enumerate(spans):
        for a2, b2, l2, s2 in spans[i + 1:]:
            if a2 >= b1:
                break                    # sorted: nothing later can overlap
            if l1 == l2 and l1 is not None:
                continue                 # one line's own sub-windows
            ov = min(b1, b2) - max(a1, a2)
            if ov > min_ov:
                hits.append({"line_a": l1, "line_b": l2, "overlap": ov,
                             "a": (a1, b1), "b": (a2, b2),
                             "src_a": s1, "src_b": s2})
    return hits


# --------------------------------------------------------------------------- #
# The combined post-render check
# --------------------------------------------------------------------------- #
def check(ff: str, final: Path, draft: dict, shown: list | None = None,
          intro_offset: float = 0.0) -> tuple[bool, list[str]]:
    """Run both checks. Returns (ok, [problems]) with timestamps.

    Freeze positions are reported in the finished file's clock. `intro_offset`
    is accepted so a caller measuring against the pre-intro timeline can be
    related to it, but freezedetect already runs on the final file, so its
    numbers need no adjustment - the parameter exists to be reported, not
    applied.
    """
    import config
    problems: list[str] = []

    fz = freezes(ff, final)
    fail_sec = float(config.FREEZE_FAIL_SEC)
    bad_fz = [f for f in fz if f["dur"] > fail_sec]
    near = [f for f in fz if f["dur"] <= fail_sec]
    if near:
        console.print(f"[dim]Motion: {len(near)} frozen stretch(es) under the "
                      f"{fail_sec:.2f}s limit (longest "
                      f"{max(f['dur'] for f in near):.2f}s).[/]")
    if bad_fz:
        problems.append(
            f"{len(bad_fz)} frozen stretch(es) longer than {fail_sec:.2f}s: "
            + ", ".join(f"{f['start']:.2f}-{f['end']:.2f}s ({f['dur']:.2f}s)"
                        for f in bad_fz[:8]))

    rp = reuse(draft, shown)
    if rp:
        problems.append(
            f"{len(rp)} pair(s) of lines show the SAME source footage: "
            + ", ".join(
                f"line {h['line_a']} and {h['line_b']} overlap "
                f"{h['overlap']:.1f}s at {max(h['a'][0], h['b'][0]):.1f}s"
                for h in rp[:8]))

    if not problems:
        console.print(f"[cyan]Motion:[/] no freeze over {fail_sec:.2f}s, no "
                      f"repeated footage ({len(fz)} short clone(s) seen).")
    return (not problems), problems


# --------------------------------------------------------------------------- #
# Draft-time prevention: catch reuse before a render
# --------------------------------------------------------------------------- #
def report_reuse(draft: dict) -> list[dict]:
    """Draft-time reuse report. Cheap, and catches it before any encoding."""
    hits = reuse(draft)
    if hits:
        console.print(f"[red][FOOTAGE-REUSE][/] {len(hits)} pair(s) of lines "
                      f"bind overlapping footage - the same shot would appear "
                      f"twice in one video:")
        for h in hits[:10]:
            console.print(f"    line {h['line_a']} "
                          f"{h['a'][0]:.1f}-{h['a'][1]:.1f}s and line "
                          f"{h['line_b']} {h['b'][0]:.1f}-{h['b'][1]:.1f}s "
                          f"overlap {h['overlap']:.1f}s")
    return hits
