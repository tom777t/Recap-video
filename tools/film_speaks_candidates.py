"""Generate <film_speaks> candidates for a film, with every measurable fact.

This is the INPUT to the selection stage. It does not choose anything: it finds
every line in the transcript that is eligible under the rules in
prompts/recap_style.md, measures what can be measured, and writes the list for
a fresh-context subagent to score and select from
(prompts/film_speaks_select.md).

    python tools/film_speaks_candidates.py --project NAME
    python tools/film_speaks_candidates.py --project NAME --no-audio   # fast
    python tools/film_speaks_candidates.py --project NAME --top 25

Writes projects/<name>/film_speaks_candidates.json.

AUDIO MEASUREMENT IS THE SLOW PART. Each candidate's span is separated with
Demucs to measure how far the dialogue stands above the music and effects.
Spans are cached, and a selected quote's span is then already separated by the
time the render needs it. --no-audio skips it and marks every candidate
unmeasured, which the AUDIO-CLEAN gate treats as a failure rather than a pass:
a quote cannot be called clean because nobody checked.
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--no-audio", action="store_true",
                    help="skip the Demucs cleanliness measurement (fast, but "
                         "every candidate is then marked unmeasured)")
    ap.add_argument("--top", type=int, default=40,
                    help="keep only the N best-qualified candidates")
    a = ap.parse_args()

    from pipeline import film_speaks as fs

    pdir = Path(config.project_dir(a.project))
    for need in ("transcript.json",):
        if not (pdir / need).exists():
            console.print(f"[red]Missing {need}[/] - candidates come from the "
                          f"transcript, the beat map, the reveal map and "
                          f"angle.md.")
            return 1

    missing = [n for n in ("reveals.json", "angle.md", "beats_proposal.md")
               if not (pdir / n).exists()]
    if missing:
        console.print(f"[yellow]Note:[/] {missing} absent - the corresponding "
                      f"eligibility criteria cannot fire, so the candidate "
                      f"list will be narrower than it should be.")

    console.print(f"[cyan]film_speaks candidates:[/] scanning "
                  f"{a.project}...")
    cands = fs.candidates(a.project, measure_audio=False, limit=a.top)
    if not cands:
        console.print(
            "[yellow]No eligible candidate.[/] Nothing in the transcript is a "
            "reveal in a character's own words, states the angle's thesis, or "
            "sits in the climax. A zero count is legitimate for this film and "
            "[FILM-SPEAKS-COUNT] will accept it.")
        io.open(pdir / "film_speaks_candidates.json", "w",
                encoding="utf-8").write(json.dumps(
                    {"project": a.project, "candidates": [],
                     "note": "no eligible candidate"}, indent=2,
                    ensure_ascii=False))
        return 0

    cands = fs.annotate_paraphrase(a.project, cands)

    if not a.no_audio:
        console.print(f"[cyan]Measuring dialogue cleanliness[/] on "
                      f"{len(cands)} span(s) with Demucs (cached; the slow "
                      f"part, about {sum(c['seconds'] for c in cands)*1.6/60:.0f} "
                      f"min for this many)...")
        for i, c in enumerate(cands, 1):
            c["audio"] = fs.audio_cleanliness(a.project, c["start"], c["end"])
            m = c["audio"].get("margin_db")
            console.print(f"[dim]  {i}/{len(cands)} {c['start']:.0f}s "
                          f"margin {m if m is not None else '?'} dB[/]")
    else:
        for c in cands:
            c["audio"] = {"measured": False,
                          "note": "--no-audio: not measured"}

    doc = {
        "project": a.project,
        "rules": {
            "count": [int(getattr(config, "FILM_SPEAKS_MIN_PER_FILM", 2)),
                      int(getattr(config, "FILM_SPEAKS_MAX_PER_FILM", 3))],
            "seconds": [float(config.FILM_SPEAKS_MIN_SEC),
                        float(config.FILM_SPEAKS_MAX_SEC)],
            "min_gap_sec": float(getattr(config, "FILM_SPEAKS_MIN_GAP_SEC",
                                         180.0)),
            "max_per_act": int(getattr(config, "FILM_SPEAKS_MAX_PER_ACT", 1)),
            "audio_clean_min_db": fs.AUDIO_CLEAN_MIN_DB,
            "paraphrase_max_overlap": fs.PARAPHRASE_MAX_OVERLAP,
            "must_serve": list(getattr(config, "FILM_SPEAKS_MUST_SERVE", ())),
        },
        "acts": [round(x, 1) for x in fs.acts(a.project)],
        "candidates": cands,
    }
    out = pdir / "film_speaks_candidates.json"
    io.open(out, "w", encoding="utf-8").write(
        json.dumps(doc, indent=2, ensure_ascii=False))

    console.print(f"[green]Wrote {out.name}[/] - {len(cands)} candidate(s)")
    by_crit: dict = {}
    for c in cands:
        for k in c["criteria"]:
            by_crit[k] = by_crit.get(k, 0) + 1
    console.print("  " + ", ".join(f"{k}: {v}" for k, v in
                                   sorted(by_crit.items())))
    clean = [c for c in cands
             if (c["audio"].get("margin_db") or -99) >= fs.AUDIO_CLEAN_MIN_DB]
    console.print(f"  {len(clean)} of {len(cands)} have measurably clean "
                  f"dialogue (>= {fs.AUDIO_CLEAN_MIN_DB:.0f} dB over the mix)")
    console.print(f"[yellow]Next:[/] a fresh-context subagent reads "
                  f"prompts/film_speaks_select.md and selects "
                  f"{doc['rules']['count'][0]}-{doc['rules']['count'][1]}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
