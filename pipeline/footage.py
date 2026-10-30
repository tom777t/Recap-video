"""Is this stretch of source footage worth putting on screen? Measured.

WHY THIS EXISTS
---------------
The finished Tokyo Drift intro held BLACK for 3.00s at 16.75s and 1.50s at
40.00s, and MOTION-CHECK reported both as frozen - correctly, because a run of
identical black frames is frozen.

Neither was a filter bug. The film-intro block reads the film's own opening,
and `vis_start` was hardcoded to 0.0, so it played the distributor logo fades.
Measured on the source: the first 32 seconds contain exactly 4.50s of black
(t=0.00-2.75 and t=23.25-24.75), which is exactly the 3.00s + 1.50s that
reached the screen, at exactly those offsets past the 16.63s junction.

The function's own docstring said "no frame is described by the narration, so
any calm opening footage is safe". That is the whole error in one sentence: a
logo fade is calm AND black. The story half never hits this because every story
clip is bound to a tagged shot window; the intro picks its own footage and
nothing looked at it.

So: before footage goes on screen, LOOK AT IT.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import config

# Mean luma (0-255) at or below which a frame is "black". Measured on this
# source: logo-fade frames sit at 0.0-0.3, the darkest real scene content in
# the opening sits at 14-18. A bar of 2.0 separates them with an order of
# magnitude to spare.
BLACK_LUMA = 2.0
# ...and a frame this flat is a dissolve or a flash: nothing is legible even if
# it is not black. Judged on the standard deviation of the same small frame.
FLAT_STD = 3.0
# TOO DIM TO PUT A TITLE CARD OVER, which is a stricter question than "is it
# black". The first choice this module made landed on source t=25.0, 0.25s
# after a fade ended: luma 2.6-3.6, above the 2.0 black bar and still a fade in
# progress. Measured on this source's opening, the three populations separate
# cleanly:
#     logo fades / dissolves   0.0 - 3.6
#     fade still rising        4.4 - 12.7
#     real scene content      14.4 - 120.3
# so 8.0 sits inside the gap. Applied ONLY where the pipeline has free choice
# of footage (the intro block, which can pick from ten minutes of film); a
# bound story clip is never rejected for being a night scene.
DIM_LUMA = 8.0
# How finely to sample when profiling. 4fps catches a half-second fade.
PROFILE_FPS = 4.0


def luma_profile(src: Path, lo: float, hi: float,
                 fps: float = PROFILE_FPS) -> list:
    """[(t, mean_luma, std)] across [lo, hi], in ONE decode pass.

    Deliberately one pass over a span rather than a seek per candidate: the
    film-intro search covers minutes of footage, and seeking per candidate made
    the check slow enough that it would have been tempting to skip.
    """
    import numpy as np
    lo = max(0.0, float(lo))
    span = max(0.0, float(hi) - lo)
    if span <= 0:
        return []
    w, h = 64, 36
    cmd = [config.ffmpeg(), "-v", "error", "-ss", f"{lo:.3f}",
           "-t", f"{span:.3f}", "-i", str(src),
           "-vf", f"fps={fps:.4f},scale={w}:{h},format=gray",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    r = subprocess.run(cmd, capture_output=True)
    n = w * h
    buf = r.stdout or b""
    cnt = len(buf) // n
    if cnt == 0:
        return []
    arr = np.frombuffer(buf[:cnt * n], dtype=np.uint8).reshape(cnt, n)
    arr = arr.astype("float32")
    means = arr.mean(axis=1)
    stds = arr.std(axis=1)
    return [(lo + i / fps, float(means[i]), float(stds[i]))
            for i in range(cnt)]


def black_spans(src: Path, lo: float, hi: float,
                min_sec: float = 0.25,
                fps: float = PROFILE_FPS,
                profile: list | None = None) -> list:
    """Spans inside [lo, hi] that are black or too flat to read."""
    prof = profile if profile is not None else luma_profile(src, lo, hi, fps)
    if not prof:
        return []
    step = 1.0 / fps
    bad = [(t, (m <= BLACK_LUMA or s <= FLAT_STD)) for t, m, s in prof]
    out = []
    i = 0
    while i < len(bad):
        if not bad[i][1]:
            i += 1
            continue
        j = i
        while j < len(bad) and bad[j][1]:
            j += 1
        a = bad[i][0]
        b = bad[j - 1][0] + step
        if b - a >= min_sec:
            out.append((round(a, 3), round(b, 3)))
        i = j
    return out


def watchable_start(src: Path, want_sec: float, lo: float, hi: float,
                    avoid: list | None = None,
                    step: float = 0.5,
                    fps: float = PROFILE_FPS) -> tuple:
    """(start, why) for a `want_sec` window inside [lo, hi] with NO black.

    Returns (None, why) when no such window exists, which is a reason to build
    no block at all rather than to ship the best of a bad set - the same
    decision the censor path already makes about flagged footage.

    `avoid` is a list of (a, b) spans the window must not overlap (flagged
    shots, story-bound footage).
    """
    want = max(0.5, float(want_sec))
    lo, hi = max(0.0, float(lo)), float(hi)
    if hi - lo < want:
        return None, f"the search range {lo:.1f}-{hi:.1f}s is shorter than {want:.1f}s"
    prof = luma_profile(src, lo, hi, fps)
    if not prof:
        return None, "could not read any frames to judge"
    bad = black_spans(src, lo, hi, 0.0, fps, profile=prof)
    avoid = [(float(a), float(b)) for a, b in (avoid or [])]
    blocked = bad + avoid

    t = lo
    best = None
    while t + want <= hi + 1e-6:
        a, b = t, t + want
        if not any(x < b and a < y for x, y in blocked):
            seg = [m for (tt, m, s) in prof if a <= tt < b]
            # EVERY frame must clear the dim bar, not just the average. The
            # first version tested the window's MEAN and picked a window whose
            # mean was 70 but whose opening three seconds were a fade at luma
            # 2.6-7.5 - an average cannot see a dark run, and a dark run at the
            # start is exactly what a viewer notices.
            if seg and min(seg) >= DIM_LUMA:
                mean = sum(seg) / len(seg)
                if best is None or mean > best[1]:
                    best = (a, mean, min(seg))
                if best[1] > 25.0:
                    break
        t += step
    if best is None:
        return None, (f"every {want:.1f}s window in {lo:.0f}-{hi:.0f}s "
                      f"contains black, flat or too-dim footage, or is "
                      f"already used ({len(bad)} black span(s), "
                      f"{len(avoid)} avoided)")
    return best[0], (f"clear {want:.1f}s window at {best[0]:.2f}s "
                     f"(mean luma {best[1]:.0f}, darkest frame "
                     f"{best[2]:.0f} >= {DIM_LUMA:.0f}; {len(bad)} black "
                     f"span(s) skipped in {lo:.0f}-{hi:.0f}s)")


def has_black(src: Path, a: float, b: float,
              min_sec: float = 0.25) -> list:
    """Black spans inside one specific window - for verifying a choice."""
    return black_spans(Path(src), a, b, min_sec)
