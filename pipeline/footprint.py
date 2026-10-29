"""What footage a line REALLY occupies. One definition, used everywhere.

THE DEFECT
----------
Lines 100 and 101 shared 0.48s of footage at 5637.2s in a finished render.
Their DECLARED windows abut exactly and do not overlap:

    line 101   5631.65 - 5637.17   (5.52s)   a hold of 6.0s
    line 100   5637.17 - 5648.33   (11.16s)

Line 101 is a hold. `_build_silence_clip` plays `clip_len` seconds from
`start` - 6.0s, the authored hold - so it really reaches 5637.65 and runs 0.48s
into line 100's footage. The fitter laid those boundaries out using the
DECLARED windows and never knew.

It is not a hold-only problem. `_build_clip` only passes `-t shot_dur` to
ffmpeg when the footage is being SLOWED; otherwise it reads from `start`
onwards and the output `-t clip_len` decides the length. So any line whose
clip is longer than its window shows real footage past that window. Measured on
this draft: six lines overrun, three of them ordinary narrated lines (54 by
0.85s, 43 by 0.57s, 55 by 0.32s).

So "the footage this line occupies" is NOT [clip_start, clip_end). It is

    [start, start + clip_len)        where clip_len is what the render builds

and the only safe way to keep that consistent is to compute it in ONE place
that mirrors render.py's own branch logic. Before this module, five callers
each had their own version (plan_widen used declared windows, plan_extend
handled holds but not narrated overruns, needed_spans handled holds, the censor
audit handled holds, available_window handled holds) - and the one that got it
wrong is the one that moved the boundaries.
"""
from __future__ import annotations


def clip_length(line: dict, narr_dur: float = 0.0) -> float:
    """The clip duration render.py will build for this line.

    Mirrors the two branches in render.py:
      hold / film_speaks -> _build_silence_clip, clip_len = the authored hold
      narrated           -> _build_clip, clip_len = max(lead + narr + GAP, hold)
    """
    from pipeline.render import GAP, _lead_for
    from pipeline.draft import parse_ts

    hold_raw = line.get("narration_silence_seconds")
    if hold_raw is None:
        hold_raw = line.get("film_speaks_seconds")
    # A wordless unit's length IS its authored hold - the silence builder never
    # consults narration, and a stale mp3 left over from when the line had
    # words must not be allowed to inflate it.
    if hold_raw is not None:
        try:
            return max(0.0, float(hold_raw))
        except (TypeError, ValueError):
            return 0.0

    cs, ce = line.get("clip_start"), line.get("clip_end")
    shot = 0.0
    if cs and ce:
        try:
            shot = max(0.0, parse_ts(ce) - parse_ts(cs))
        except Exception:
            shot = 0.0
    nd = max(0.0, float(narr_dur or 0.0))
    hold = 0.0
    try:
        hold = max(0.0, float(line.get("hold") or 0.0))
    except (TypeError, ValueError):
        hold = 0.0
    return max(_lead_for(nd, shot) + nd + GAP, hold)


def footprint(line: dict, narr_dur: float = 0.0) -> tuple | None:
    """(start, real_end) of the footage this line shows, or None.

    WHEN THE WINDOW IS A CEILING AND WHEN IT IS NOT - this is the whole point,
    and a first version of this function got it wrong in the generous
    direction, which would have reserved footage no line ever shows:

      * SLOWED narrated clip. `_build_clip` passes `-t shot_dur` only when
        setpts_factor > 1, i.e. exactly when the narration does not fit. So a
        line that overruns its window is SLOWED to fit and reads no more than
        the window. real_end = declared end.
      * UNSLOWED clip. No `-t`, so ffmpeg reads from `start` onward and the
        output length decides. Normally clip_len <= shot_dur there, so it stays
        inside the window anyway.
      * WORDLESS unit (hold / film_speaks). `_build_silence_clip` reads
        `clip_len` = the authored hold from `start` with no `-t` at all, so a
        6.0s hold in a 5.52s window really reaches 0.48s past it. THIS is the
        case that put lines 100 and 101 on the same footage.
      * a narrated line carrying an explicit `hold` longer than its window:
        same mechanism.

    So the window is a ceiling for narrated clips and a floor for wordless
    ones, and the test is whether the slowdown engages.
    """
    from pipeline.draft import parse_ts
    from pipeline.render import intro_owned, GAP, _lead_for

    if intro_owned(line) or line.get("pool") or line.get("montage"):
        return None
    cs, ce = line.get("clip_start"), line.get("clip_end")
    if not cs or not ce:
        return None
    try:
        a, b = parse_ts(cs), parse_ts(ce)
    except Exception:
        return None
    shot = max(0.0, b - a)

    wordless = (line.get("narration_silence_seconds") is not None
                or line.get("film_speaks_seconds") is not None)
    if wordless:
        return a, max(b, a + clip_length(line, narr_dur))

    nd = max(0.0, float(narr_dur or 0.0))
    narr_need = _lead_for(nd, shot) + nd + GAP
    if shot > 0 and narr_need > shot:
        # slowed to fit: the render caps the read at the window
        return a, b
    clip_len = clip_length(line, narr_dur)
    return a, max(b, a + clip_len)


def footprints(draft: dict, durs: dict | None = None) -> list[dict]:
    """[{id, a, b, real_b, line}] for every line with a window, in time order.

    `durs` maps line id -> measured narration seconds. Without it a narrated
    line's overrun cannot be known, so its footprint is its declared window -
    which is why the fitter should always pass measured or estimated durations.
    """
    durs = durs or {}
    from pipeline.draft import parse_ts
    out = []
    for ln in draft.get("lines") or []:
        fp = footprint(ln, durs.get(ln.get("id"), 0.0))
        if fp is None:
            continue
        a, real_b = fp
        try:
            b = parse_ts(ln["clip_end"])
        except Exception:
            b = real_b
        out.append({"id": ln.get("id"), "a": a, "b": b, "real_b": real_b,
                    "line": ln})
    out.sort(key=lambda r: r["a"])
    return out


def overlaps(draft: dict, durs: dict | None = None,
             min_overlap: float | None = None) -> list[dict]:
    """Pairs of lines whose REAL footprints overlap."""
    import config
    if min_overlap is None:
        min_overlap = float(getattr(config, "FOOTAGE_REUSE_MIN_OVERLAP_SEC",
                                    0.4))
    rows = footprints(draft, durs)
    hits = []
    for i, r in enumerate(rows):
        for s in rows[i + 1:]:
            if s["a"] >= r["real_b"]:
                break
            ov = min(r["real_b"], s["real_b"]) - max(r["a"], s["a"])
            if ov > min_overlap:
                hits.append({"a_id": r["id"], "b_id": s["id"],
                             "overlap": ov,
                             "a_span": (r["a"], r["real_b"]),
                             "b_span": (s["a"], s["real_b"])})
    return hits
