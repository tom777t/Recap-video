"""fit_narration.py - resolve every capacity overrun found by the pre-flight.

THE PROBLEM
-----------
After the first Warren render, 19 of 102 bound lines had narration that could
not fit their footage window. The cause was not one thing:

  * 15 of them sat in 3.00s windows holding 20-36 words. No voice at any rate
    fits 29 words in 3 seconds. Those windows are RULE A3 anchor points - the
    line's clip_start marks the narrated moment - and the host shot they sit in
    is 11-21s long, with the slack sitting on a NEIGHBOURING line that needed
    almost none of it (line 82 had 3.00s for 12.88s of speech; line 83, inside
    the same 21s shot, had 9.00s for 5.36s). The footage was there; the
    allocation was backwards.
  * a few were 0.02-0.4s over - rounding, not writing.
  * two were genuinely too many words for the moment they describe.

So the resolution order matters, cheapest and least destructive first:

  (a) WIDEN the window using footage of the SAME SHOT. Never crosses a real cut
      (the host shot's own boundaries are cuts), never crosses a reveal landing,
      never collides with a line bound outside that shot. Where several lines
      share one host shot their boundaries are re-allocated so each gets what
      it needs. The picture does not change - it is the same continuous take -
      so nothing the line says about what is on screen stops being true.
  (b) a RATE BUMP on that one line, capped at +8%, written into draft.json as
      `rate_bump` and re-synthesized. Bounded because a bump big enough to fix
      a real overlength problem is a bump you can hear.
  (c) TRIM THE TEXT. Only a writer (or a fresh-context subagent) can decide
      which words carry the payload, so this tool does NOT invent an edit: it
      writes narration_fit_todo.json naming each line, its exact word budget,
      and the facts it must keep, then the trim is made, re-synthesized and
      FACT/SPOILER-audited.

Usage
-----
  python tools/fit_narration.py --project NAME            # dry run, report only
  python tools/fit_narration.py --project NAME --apply    # write draft.json
  python tools/fit_narration.py --project NAME --apply --max-bump 1.08

Nothing is written without --apply. With --apply the draft is backed up to
draft_prefit.json first.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from rich.console import Console  # noqa: E402

console = Console()

# Lower bound on any window we create. Below about a second a cut reads as a
# glitch rather than a shot, however well the narration fits it.
MIN_WINDOW_SEC = 1.20
# Keep a hair of slack when we size a window to its requirement, so float
# rounding cannot leave the render exactly on the contract boundary.
SAFETY_SEC = 0.08
# Headroom required between the fitted audio and the capacity ceiling. A rate
# bump is applied to a request, not to a waveform: the returned audio is a new
# performance and its length varies by a percent or two, because pauses and
# breaths do not scale with speaking rate. Fitting to the boundary therefore
# fails about half the time. Whichever of these two is larger wins.
MARGIN_MIN_SEC = float(getattr(config, "CAPACITY_MARGIN_MIN_SEC", 0.25))
MARGIN_FRACTION = float(getattr(config, "CAPACITY_MARGIN_FRACTION", 0.03))


def _hms(t: float) -> str:
    t = max(0.0, float(t))
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def required_window(narr_dur: float) -> float:
    """Smallest window that satisfies the binding contract for this audio.

    render.py's check is
        need = _lead_for(narr, w) + narr + GAP   and   need <= w * SLOWDOWN
    and _lead_for clamps the lead to `w*SLOWDOWN - narr - GAP`, so whenever the
    lead is clamped `need` lands at the capacity and passes. The condition
    therefore reduces exactly to
        narr + GAP <= w * SLOWDOWN
    which is solvable rather than something to search for.
    """
    from pipeline.schemas import BINDING_SLOWDOWN_MAX
    from pipeline.render import GAP
    return (float(narr_dur) + GAP) / BINDING_SLOWDOWN_MAX + SAFETY_SEC


# --------------------------------------------------------------------------- #
# the picture: shots, cuts, reveal holds, and who is bound where
# --------------------------------------------------------------------------- #
def _load_shots(pdir: Path) -> list[tuple[float, float, str]]:
    from pipeline.draft import parse_ts
    for cand in ("shots.json", "shots_machine.json"):
        p = pdir / cand
        if not p.exists():
            continue
        try:
            shots = json.loads(p.read_text(encoding="utf-8-sig"))["shots"]
        except Exception:
            continue
        out = []
        for s in shots:
            cs, ce = s.get("clip_start"), s.get("clip_end")
            if not cs or not ce:
                continue
            try:
                a, b = parse_ts(cs), parse_ts(ce)
            except Exception:
                continue
            if b > a:
                out.append((a, b, str(s.get("id") or "")))
        out.sort()
        return out
    return []


def _reveal_lands(project: str) -> list[float]:
    """Absolute seconds where each reveal lands.

    A window must not be widened ACROSS one of these: the footage after a
    reveal lands shows the reveal, and pulling it under an earlier line puts
    the twist on screen before the narration gets there. This is the same rule
    the intro montage obeys.
    """
    try:
        from pipeline.draft import parse_reveal_map
        out = []
        for r in parse_reveal_map(project) or []:
            v = r.get("land_sec")
            if v is None:
                continue
            out.append(float(v))
        return sorted(out)
    except Exception:
        return []


def _host_of(shots: list, a: float) -> tuple[float, float, str] | None:
    for s in shots:
        if s[0] - 0.6 <= a < s[1]:
            return s
    return None


# --------------------------------------------------------------------------- #
# strategy (a): widen / re-allocate inside the host shot
# --------------------------------------------------------------------------- #
def _need_for(line: dict, narr_dur: float) -> float:
    """Footage a line must be given.

    A narrated line needs required_window(): the render SLOWS it to fit, so the
    window is the ceiling. A WORDLESS unit (hold / film_speaks) is not slowed
    at all - _build_silence_clip reads its authored length straight from the
    source - so it needs that length, or the next line is handed footage this
    one will play.
    """
    from pipeline import footprint as _fp
    if (line.get("narration_silence_seconds") is not None
            or line.get("film_speaks_seconds") is not None):
        # EXACTLY the hold, with no SAFETY_SEC. That margin exists to absorb
        # TTS measurement jitter - a synthesized line may come back a little
        # longer than predicted. A hold is an authored constant with no
        # measurement in it, so adding safety there just widens windows that
        # are already exactly right: it proposed +0.08s on lines 75 and 110,
        # whose holds equal their windows to the frame, and on 110 it would
        # have pushed a film_speaks window 0.08s past the span whose audio
        # cleanliness was actually measured.
        return max(MIN_WINDOW_SEC, _fp.clip_length(line, narr_dur))
    return required_window(narr_dur)


def plan_widen(draft: dict, pdir: Path, project: str,
               durs: dict, src_dur: float = 0.0) -> tuple[dict, list]:
    """Re-allocate window boundaries inside each host shot.

    Returns ({line_id: (new_start, new_end)}, [notes]). Only lines that need a
    change are present. Everything here stays inside ONE host shot, so no real
    cut is crossed and the shot on screen for each line is unchanged.
    """
    from pipeline.draft import parse_ts
    from pipeline import footprint as _fpm
    from pipeline.render import intro_owned

    shots = _load_shots(pdir)
    lands = _reveal_lands(project)
    notes: list = []
    if not shots:
        notes.append("no shots.json - cannot widen windows without knowing "
                     "where the real cuts are")
        return {}, notes

    # every explicitly bound line, in time order
    bound = []
    for ln in draft["lines"]:
        if intro_owned(ln) or ln.get("pool") or ln.get("montage"):
            continue
        cs, ce = ln.get("clip_start"), ln.get("clip_end")
        if not cs or not ce:
            continue
        try:
            a, b = parse_ts(cs), parse_ts(ce)
        except Exception:
            continue
        _fp = _fpm.footprint(ln, durs.get(ln["id"], 0.0))
        bound.append({"id": ln["id"], "a": a, "b": b, "ln": ln,
                      "real_b": _fp[1] if _fp else b})
    bound.sort(key=lambda r: r["a"])

    # group by host shot
    groups: dict = {}
    for r in bound:
        h = _host_of(shots, r["a"])
        key = (h[0], h[1]) if h else None
        groups.setdefault(key, []).append(r)

    new: dict = {}
    crossed: set = set()
    for key, members in groups.items():
        if key is None:
            continue
        hs, he = key
        members.sort(key=lambda r: r["a"])

        # How far may this group's footage reach? Not past the host shot (that
        # is a cut), not past a line bound OUTSIDE this shot, not past a reveal
        # landing that falls after the group starts.
        span_lo = min(m["a"] for m in members)
        limit = he

        # MULTI-SHOT EXTENSION (2026-10-27). This used to stop at the host
        # shot's end, on the reasoning that crossing a real cut changes the
        # picture mid-line. With BINDING_SLOWDOWN_MAX cut to 1.15 that
        # reasoning inverts: the alternative to crossing a cut is stretching
        # one shot, and setpts stretching is frame duplication that reads as
        # judder. Real footage with a real cut in it is better picture than the
        # same shot slowed down, so a window may now run on across the
        # following cuts - which is what multi-shot binding means. The limit is
        # the NEXT BOUND LINE, not the next cut.
        #
        # A window that ALREADY runs past its host shot stays grandfathered;
        # clamping it back made a line worse (line 108 went from a 1.46x
        # problem to 2.24x when it was cut from 12.00s to 7.88s).
        # How far this group may reach. The next BOUND LINE is the real
        # constraint, not the host shot's end: footage between the host shot
        # and the next line belongs to nobody, and real footage with a real cut
        # in it is better picture than one shot slowed down.
        #
        # This used to be `max(he, max(members' ends))` and then only ever
        # `min()`-ed downward, so the limit could never exceed the host shot's
        # end - the same-shot widen was the ONLY thing that ever ran, and
        # anything it could not fix went straight to a rate bump or a trim
        # while 71 minutes of unused footage sat in 75 gaps across the film.
        limit = max(he, max(m["b"] for m in members))
        for r in bound:
            if r["a"] >= members[-1]["b"]:
                limit = max(limit, r["a"])
                break
        else:
            if src_dur:
                limit = max(limit, float(src_dur))
        # A reveal landing is still absolute: footage from after a reveal lands
        # shows the reveal, and pulling it under an earlier line puts the twist
        # on screen before the narration gets there.
        for L in lands:
            if L > span_lo:
                limit = min(limit, L)
                break
        if src_dur:
            limit = min(limit, float(src_dur))

        # A WORDLESS unit needs its HOLD reserved, not its narration. It has
        # no narration, so required_window() returns almost nothing and the
        # layout handed the next line the footage the hold actually plays -
        # which is exactly how a 6.0s hold in a 5.52s window ran 0.48s into
        # line 100.
        need = {m["id"]: _need_for(m["ln"], durs.get(m["id"], 0.0))
                for m in members}
        available = limit - span_lo
        if available <= 0:
            continue

        cur_len = {m["id"]: m["b"] - m["a"] for m in members}
        over = [m for m in members
                if cur_len[m["id"]] + 1e-6 < need[m["id"]]]
        if not over:
            continue      # nobody in this shot needs more room

        # THE INVARIANT: this pass may never leave a line worse off than it
        # started. A line keeps at least what it has, unless it has genuine
        # SLACK (its audio needs less than its window), in which case it may be
        # asked down to its own requirement and no further. Anything that still
        # does not fit after that is not a footage problem and is handed to the
        # rate bump / text trim - shrinking it here would just move the damage.
        floor = {m["id"]: max(MIN_WINDOW_SEC,
                              min(cur_len[m["id"]], need[m["id"]]))
                 for m in members}
        want = {m["id"]: max(cur_len[m["id"]], need[m["id"]])
                for m in members}

        if sum(want.values()) > available:
            # take back slack only, proportionally, never below the floor
            excess = sum(want.values()) - available
            slack_tot = sum(want[i] - floor[i] for i in want)
            if slack_tot <= 1e-9:
                notes.append(
                    f"shot {hs:.1f}-{he:.1f}s: lines "
                    f"{[m['id'] for m in members]} need "
                    f"{sum(need[m['id']] for m in members):.1f}s but only "
                    f"{available:.1f}s is reachable without crossing a cut or "
                    f"a reveal, and no line here has slack to give - leaving "
                    f"these windows alone; rate/trim will handle it")
                continue
            take = min(1.0, excess / slack_tot)
            want = {i: want[i] - (want[i] - floor[i]) * take for i in want}

        if sum(want.values()) > available + 1e-6:
            notes.append(
                f"shot {hs:.1f}-{he:.1f}s: lines "
                f"{[m['id'] for m in members]} cannot all fit in the "
                f"{available:.1f}s reachable here - widening what can be "
                f"widened, residue goes to rate/trim")

        cur = span_lo
        for m in members:
            w = want[m["id"]]
            na, nb = cur, cur + w
            cur = nb
            # never hand back something smaller than the floor
            if (nb - na) + 1e-6 < floor[m["id"]]:
                nb = na + floor[m["id"]]
                cur = nb
            if abs(na - m["a"]) > 1e-3 or abs(nb - m["b"]) > 1e-3:
                new[m["id"]] = (na, nb)
                # Record whether this window now runs past its host shot, so
                # the report can tell a same-shot widen from a MULTI-SHOT
                # extension. Since the limit became "the next bound line"
                # rather than "the host shot's end", this routine does both -
                # and reporting both as "widened (same shot)" was simply
                # wrong about what it had done.
                if nb > he + 0.05:
                    crossed.add(m["id"])

    # Assert the invariant rather than trusting it: a bug here silently
    # degrades footage, which is the hardest kind of damage to notice later.
    for lid, (na, nb) in new.items():
        m = next(r for r in bound if r["id"] == lid)
        req = _need_for(r["ln"], durs.get(lid, 0.0))
        allowed_floor = max(MIN_WINDOW_SEC, min(m["b"] - m["a"], req)) - 1e-3
        if (nb - na) < allowed_floor:
            raise AssertionError(
                f"fit_narration would shrink line {lid} from "
                f"{m['b']-m['a']:.2f}s to {nb-na:.2f}s, below its floor "
                f"{allowed_floor:.2f}s - refusing to make a line worse")
    return new, notes, crossed


def plan_extend(draft: dict, pdir: Path, project: str, durs: dict,
                src_dur: float = 0.0) -> tuple[dict, list]:
    """STAGE B - MULTI-SHOT EXTENSION into adjacent footage nobody uses.

    Runs after the same-shot widen, for lines that still do not fit. Grows a
    window across SHOT BOUNDARIES into genuinely free footage - the gaps
    between bound windows - forward first (which keeps clip_start, the RULE A3
    anchor on the narrated moment), then backward if forward is not enough.

    Why this is the right second resort, ahead of a rate bump or a trim:
    BINDING_SLOWDOWN_MAX is 1.15, so the alternative to more footage is
    stretching one shot with setpts frame duplication, which reads as judder.
    Real footage with a real cut in it is better picture - and the 2f splitter
    already cuts a long window at its real cuts, so a multi-shot window renders
    as cuts rather than as a seam.

    THIS STAGE DID NOT EXIST. The widener only ever grew a window inside its
    host shot and then handed everything else to the rate bump and the trim
    worklist - while 71 minutes of unused footage sat in 75 gaps across the
    film.

    Bounds, in order of absoluteness:
      * never into another line's footage (that is [FOOTAGE-REUSE]), counting a
        hold's REAL footprint, which runs past its declared end
      * never across a reveal landing (that puts the twist on screen early)
      * never past the source
    """
    from pipeline.draft import parse_ts
    from pipeline import footprint as _fpm
    from pipeline.render import intro_owned

    lands = _reveal_lands(project)
    notes: list = []

    bound = []
    for ln in draft["lines"]:
        if intro_owned(ln) or ln.get("pool") or ln.get("montage"):
            continue
        cs, ce = ln.get("clip_start"), ln.get("clip_end")
        if not cs or not ce:
            continue
        try:
            a, b = parse_ts(cs), parse_ts(ce)
        except Exception:
            continue
        # The REAL footprint, from the one shared definition. A local
        # hold-only version lived here and missed that the same mechanism
        # applies to a narrated line carrying an explicit hold - and
        # plan_widen had no version at all, which is how lines 100 and 101
        # ended up on the same 0.48s of footage.
        _fp = _fpm.footprint(ln, durs.get(ln["id"], 0.0))
        real_b = _fp[1] if _fp else b
        bound.append({"id": ln["id"], "a": a, "b": b, "real_b": real_b,
                      "ln": ln})
    bound.sort(key=lambda r: r["a"])

    new: dict = {}
    for i, r in enumerate(bound):
        lid = r["id"]
        if r["ln"].get("film_speaks_seconds") is not None:
            continue                      # its span IS the quote; never move it
        req = required_window(durs.get(lid, 0.0))
        cur = r["b"] - r["a"]
        if cur + 1e-6 >= req:
            continue                      # already fits

        prev_end = bound[i - 1]["real_b"] if i else 0.0
        next_start = bound[i + 1]["a"] if i + 1 < len(bound) else (
            float(src_dur) if src_dur else r["b"])
        fwd_cap, back_cap = next_start, prev_end
        for L in lands:
            if L >= r["b"]:
                fwd_cap = min(fwd_cap, L)
                break
        for L in reversed(lands):
            if L <= r["a"]:
                back_cap = max(back_cap, L)
                break
        if src_dur:
            fwd_cap = min(fwd_cap, float(src_dur))

        a_new, b_new = r["a"], min(fwd_cap, r["a"] + req)
        if (b_new - a_new) + 1e-6 < req:
            short = req - (b_new - a_new)
            a_new = max(back_cap, a_new - short)
        got = b_new - a_new
        if got <= cur + 0.05:
            continue                      # nothing gained; leave it alone
        new[lid] = (a_new, b_new)
        if got + 1e-6 < req:
            notes.append(
                f"line {lid}: extended to {got:.1f}s of the {req:.1f}s needed "
                f"(free footage runs out at {prev_end:.0f}s / "
                f"{next_start:.0f}s)")

    # The invariant that matters: no two windows may overlap after this.
    merged = []
    for r in bound:
        a, b = new.get(r["id"], (r["a"], r["b"]))
        merged.append((a, b, r["id"]))
    merged.sort()
    for (a1, b1, i1), (a2, b2, i2) in zip(merged, merged[1:]):
        if a2 < b1 - 1e-6:
            raise AssertionError(
                f"multi-shot extension overlapped line {i1} "
                f"({a1:.2f}-{b1:.2f}) with line {i2} ({a2:.2f}-{b2:.2f}) - "
                f"that is the footage-reuse defect, refusing to write it")
    return new, notes


def plan_merge_short(draft: dict, durs: dict,
                     min_words: int = 12) -> tuple[list, list]:
    """STAGE D - a line too short to be worth its own shot merges with a
    neighbour.

    A 10-word line in a 3-second window cannot be rate-bumped or trimmed into
    fitting: asking it to become 5 words does not leave a sentence, it leaves a
    fragment. Such a line belongs with the one next to it, sharing one window
    and one breath.

    Returns ([(victim_id, host_id)], notes). The MERGE ITSELF is a writing act -
    two sentences have to become one that reads - so this proposes the pairs
    and the wording is done by the trim subagent. Merging by arithmetic would
    be the same mistake as trimming by arithmetic.
    """
    from pipeline.draft import parse_ts
    pairs, notes = [], []
    lines = draft["lines"]
    for i, ln in enumerate(lines):
        if (ln.get("film_speaks_seconds") is not None
                or ln.get("narration_silence_seconds") is not None):
            continue
        txt = str(ln.get("narration") or "").strip()
        if not txt:
            continue
        w = len(txt.split())
        if w > min_words:
            continue
        cs, ce = ln.get("clip_start"), ln.get("clip_end")
        if not cs or not ce:
            continue
        try:
            win = parse_ts(ce) - parse_ts(cs)
        except Exception:
            continue
        if required_window(durs.get(ln["id"], 0.0)) <= win + 1e-6:
            continue                      # it fits; nothing to merge
        host = None
        for j in (i - 1, i + 1):
            if 0 <= j < len(lines):
                cand = lines[j]
                if (str(cand.get("narration") or "").strip()
                        and cand.get("film_speaks_seconds") is None
                        and cand.get("narration_silence_seconds") is None
                        and cand.get("clip_start")):
                    host = cand
                    break
        if host is None:
            continue
        pairs.append((ln["id"], host["id"]))
        notes.append(
            f"line {ln['id']}: {w} words in {win:.1f}s cannot be trimmed into "
            f"fitting - merge it with line {host['id']}")
    return pairs, notes


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="write draft.json (default: report only)")
    ap.add_argument("--widen-only", action="store_true",
                    help="apply strategy (a) ONLY - widen windows - and skip "
                         "the rate bumps and trim worklist. Widening depends "
                         "only on knowing a line is short of room, so it is "
                         "sound even from an estimate; a rate bump or a trim "
                         "sized against a guess removes words that may not "
                         "need removing. Use this before the first TTS pass, "
                         "then run again without it once the audio is real.")
    ap.add_argument("--use-estimate", action="store_true",
                    help="work from the DRAFT-TIME estimate instead of the "
                         "real audio. For when the narration is stale (the "
                         "voice mapping or the text changed) or does not exist "
                         "yet - this lets capacity be fixed BEFORE paying for "
                         "TTS. Window widening is exact either way; only the "
                         "rate/trim decisions depend on the duration, and the "
                         "pre-flight re-checks them on the real audio.")
    ap.add_argument("--max-bump", type=float, default=None,
                    help="ceiling for the per-line rate bump. Defaults to the "
                         "voice-consistency band (config.VOICE_RATE_BAND) - a "
                         "bump big enough to fix a real overlength problem is "
                         "a bump you can hear as a second narrator.")
    a = ap.parse_args()

    # A rate bump is a voice change, so it answers to the voice band, not to a
    # number of its own. Capping these separately is how one line ended up
    # outside the band that every tag respects.
    _band_cap = round(1.0 + float(config.VOICE_RATE_BAND), 4)
    if a.max_bump is None:
        a.max_bump = _band_cap
    elif a.max_bump > _band_cap:
        console.print(f"[yellow]--max-bump {a.max_bump:.3f} exceeds the "
                      f"+-{config.VOICE_RATE_BAND:.0%} voice band; clamping to "
                      f"{_band_cap:.3f}.[/]")
        a.max_bump = _band_cap

    from pipeline import preflight as pf
    from pipeline.draft import parse_ts

    pdir = Path(config.project_dir(a.project))
    draft = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    ndir = pdir / "narration"

    # Measure the REAL audio for every line that has some.
    narration = []
    for ln in draft["lines"]:
        p = ndir / f"line_{ln['id']:03d}.mp3"
        if p.exists():
            narration.append((ln["id"], p, 0.0))

    # Staleness is judged BEFORE the bumps are reset, because the files on disk
    # were synthesized with those bumps - that is what their signatures say.
    stale = set(pf.stale_audio(draft, pdir))

    # ---- RESET every previous rate_bump before re-fitting ------------------
    # A bump is an absolute property of a line, so a re-fit must start from the
    # BASE rate and decide again. Carrying the old value in and multiplying is
    # how 1.08 became 1.188 and then 1.283 - outside the +-10% voice band that
    # every delivery tag respects.
    #
    # The audio on disk is still the BUMPED reading, so it is not thrown away:
    # dividing the bump back out recovers the base duration. Pauses do not
    # scale perfectly with rate, so that is approximate - but it is a
    # measurement of this line's actual speech, which beats a word-count
    # estimate by a wide margin.
    old_bumps = {ln["id"]: float(ln["rate_bump"])
                 for ln in draft["lines"] if ln.get("rate_bump")}
    if old_bumps:
        for ln in draft["lines"]:
            ln.pop("rate_bump", None)
        _worst = max(old_bumps.values())
        console.print(
            f"[yellow]Reset {len(old_bumps)} previous rate_bump(s)[/] "
            f"(worst was {_worst:.3f}x) - re-fitting from the base rate so "
            f"bumps cannot compound past the "
            f"{1.0 + config.VOICE_RATE_BAND:.2f}x band.")
    if a.use_estimate:
        # Durations from the draft-time estimate. Honest about what this is:
        # the estimate is weaker evidence than a measurement, so the pre-flight
        # re-checks everything on the real audio at render time. But window
        # WIDENING does not depend on the duration being exact - it only needs
        # to know a line is short of room - so fixing capacity before paying
        # for a TTS pass is worth doing.
        from pipeline.schemas import estimate_narration_seconds as _est
        durs = {}
        for ln in draft["lines"]:
            if (ln.get("narration_silence_seconds") is not None
                    or ln.get("film_speaks_seconds") is not None):
                continue
            txt = str(ln.get("narration") or "").strip()
            if not txt:
                continue
            durs[ln["id"]] = _est(len(txt.split()),
                                  ln.get("delivery"), ln.get("rate_bump"))
        narration = [(lid, ndir / f"line_{lid:03d}.mp3", d)
                     for lid, d in durs.items()]
        console.print(f"[yellow]Working from the draft-time ESTIMATE[/] for "
                      f"{len(durs)} line(s)"
                      + (f" ({len(stale)} have stale audio)" if stale else "")
                      + ". The pre-flight will re-check on the real audio.")
        findings = pf.capacity_findings(draft, narration)
    else:
        if not narration:
            console.print("[red]No narration/*.mp3 - run the render once so "
                          "the real audio exists, or pass --use-estimate to "
                          "work from word counts.[/]")
            return 1
        if stale:
            console.print(
                f"[yellow]{len(stale)} line(s) have audio that no longer "
                f"matches their text or rate_bump, so measuring them would "
                f"judge the wrong waveform. They are SKIPPED. Pass "
                f"--use-estimate to fit them from word counts instead.[/]")
        durs = {}
        ffp = config.ffprobe()
        for lid, p, _d in narration:
            if lid in stale:
                continue
            _m = pf._audio_dur(ffp, p)
            # UN-SCALE a previous bump. The file was synthesized at old_bump,
            # so it is shorter than this line's base reading; the fit has to
            # reason about the BASE, because the bump it is about to choose
            # replaces the old one rather than stacking on it.
            _ob = old_bumps.get(lid)
            if _ob and _ob > 1.0:
                _m *= 1.0 + (_ob - 1.0) * 0.90
            durs[lid] = _m
        # judge capacity on those un-scaled durations, not on the raw files
        narration = [(lid, ndir / f"line_{lid:03d}.mp3", durs.get(lid, 0.0))
                     for lid, _p, _d in narration]
        findings = pf.capacity_findings(draft, narration, skip_ids=stale)

    if not findings:
        console.print("[green]No capacity overruns - nothing to fit.[/]")
        return 0

    console.print(f"[cyan]fit_narration:[/] {len(findings)} overrun(s) on "
                  f"{a.project}")

    by_id = {ln["id"]: ln for ln in draft["lines"]}
    actions: dict = {}

    # ---- (a) widen inside the host shot ---------------------------------- #
    # Source duration bounds any extension: a window may not run off the end
    # of the film.
    _src_dur = 0.0
    try:
        import subprocess as _sp
        _r = _sp.run([config.ffprobe(), "-v", "error", "-show_entries",
                      "format=duration", "-of", "default=nw=1:nk=1",
                      str(pdir / "source.mp4")], capture_output=True, text=True)
        _src_dur = float((_r.stdout or "0").strip())
    except Exception:
        _src_dur = 0.0

    widen, notes, crossed = plan_widen(draft, pdir, a.project, durs,
                                       src_dur=_src_dur)
    for n in notes:
        console.print(f"[yellow]  note: {n}[/]")

    for lid, (na, nb) in sorted(widen.items()):
        ln = by_id.get(lid)
        if ln is None:
            continue
        old = (parse_ts(ln["clip_start"]), parse_ts(ln["clip_end"]))
        actions[lid] = {
            "strategy": ("b-extend" if lid in crossed else "a-widen"),
            "from": f"{old[0]:.2f}-{old[1]:.2f} ({old[1]-old[0]:.2f}s)",
            "to": f"{na:.2f}-{nb:.2f} ({nb-na:.2f}s)",
            "new_start": _hms(na), "new_end": _hms(nb),
        }

    # Apply the widening in memory so the next stage judges the NEW windows.
    for lid, act in actions.items():
        by_id[lid]["clip_start"] = act["new_start"]
        by_id[lid]["clip_end"] = act["new_end"]

    # ---- (b) MULTI-SHOT EXTENSION into free adjacent footage -------------- #
    # Ahead of any rate bump or trim: at a 1.15x slow-motion ceiling the
    # alternative to more footage is frame-duplication judder, and real footage
    # with a real cut in it looks better than one shot slowed down.
    extend, xnotes = plan_extend(draft, pdir, a.project, durs,
                                 src_dur=_src_dur)
    for n in xnotes:
        console.print(f"[yellow]  note: {n}[/]")
    for lid, (na, nb) in sorted(extend.items()):
        ln = by_id.get(lid)
        if ln is None:
            continue
        old = (parse_ts(ln["clip_start"]), parse_ts(ln["clip_end"]))
        prev = actions.get(lid, {}).get("strategy")
        actions[lid] = {
            "strategy": (f"{prev}+b-extend" if prev else "b-extend"),
            "from": actions.get(lid, {}).get(
                "from", f"{old[0]:.2f}-{old[1]:.2f} ({old[1]-old[0]:.2f}s)"),
            "to": f"{na:.2f}-{nb:.2f} ({nb-na:.2f}s)",
            "new_start": _hms(na), "new_end": _hms(nb),
        }
        ln["clip_start"] = _hms(na)
        ln["clip_end"] = _hms(nb)

    still = pf.capacity_findings(draft, narration)
    if a.widen_only and still:
        console.print(
            f"[yellow]--widen-only:[/] {len(still)} line(s) still overrun "
            f"after widening. Not sizing a rate bump or a trim against "
            f"{'an estimate' if a.use_estimate else 'this audio'} - re-run "
            f"without --widen-only once the narration is current, and the "
            f"pre-flight will measure them.")
        still = []

    # ---- (d) SHORT LINES MERGE, before anything is trimmed ---------------- #
    # Identified here, ahead of the rate bump, because a line this short is not
    # a capacity problem the other stages can solve: line 31 held 10 words in
    # 3 seconds and the trim stage asked it to become FIVE, which is not a
    # sentence. Such a line belongs with its neighbour. The wording is a
    # writing act, so these go to the subagent worklist rather than being
    # merged by arithmetic.
    merge_pairs, mnotes = plan_merge_short(draft, durs)
    merge_ids = {v for v, _h in merge_pairs}
    for n in mnotes:
        console.print(f"[yellow]  merge: {n}[/]")
    for _v, _h in merge_pairs:
        prev = actions.get(_v, {}).get("strategy")
        actions[_v] = {
            "strategy": (f"{prev}+d-merge" if prev else "d-merge"),
            "merge_with": _h,
            "note": f"too short to carry its own shot - merge with line {_h}",
            **{k: v for k, v in actions.get(_v, {}).items()
               if k in ("from", "to", "new_start", "new_end")},
        }

    # ---- (c) bounded rate bump ------------------------------------------- #
    trim_todo = []
    hold_todo = []
    for f in still:
        lid = f["line_id"]
        if lid in merge_ids:
            continue          # a merge candidate is not a rate/trim candidate
        ln = by_id[lid]
        shot = f["shot_dur"]
        if f.get("wordless"):
            # A HOLD CANNOT BE RATE-BUMPED. There are no words to read faster,
            # and stamping a rate_bump on a wordless line would mark its
            # (nonexistent) audio stale and send it to the TTS pass forever.
            # The only lever a hold has is its own LENGTH, so if widening and
            # extending could not find it enough footage, shorten the hold to
            # what it did get. That is the wordless equivalent of a text trim,
            # and it is the cheapest edit in the film: a silence 0.06s shorter.
            got = shot
            if lid in actions and actions[lid].get("new_end") is not None:
                # these are timestamp STRINGS, not seconds
                got = parse_ts(str(actions[lid]["new_end"])) \
                    - parse_ts(str(actions[lid]["new_start"]))
            new_hold = round(max(0.1, got), 3)
            key = ("film_speaks_seconds"
                   if ln.get("film_speaks_seconds") is not None
                   else "narration_silence_seconds")
            prev = actions.get(lid, {}).get("strategy")
            actions.setdefault(lid, {})
            actions[lid].update({
                "strategy": (f"{prev}+c-hold" if prev else "c-hold"),
                "hold_key": key,
                "hold": new_hold,
                "note": (f"hold {float(ln.get(key)):.2f}s -> {new_hold:.2f}s "
                         f"to fit the {got:.2f}s of footage it was given"),
                "hold_was": float(ln.get(key)),
            })
            ln[key] = new_hold
            hold_todo.append(lid)
            continue
        # what multiplier would make the audio fit this window?
        from pipeline.schemas import BINDING_SLOWDOWN_MAX
        from pipeline.render import GAP
        # SAFETY MARGIN, not 1e-3. Fitting a line to land exactly on its
        # capacity assumes the re-synthesized audio comes back the predicted
        # length, and it does not: a rate bump does not scale pauses, so the
        # result lands a percent or two either side. Six lines in the first fit
        # pass came out with under 0.1s of headroom, which is inside that
        # error - they would have bounced straight back off the pre-flight on
        # the next render. Leave room.
        cap_full = shot * BINDING_SLOWDOWN_MAX
        margin = max(MARGIN_MIN_SEC, MARGIN_FRACTION * cap_full)
        allowed_narr = cap_full - GAP - margin
        if allowed_narr <= 0:
            need_mult = 999.0
        else:
            need_mult = f["narr_dur"] / allowed_narr
        cur = float(ln.get("rate_bump") or 1.0)
        if need_mult <= a.max_bump + 1e-9:
            mult = round(max(need_mult, 1.0) * 1.01, 4)   # 1% margin
            mult = min(mult, a.max_bump)
            prev = actions.get(lid, {}).get("strategy")
            actions[lid] = {
                "strategy": (f"{prev}+c-rate" if prev else "c-rate"),
                "rate_bump": mult,
                "note": (f"needs {need_mult:.3f}x, applying {mult:.3f}x "
                         f"(cap {a.max_bump:.2f}x)"),
                **({k: v for k, v in actions.get(lid, {}).items()
                    if k in ("from", "to", "new_start", "new_end")}),
            }
            # ABSOLUTE, never compounded. This line used to be
            #     mult if cur == 1.0 else round(cur * mult, 4)
            # which multiplied the NEW bump onto whatever an earlier fit pass
            # had already set. Two passes took 1.08 to 1.188 and three took
            # line 86 to 1.283 - all outside the +-10% voice band that every
            # delivery tag respects, so the "one narrator" contract was being
            # broken by the tool that is supposed to respect it. A rate_bump is
            # a property of the line, not an increment to apply again.
            ln["rate_bump"] = mult
        else:
            # (c) the text is the problem - but spend the rate budget FIRST so
            # the text loses as little as possible. Trimming against the
            # unbumped duration asked line 64 to drop 3 words when 1 would do,
            # and every word dropped is payload at risk.
            # Absolute, not compounded - see the note above.
            ln["rate_bump"] = a.max_bump
            # A rate bump does not shorten audio in exact proportion - pauses
            # and breaths do not scale with speaking rate - so assume only 90%
            # of it lands. Under-trimming here just means the pre-flight asks
            # again; over-trimming throws away words for nothing.
            effective = 1.0 + (a.max_bump - 1.0) * 0.90
            bumped = f["narr_dur"] / effective
            budget = allowed_narr
            words_now = f["words"]
            keep_ratio = (budget / bumped) if bumped else 0.0
            target_words = max(4, int(words_now * min(1.0, keep_ratio)))
            prev = actions.get(lid, {}).get("strategy")
            actions[lid] = {
                "strategy": (f"{prev}+c-rate+e-trim" if prev
                             else "b-rate+e-trim"),
                "rate_bump": ln["rate_bump"],
                "note": (f"needs {need_mult:.3f}x rate; the {a.max_bump:.2f}x "
                         f"cap leaves {need_mult/effective:.3f}x for the text"),
                "target_words": target_words,
                "words_now": words_now,
                **({k: v for k, v in actions.get(lid, {}).items()
                    if k in ("from", "to", "new_start", "new_end")}),
            }
            trim_todo.append({
                "line_id": lid,
                "delivery": ln.get("delivery"),
                "beat": ln.get("note"),
                "clip_start": ln.get("clip_start"),
                "clip_end": ln.get("clip_end"),
                "window_sec": round(shot, 2),
                "audio_sec_now": f["narr_dur"],
                "audio_sec_budget": round(budget, 2),
                "rate_bump_applied": ln["rate_bump"],
                "words_now": words_now,
                "target_words": target_words,
                "narration": ln.get("narration"),
                "callback_beat": ln.get("callback_beat"),
                "instruction": (
                    f"Trim to <= {target_words} words. Keep the payload and "
                    f"every fact; drop adjectives, hedges and restatement "
                    f"first. Do not introduce a fact that is not already in "
                    f"this line. Do not name anything held by a later reveal."),
            })

    # ---- INVARIANT: no bump may leave the voice band ----------------------
    # Asserted rather than trusted. The compounding bug put 17 lines outside
    # the band and nothing noticed until a human read the draft, because every
    # individual decision looked correct - it was the ACCUMULATION that broke
    # the contract. An invariant catches an accumulation; a code review of the
    # decision does not.
    from pipeline import voice_check as _vc
    _band_bad = [(ln["id"], float(ln["rate_bump"]))
                 for ln in draft["lines"]
                 if ln.get("rate_bump") and not _vc.bump_in_band(ln["rate_bump"])]
    if _band_bad:
        raise AssertionError(
            f"fit_narration produced rate_bump(s) outside the "
            f"+-{config.VOICE_RATE_BAND:.0%} voice band: {_band_bad}. A bump is "
            f"absolute, never compounded onto a previous one.")

    # ---- report ----------------------------------------------------------- #
    console.print()
    console.print(f"[bold]Per-line resolution ({len(actions)} line(s)):[/]")
    for lid in sorted(actions):
        act = actions[lid]
        console.print(f"  line {lid:>3}  [{act['strategy']}]")
        if "from" in act:
            console.print(f"         window {act['from']} -> {act['to']}")
        if "rate_bump" in act:
            console.print(f"         rate_bump {act['rate_bump']:.3f}  "
                          f"({act.get('note','')})")
        if "hold" in act and "hold_key" in act:
            console.print(f"         hold {act['hold_was']:.2f}s -> "
                          f"{act['hold']:.2f}s  ({act.get('note','')})")
        if act["strategy"].endswith("e-trim"):
            console.print(f"         TEXT TRIM: {act['words_now']} -> "
                          f"<= {act['target_words']} words  "
                          f"({act.get('note','')})")

    n_a = sum(1 for v in actions.values() if "a-widen" in v["strategy"])
    n_x = sum(1 for v in actions.values() if "b-extend" in v["strategy"])
    n_m = sum(1 for v in actions.values() if "d-merge" in v["strategy"])
    n_b = sum(1 for v in actions.values() if "c-rate" in v["strategy"])
    n_c = sum(1 for v in actions.values() if "e-trim" in v["strategy"])
    n_h = sum(1 for v in actions.values() if "c-hold" in v["strategy"])
    console.print()
    console.print(f"[bold]Summary:[/] {n_a} widened (same shot), {n_x} extended "
                  f"(multi-shot), {n_b} rate-bumped, {n_h} hold(s) shortened, "
                  f"{n_m} to merge, {n_c} need a text trim")

    if not a.apply:
        console.print("\n[yellow]Dry run - nothing written. Re-run with "
                      "--apply.[/]")
        return 0

    # ---- write ------------------------------------------------------------ #
    bak = pdir / "draft_prefit.json"
    if not bak.exists():
        bak.write_text(json.dumps(
            json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig")),
            indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"[dim]Backed up the pre-fit draft to {bak.name}[/]")
    io.open(pdir / "draft.json", "w", encoding="utf-8").write(
        json.dumps(draft, indent=2, ensure_ascii=False))
    console.print(f"[green]Wrote draft.json[/] ({n_a} window(s) widened, "
                  f"{n_b} rate_bump(s) set)")

    if trim_todo:
        tp = pdir / "narration_fit_todo.json"
        io.open(tp, "w", encoding="utf-8").write(json.dumps(
            {"project": a.project, "lines": trim_todo}, indent=2,
            ensure_ascii=False))
        console.print(
            f"[yellow]{len(trim_todo)} line(s) still need a TEXT trim - "
            f"written to {tp.name}.[/]")
        console.print("[yellow]  These are a writing decision, not an "
                      "arithmetic one: only a reader of the beat can tell "
                      "which words carry the payload. Trim them, re-run the "
                      "render (it re-synthesizes just those lines), and the "
                      "pre-flight will confirm.[/]")
    if n_b:
        console.print("[yellow]Rate-bumped lines will re-synthesize on the "
                      "next render (the bump is part of the TTS cache key).[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
