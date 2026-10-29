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


def reveal_extra(line: dict) -> float:
    """Extra front silence this line specifically gets, in seconds.

    config.PRE_REVEAL_PAUSE on a <reveal> line, so the reveal arrives out of a
    gap instead of on the heels of the previous sentence.

    THIS IS WHY IT LIVES HERE. The render loop applied it and the pre-flight
    did not, so on every reveal line the pre-flight's required duration was
    0.6s smaller than the one the renderer actually built - 17 lines of this
    draft. None of them produced a short clip, because they happened to have
    the slack, but the two formulas disagreed and a line that passed the
    pre-flight could still violate the binding contract.
    """
    import config
    if str(line.get("delivery") or "") != "reveal":
        return 0.0
    return float(getattr(config, "PRE_REVEAL_PAUSE", 0.0) or 0.0)


def lead_and_clip(narr_dur: float, shot_dur: float, hold: float = 0.0,
                  extra: float = 0.0) -> tuple:
    """(lead, clip_len) - THE arithmetic, in one place.

    Every caller that needs to know how long a narrated line's picture must be
    goes through here: the pre-flight, tools/fit_narration.py and
    render._build_clip. They each had their own copy, and the copies differed
    by the reveal pause.
    """
    from pipeline.render import GAP, _lead_for
    lead = _lead_for(narr_dur, shot_dur, extra=extra)
    return lead, max(lead + float(narr_dur) + GAP, float(hold or 0.0))


def clip_length(line: dict, narr_dur: float = 0.0) -> float:
    """The clip duration render.py will build for this line.

    Mirrors the two branches in render.py:
      hold / film_speaks -> _build_silence_clip, clip_len = the authored hold
      narrated           -> _build_clip, clip_len = max(lead + narr + GAP, hold)
    """
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
    # ONE definition, shared with the pre-flight, the fitter and _build_clip -
    # and it includes the reveal pause, which the pre-flight's own copy did not.
    return lead_and_clip(nd, shot, hold, reveal_extra(line))[1]


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
    from pipeline.render import intro_owned

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
    narr_need = lead_and_clip(nd, shot, 0.0, reveal_extra(line))[1]
    if shot > 0 and narr_need > shot:
        # slowed to fit: the render caps the read at the window
        return a, b
    clip_len = clip_length(line, narr_dur)
    return a, max(b, a + clip_len)


def picture_reach(line: dict, narr_dur: float = 0.0,
                  cuts: list | None = None,
                  censor_region=None) -> tuple:
    """(reach_seconds, why) - the LONGEST video the builder can actually make.

    THE DEFECT THIS EXISTS FOR. clip_024 claimed 8.726s and its video stream
    was 7.367s. The pre-flight had passed the line, and it was right to on its
    own terms: it compared `lead + narr + GAP` (8.726s) against the window's
    capacity (13.583s x 1.15) and saw plenty of room. What it did not model is
    that the builder SPLITS a long line across cuts and gives each sub-shot an
    EQUAL share of the screen time. The splitter chose a cut 2.173s into the
    window, so a 2.173s sub-shot was asked for 4.363s of screen time. It can
    reach 2.173 + 0.5 (read-ahead) + 0.3 (the capped clone) = 2.973s, and
    `trim` only truncates - it cannot extend. Short by 1.390s; measured 1.359s,
    a frame of rounding apart.

    So "does the narration fit the window" and "can the picture supply the
    clip" are different questions, and only the first was being asked. Three
    ceilings bound the answer and all three are applied here:

      * BINDING_SLOWDOWN_MAX - a slowed clip reads its window and stretches it
      * MAX_FREEZE_SEC       - the clone that pads a short segment is capped
      * the split shares     - each sub-shot gets clip_len/n regardless of how
                               much footage it has
    """
    import config
    from pipeline.draft import parse_ts
    from pipeline.schemas import BINDING_SLOWDOWN_MAX

    cs, ce = line.get("clip_start"), line.get("clip_end")
    if not cs or not ce:
        return float("inf"), "no explicit window"
    try:
        a, b = parse_ts(cs), parse_ts(ce)
    except Exception:
        return float("inf"), "unparseable window"
    shot = max(0.0, b - a)
    clone = float(getattr(config, "MAX_FREEZE_SEC", 0.3))

    wordless = (line.get("narration_silence_seconds") is not None
                or line.get("film_speaks_seconds") is not None)
    if wordless:
        # _build_silence_clip reads from `start` with no -t, so the only limit
        # is the source itself.
        return float("inf"), "hold reads to EOF"

    nd = max(0.0, float(narr_dur or 0.0))
    try:
        hold = max(0.0, float(line.get("hold") or 0.0))
    except (TypeError, ValueError):
        hold = 0.0
    lead, clip_len = lead_and_clip(nd, shot, hold, reveal_extra(line))

    # does the builder split this line?
    segs = []
    if cuts:
        try:
            from pipeline.render import _split_points
            segs = _split_points(shot, clip_len, list(cuts), a, b,
                                 censor_region=censor_region) or []
        except Exception:
            segs = []
    if len(segs) >= 2:
        share = clip_len / len(segs)
        reach = 0.0
        worst = None
        for (x, y) in segs:
            avail = (y - x) + 0.5 + clone     # read-ahead + capped clone
            reach += min(share, avail)
            if avail < share and (worst is None or avail - share < worst[0]):
                worst = (avail - share, x, y)
        why = (f"split into {len(segs)} sub-shot(s) at {share:.2f}s each"
               + (f"; the {worst[2] - worst[1]:.2f}s sub-shot at "
                  f"{worst[1]:.2f}s is {-worst[0]:.2f}s short"
                  if worst else ""))
        return reach, why

    narr_need = lead + nd + GAP_()
    if shot > 0 and narr_need > shot:
        # slowed: the read is bounded, and the stretch is capped
        return shot * BINDING_SLOWDOWN_MAX + clone, (
            f"slowed to fit; capped at {BINDING_SLOWDOWN_MAX:.2f}x of a "
            f"{shot:.2f}s window")
    # unslowed single clip: reads to EOF, so only the source bounds it
    return float("inf"), "single unslowed clip reads to EOF"


def GAP_() -> float:
    from pipeline.render import GAP
    return GAP


def short_clips(draft: dict, durs: dict | None = None,
                cuts: list | None = None,
                regions: dict | None = None,
                tol: float | None = None) -> list[dict]:
    """Every line whose PICTURE cannot supply the clip the builder will ask for.

    This is the check that has to run BEFORE any encoding. The per-clip
    verification added with [FILE-CHECK] is correct but stops at the FIRST
    offender, after however many minutes of encoding it took to reach it -
    five lines in this draft were short, so that is five sequential renders to
    discover them one at a time.
    """
    import config
    durs = durs or {}
    regions = regions or {}
    if tol is None:
        tol = 2.0 / float(getattr(config, "OUTPUT_FPS", 30) or 30)
    out = []
    for ln in (draft.get("lines") or []):
        lid = ln.get("id")
        try:
            from pipeline.render import intro_owned
            if intro_owned(ln) or ln.get("pool") or ln.get("montage"):
                continue
        except Exception:
            pass
        nd = float(durs.get(lid) or 0.0)
        need = clip_length(ln, nd)
        if need <= 0:
            continue
        reach, why = picture_reach(ln, nd, cuts, regions.get(lid))
        if reach + tol < need:
            out.append({"line_id": lid, "required": round(need, 3),
                        "reach": round(reach, 3),
                        "short_by": round(need - reach, 3), "why": why})
    out.sort(key=lambda r: -r["short_by"])
    return out


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
