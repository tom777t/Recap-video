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
MARGIN_MIN_SEC = 0.25
MARGIN_FRACTION = 0.03


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
def plan_widen(draft: dict, pdir: Path, project: str,
               durs: dict) -> tuple[dict, list]:
    """Re-allocate window boundaries inside each host shot.

    Returns ({line_id: (new_start, new_end)}, [notes]). Only lines that need a
    change are present. Everything here stays inside ONE host shot, so no real
    cut is crossed and the shot on screen for each line is unchanged.
    """
    from pipeline.draft import parse_ts
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
        bound.append({"id": ln["id"], "a": a, "b": b, "ln": ln})
    bound.sort(key=lambda r: r["a"])

    # group by host shot
    groups: dict = {}
    for r in bound:
        h = _host_of(shots, r["a"])
        key = (h[0], h[1]) if h else None
        groups.setdefault(key, []).append(r)

    new: dict = {}
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

        # A window that ALREADY runs past the host shot is grandfathered: it was
        # authored that way and the render accepts it. Clamping it back to the
        # shot boundary here would be this tool making a line WORSE - it did
        # exactly that to line 108, cutting 12.00s to 7.88s and turning a 1.46x
        # problem into a 2.24x one.
        limit = max(limit, max(m["b"] for m in members))
        for r in bound:
            if r["a"] >= members[-1]["b"] and not (hs - 0.6 <= r["a"] < he):
                limit = min(limit, r["a"])
                break
        for L in lands:
            if L > span_lo:
                limit = min(limit, L)
                break

        need = {m["id"]: required_window(durs.get(m["id"], 0.0))
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

    # Assert the invariant rather than trusting it: a bug here silently
    # degrades footage, which is the hardest kind of damage to notice later.
    for lid, (na, nb) in new.items():
        m = next(r for r in bound if r["id"] == lid)
        req = required_window(durs.get(lid, 0.0))
        allowed_floor = max(MIN_WINDOW_SEC, min(m["b"] - m["a"], req)) - 1e-3
        if (nb - na) < allowed_floor:
            raise AssertionError(
                f"fit_narration would shrink line {lid} from "
                f"{m['b']-m['a']:.2f}s to {nb-na:.2f}s, below its floor "
                f"{allowed_floor:.2f}s - refusing to make a line worse")
    return new, notes


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="write draft.json (default: report only)")
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
    if not narration:
        console.print("[red]No narration/*.mp3 - run the render once (or "
                      "`recap.py render`) so the real audio exists, then "
                      "re-run this.[/]")
        return 1

    findings = pf.capacity_findings(draft, narration)
    if not findings:
        console.print("[green]No capacity overruns - nothing to fit.[/]")
        return 0

    durs = {}
    ffp = config.ffprobe()
    for lid, p, _d in narration:
        durs[lid] = pf._audio_dur(ffp, p)

    console.print(f"[cyan]fit_narration:[/] {len(findings)} overrun(s) on "
                  f"{a.project}")

    by_id = {ln["id"]: ln for ln in draft["lines"]}
    actions: dict = {}

    # ---- (a) widen inside the host shot ---------------------------------- #
    widen, notes = plan_widen(draft, pdir, a.project, durs)
    for n in notes:
        console.print(f"[yellow]  note: {n}[/]")

    for lid, (na, nb) in sorted(widen.items()):
        ln = by_id.get(lid)
        if ln is None:
            continue
        old = (parse_ts(ln["clip_start"]), parse_ts(ln["clip_end"]))
        actions[lid] = {
            "strategy": "a-widen",
            "from": f"{old[0]:.2f}-{old[1]:.2f} ({old[1]-old[0]:.2f}s)",
            "to": f"{na:.2f}-{nb:.2f} ({nb-na:.2f}s)",
            "new_start": _hms(na), "new_end": _hms(nb),
        }

    # Apply the widening in memory so the next stage judges the NEW windows.
    for lid, act in actions.items():
        by_id[lid]["clip_start"] = act["new_start"]
        by_id[lid]["clip_end"] = act["new_end"]

    still = pf.capacity_findings(draft, narration)

    # ---- (b) bounded rate bump ------------------------------------------- #
    trim_todo = []
    for f in still:
        lid = f["line_id"]
        ln = by_id[lid]
        shot = f["shot_dur"]
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
                "strategy": (f"{prev}+b-rate" if prev else "b-rate"),
                "rate_bump": mult,
                "note": (f"needs {need_mult:.3f}x, applying {mult:.3f}x "
                         f"(cap {a.max_bump:.2f}x)"),
                **({k: v for k, v in actions.get(lid, {}).items()
                    if k in ("from", "to", "new_start", "new_end")}),
            }
            ln["rate_bump"] = mult if cur == 1.0 else round(cur * mult, 4)
        else:
            # (c) the text is the problem - but spend the rate budget FIRST so
            # the text loses as little as possible. Trimming against the
            # unbumped duration asked line 64 to drop 3 words when 1 would do,
            # and every word dropped is payload at risk.
            ln["rate_bump"] = (a.max_bump if cur == 1.0
                               else round(cur * a.max_bump, 4))
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
                "strategy": (f"{prev}+b-rate+c-trim" if prev
                             else "b-rate+c-trim"),
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
        if act["strategy"].endswith("c-trim"):
            console.print(f"         TEXT TRIM: {act['words_now']} -> "
                          f"<= {act['target_words']} words  "
                          f"({act.get('note','')})")

    n_a = sum(1 for v in actions.values() if v["strategy"].startswith("a-"))
    n_b = sum(1 for v in actions.values() if "b-rate" in v["strategy"])
    n_c = sum(1 for v in actions.values() if "c-trim" in v["strategy"])
    console.print()
    console.print(f"[bold]Summary:[/] {n_a} widened, {n_b} rate-bumped, "
                  f"{n_c} need a text trim")

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
