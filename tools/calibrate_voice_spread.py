"""Calibrate the voice-consistency ceilings on a CONTROL.

WHY
---
[VOICE-CONSISTENCY] blocked a render on a 1.95x line-to-line spread against a
1.25x ceiling. The 1.25 was never measured - it was picked because 1.77x
"sounded like three people" and 1.25 "sounded like one". That is a guess
wearing a number, and it blocked a render whose base rate was dead on target
(185.2 WPM) and whose tag means were all inside +-11%.

Every other bar in this project is calibrated against a control. This one was
not, so here is the control: take varied real draft lines, synthesize them with
ONE IDENTICAL DELIVERY, and measure what a single consistent narrator actually
does. Whatever spread Warren produces when nothing is varying except the words
IS the floor for any ceiling - a bar below it fails a narrator who is behaving
perfectly.

    python tools/calibrate_voice_spread.py --project NAME
    python tools/calibrate_voice_spread.py --project NAME --n 20 --write

Costs money (Inworld bills per character): ~20 lines is about 3,000 characters,
roughly $0.08. Audio goes to a scratch directory, never the project's
narration cache.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics as st
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from rich.console import Console  # noqa: E402

console = Console()

# The control delivery: ONE tag's mapping for every line, so the only thing
# varying is the words. `normal` is the right choice - it is the mapping the
# other tags are compensated against.
CONTROL_TAG = "normal"
# Margin on top of what the control produces. A ceiling set exactly at the
# observed maximum fails half the time on a narrator doing nothing wrong.
SPREAD_MARGIN = 1.15
JUMP_MARGIN = 1.25


def _varied_sample(project: str, n: int) -> list[dict]:
    """`n` real draft lines spread across the LENGTH range.

    Length is what drives natural rate variation (a 10-word line and a 50-word
    line articulate differently), so the control has to span it rather than
    sampling one bucket.
    """
    pdir = Path(config.project_dir(project))
    d = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    rows = []
    floor = int(getattr(config, "VOICE_RATE_MIN_WORDS", 6))
    for ln in d.get("lines") or []:
        if (ln.get("narration_silence_seconds") is not None
                or ln.get("film_speaks_seconds") is not None):
            continue
        txt = str(ln.get("narration") or "").strip()
        if len(txt.split()) < floor:
            continue
        rows.append({"id": ln["id"], "text": txt, "words": len(txt.split())})
    if not rows:
        return []
    rows.sort(key=lambda r: r["words"])
    # even stride across the length range
    step = max(1, len(rows) // n)
    out = [rows[i] for i in range(0, len(rows), step)][:n]
    return out


def run_control(project: str, n: int = 20) -> dict:
    from pipeline.tts_providers import all_providers, synthesize_cached
    from pipeline.tts import DEFAULT_PROVIDER
    from pipeline import voice_check as vc

    prov = all_providers()[DEFAULT_PROVIDER]
    ok, why = prov.available()
    if not ok:
        raise RuntimeError(f"cannot synthesize: {why}")
    rows = _varied_sample(project, n)
    if len(rows) < 6:
        raise RuntimeError("not enough usable draft lines for a control")

    scratch = Path(tempfile.mkdtemp(prefix="vspread_"))
    ff = config.ffmpeg()
    try:
        got = []
        for i, r in enumerate(rows, 1):
            out = scratch / f"c{i:02d}.mp3"
            try:
                # ONE identical delivery for every line
                synthesize_cached(prov, r["text"], CONTROL_TAG, out, scratch)
            except Exception as e:
                console.print(f"[yellow]  line {r['id']}: {e}[/]")
                continue
            dur, speech, sil = vc.speech_seconds(out, ff)
            if speech <= 0.05:
                continue
            syl = sum(vc._syllables(w) for w in r["text"].split())
            got.append({"id": r["id"], "words": r["words"],
                        "dur": dur, "speech": speech, "silence": sil,
                        "wps": r["words"] / speech,
                        "sps": syl / speech,
                        "wps_raw": r["words"] / dur})
            console.print(f"[dim]  {i}/{len(rows)} line {r['id']:>3} "
                          f"{r['words']:>2}w  {60*got[-1]['wps']:.0f} WPM "
                          f"articulated ({60*got[-1]['wps_raw']:.0f} raw)[/]")
        if len(got) < 6:
            raise RuntimeError("too few control lines synthesized")

        wps = [g["wps"] for g in got]
        sps = [g["sps"] for g in got]
        raw = [g["wps_raw"] for g in got]
        # adjacent pairs, in the order the lines appear in the draft
        got_in_order = sorted(got, key=lambda g: g["id"])
        jumps = [abs(b["wps"] / a["wps"] - 1.0)
                 for a, b in zip(got_in_order, got_in_order[1:])]
        # rolling 3-line average, which is how the gate will judge
        roll = []
        for i in range(len(got_in_order) - 2):
            roll.append(st.mean(g["wps"] for g in got_in_order[i:i + 3]))
        from pipeline import voice_check as _vc
        return {
            "n": len(got),
            "roll3_spread_pct": _vc._pct_spread(roll),
            "line_spread_pct": _vc._pct_spread(wps),
            "mean_wpm": 60 * st.mean(wps),
            "spread_artic": max(wps) / min(wps),
            "spread_raw": max(raw) / min(raw),
            "spread_sps": max(sps) / min(sps),
            "jump_max": max(jumps) if jumps else 0.0,
            "jump_p90": (sorted(jumps)[int(len(jumps) * 0.9)]
                         if jumps else 0.0),
            "jump_median": st.median(jumps) if jumps else 0.0,
            "roll3_spread": (max(roll) / min(roll)) if roll else 1.0,
            "rows": got,
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--write", action="store_true",
                    help="write the calibrated ceilings into config.py")
    a = ap.parse_args()

    console.print(f"[cyan]Control:[/] {a.n} varied draft lines, all with the "
                  f"'{CONTROL_TAG}' delivery - the only thing varying is the "
                  f"words.")
    res = run_control(a.project, a.n)

    console.print()
    console.print(f"[bold]A single consistent narrator, {res['n']} lines, "
                  f"mean {res['mean_wpm']:.0f} WPM:[/]")
    console.print(f"  line-to-line spread   "
                  f"[bold]{res['spread_artic']:.2f}x[/] articulated   "
                  f"({res['spread_raw']:.2f}x on raw WPM, "
                  f"{res['spread_sps']:.2f}x on syllables)")
    console.print(f"  rolling 3-line spread [bold]{res['roll3_spread_pct']:.2f}x[/] "
                  f"(p95/p5; {res['roll3_spread']:.2f}x on max/min)")
    console.print(f"  adjacent jump         median {res['jump_median']:.0%}, "
                  f"p90 {res['jump_p90']:.0%}, max "
                  f"[bold]{res['jump_max']:.0%}[/]")

    spread_ceil = round(res["line_spread_pct"] * SPREAD_MARGIN, 2)
    roll_ceil = round(res["roll3_spread_pct"] * SPREAD_MARGIN, 2)
    jump_ceil = round(max(res["jump_p90"], 0.05) * JUMP_MARGIN, 2)
    console.print()
    console.print("[bold]Proposed ceilings (control + margin):[/]")
    console.print(f"  VOICE_LINE_SPREAD_MAX  = {spread_ceil}   "
                  f"(control p95/p5 {res['line_spread_pct']:.2f}x x {SPREAD_MARGIN})")
    console.print(f"  VOICE_ROLL3_SPREAD_MAX = {roll_ceil}   "
                  f"(control p95/p5 {res['roll3_spread_pct']:.2f}x x {SPREAD_MARGIN})")
    console.print(f"  VOICE_ADJACENT_MAX_JUMP= {jump_ceil}   "
                  f"(control p90 {res['jump_p90']:.0%} x {JUMP_MARGIN})")
    console.print("[dim]  A bar below the control fails a narrator doing "
                  "nothing wrong. These are floors, not preferences.[/]")

    if a.write:
        import re
        p = Path(ROOT) / "config.py"
        s = p.read_text(encoding="utf-8")
        subs = {
            "VOICE_LINE_SPREAD_MAX": spread_ceil,
            "VOICE_ROLL3_SPREAD_MAX": roll_ceil,
            "VOICE_ADJACENT_MAX_JUMP": jump_ceil,
        }
        for k, v in subs.items():
            # "no textual change" is NOT "not found" - it is also what happens
            # when the value is already correct, which this reported as a
            # failure after writing the first two constants.
            if not re.search(rf"^{k} = [\d.]+", s, flags=re.M):
                console.print(f"[red]Could not find {k} in config.py[/]")
                return 1
            s = re.sub(rf"^{k} = [\d.]+", f"{k} = {v}", s,
                       count=1, flags=re.M)
        p.write_text(s, encoding="utf-8")
        console.print("[green]Wrote the calibrated ceilings to config.py[/]")
        out = Path(ROOT) / "config" / "voice_spread_control.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(
            {k: v for k, v in res.items() if k != "rows"}, indent=2),
            encoding="utf-8")
        console.print(f"[dim]Control measurements kept in {out.name} so the "
                      f"ceilings can be traced to evidence.[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
