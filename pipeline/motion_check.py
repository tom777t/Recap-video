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
def _to_source(freeze: dict, shown: list | None,
               intro_offset: float = 0.0) -> tuple | None:
    """Map a freeze in the FINISHED file back to the source span it came from.

    `shown` records carry `out_a`/`out_b` - where each source window landed on
    the render timeline, before the intro was prepended - so the finished-file
    timestamp is offset by `intro_offset` to compare. Returns None when no
    record covers it, which is reported rather than excused.
    """
    if not shown:
        return None
    mid = (float(freeze["start"]) + float(freeze["end"])) / 2.0 \
        - float(intro_offset or 0.0)
    for u in shown:
        oa, ob = u.get("out_a"), u.get("out_b")
        if oa is None or ob is None or ob <= oa:
            continue
        if not (oa <= mid < ob):
            continue
        # proportional position inside the clip -> position inside the window
        frac = (mid - oa) / (ob - oa)
        sa, sb = float(u["a"]), float(u["b"])
        centre = sa + frac * (sb - sa)
        half = max(0.25, float(freeze["dur"]) / 2.0)
        return (max(sa, centre - half), min(sb, centre + half))
    return None


def source_has_motion(ff: str, source: Path, a: float, b: float,
                      noise_db: float | None = None) -> bool | None:
    """Does the SOURCE move over [a, b)? None = could not tell.

    freezedetect on the finished file cannot distinguish the two things that
    make a picture stop moving:

      * the render froze it      - a defect
      * the film is holding on a static shot - a shot, not a defect

    A held close-up, a locked-off establishing shot, a title card and a beat of
    stillness before an impact are all legitimate and common, and flagging them
    produced findings with nothing to fix - which is how a check gets ignored.
    So a freeze is only a freeze where the source MOVED over the same span and
    the render does not.

    Returns None rather than False when the probe fails, so an unknown answer
    is never read as "the source was static" - that would silently suppress
    real freezes.
    """
    import config
    if not source.exists() or b <= a:
        return None
    noise = config.FREEZE_NOISE_DB if noise_db is None else noise_db
    span = max(0.12, b - a)
    r = subprocess.run(
        [ff, "-hide_banner", "-nostats", "-ss", f"{a:.3f}", "-t", f"{span:.3f}",
         "-i", str(source),
         "-vf", f"freezedetect=n={noise}dB:d={min(span * 0.6, 0.2):.3f}",
         "-map", "0:v:0", "-f", "null", "-"],
        capture_output=True, text=True)
    if r.returncode != 0:
        return None
    log = r.stderr or ""
    if "freeze_start" not in log:
        return True                   # no freeze found in the source: it moved
    # The source froze too. Treat it as static only if the frozen stretch
    # covers most of the span - a brief clone inside otherwise moving footage
    # is still moving footage.
    #
    # An UNTERMINATED freeze has to be counted. When the picture is still
    # frozen as the probed span ends, ffmpeg prints freeze_start with no
    # matching freeze_duration - so summing durations alone gave 0 for a
    # solid-colour source and called it "moving", which is exactly backwards
    # and would have left every held shot being flagged.
    starts = [float(m.group(1)) for m in
              re.finditer(r"freeze_start\s*:\s*([\d.]+)", log)]
    durs = [float(m.group(1)) for m in
            re.finditer(r"freeze_duration\s*:\s*([\d.]+)", log)]
    frozen = sum(durs)
    if len(starts) > len(durs) and starts:
        # the last freeze never ended: it runs to the end of the span
        frozen += max(0.0, span - (starts[-1] - a if starts[-1] > a
                                   else starts[-1]))
    return frozen < span * 0.6


def check(ff: str, final: Path, draft: dict, shown: list | None = None,
          intro_offset: float = 0.0, source: Path | None = None) -> tuple[bool, list[str]]:
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
    long_fz = [f for f in fz if f["dur"] > fail_sec]
    near = [f for f in fz if f["dur"] <= fail_sec]
    if near:
        console.print(f"[dim]Motion: {len(near)} frozen stretch(es) under the "
                      f"{fail_sec:.2f}s limit (longest "
                      f"{max(f['dur'] for f in near):.2f}s).[/]")

    # A FROZEN PICTURE IS NOT AUTOMATICALLY A DEFECT. freezedetect cannot tell
    # a render freeze from a shot the film holds still - a locked-off
    # establishing shot, a held close-up, a title card, a beat of stillness
    # before an impact. Flagging those produced findings with nothing to fix.
    # So each long freeze is checked against the SOURCE over the same span: it
    # is a defect only where the source MOVED and the render does not.
    bad_fz, excused, unknown = [], [], []
    for f in long_fz:
        src_span = _to_source(f, shown, intro_offset)
        if source is None or src_span is None:
            unknown.append(f)
            bad_fz.append(f)          # cannot excuse what cannot be checked
            continue
        moved = source_has_motion(ff, source, *src_span)
        if moved is False:
            excused.append((f, src_span))
        elif moved is None:
            unknown.append(f)
            bad_fz.append(f)
        else:
            bad_fz.append(f)
    if excused:
        console.print(
            f"[dim]Motion: {len(excused)} frozen stretch(es) excused - the "
            f"SOURCE is static over the same span, so the film is holding the "
            f"shot: "
            + ", ".join(f"{f['start']:.1f}s (src {a:.1f}s)"
                        for f, (a, _b) in excused[:5]) + "[/]")
    if unknown:
        console.print(
            f"[yellow]Motion: {len(unknown)} frozen stretch(es) could not be "
            f"traced back to a source span, so they are reported rather than "
            f"excused - an unknown answer is not an all-clear.[/]")
    if bad_fz:
        problems.append(
            f"{len(bad_fz)} frozen stretch(es) longer than {fail_sec:.2f}s "
            f"where the SOURCE moves: "
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
