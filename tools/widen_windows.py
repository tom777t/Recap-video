# -*- coding: utf-8 -*-
"""widen_windows.py - give each line's picture the stretch of film it summarises.

    python tools/widen_windows.py --project tokyodrift2006           # report
    python tools/widen_windows.py --project tokyodrift2006 --apply   # write

WHY. The viewer compared two Tokyo Drift renders. The one judged "no mismatch,
engaging" (30 Oct, pre-rewrite draft) gave each line a window ~1.7x its
narration that reached past its first catalogued shot on 56 of 102 lines (27%
of picture time). The rewrite bound each line inside ONE catalogued shot
(window ~1.37x, 2% beyond the host shot) so its claims could be verified
against that shot's tags - and the viewer saw the picture stop following the
story: a line that summarises a scene showed one camera stretch of it.

The builder already splits a long window across its cuts and gives every
sub-shot an equal share of the line's screen time, so a window that covers
the scene IS the "picture follows the sentence" edit, with no new render
code. This tool widens windows back towards the calibrated ratio:

  * clip_start never moves (it anchors the narrated moment);
  * only clip_end grows, never shrinks;
  * never into the next bound line's window (no footage reuse);
  * never past a reveal's landing time (no early reveal footage);
  * never into a censor-flagged shot;
  * with a cut list, never into a split the builder could not fill
    ([SHORT-CLIP], footprint.short_clips) - the extension backs off instead.

The target ratio is config.WINDOW_SPAN_RATIO, calibrated on the approved
render. Holds and film_speaks units are left alone.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from pipeline.draft import parse_ts  # noqa: E402


def _hms(sec: float) -> str:
    h, r = divmod(max(0.0, sec), 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def _narr_secs(ln: dict, measured: dict) -> float:
    lid = ln.get("id")
    if measured.get(lid):
        return float(measured[lid])
    wpm = float(getattr(config, "TARGET_WPM", 210))
    return len(str(ln.get("narration") or "").split()) / wpm * 60.0


def _measured(pdir: Path) -> dict:
    """Real narration durations when the mp3s exist (the user's machine)."""
    from pipeline import preflight as pf
    out = {}
    ffp = config.ffprobe()
    for p in sorted((pdir / "narration").glob("line_*.mp3")):
        try:
            out[int(p.stem.split("_")[1])] = pf._audio_dur(ffp, p) or 0.0
        except (ValueError, IndexError):
            continue
    return out


def plan(project: str, ratio: float | None = None) -> tuple[dict, list, str]:
    pdir = Path(config.project_dir(project))
    draft = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    ratio = float(ratio or getattr(config, "WINDOW_SPAN_RATIO", 1.7))
    measured = _measured(pdir)

    lands = []
    try:
        for r in json.loads((pdir / "reveals.json").read_text(
                encoding="utf-8-sig")).get("reveals") or []:
            try:
                lands.append(parse_ts(str(r.get("land") or r.get("land_ref"))))
            except Exception:
                continue
    except FileNotFoundError:
        pass
    from pipeline import censor
    flagged = [(float(f["a"]), float(f["b"])) for f in censor.flagged_shots(pdir)]
    try:
        from pipeline import cuts as _cuts
        cutlist = sorted(float(c) for c in (_cuts.load_cuts(project) or []))
    except Exception:
        cutlist = []
    from pipeline import footprint

    bound = sorted([ln for ln in draft["lines"]
                    if ln.get("clip_start") and ln.get("clip_end")],
                   key=lambda ln: parse_ts(ln["clip_start"]))
    starts = [parse_ts(ln["clip_start"]) for ln in bound]
    changes = []
    for i, ln in enumerate(bound):
        if not str(ln.get("narration") or "").strip():
            continue                                  # hold / film_speaks
        if ln.get("narration_silence_seconds") or ln.get("film_speaks_seconds"):
            continue
        a, b = starts[i], parse_ts(ln["clip_end"])
        n = _narr_secs(ln, measured)
        want = a + ratio * n
        if want <= b + 0.05:
            continue
        lim = starts[i + 1] - 0.05 if i + 1 < len(bound) else want
        lim = min([lim] + [L for L in lands if a < L])
        lim = min([lim] + [fa for fa, fb in flagged if fa >= b and fa < want])
        nb = min(want, lim)
        if nb <= b + 0.25:
            continue
        # back off while the builder could not fill the split it would make
        why = "ratio"
        if cutlist:
            while nb > b + 0.25:
                probe = dict(ln, clip_end=_hms(nb))
                if not footprint.short_clips({"lines": [probe]},
                                             {ln["id"]: n}, cutlist):
                    break
                nb -= 0.5
                why = "backed off for SHORT-CLIP"
            if nb <= b + 0.25:
                continue
        if nb < want - 0.3 and why == "ratio":
            why = "capped by neighbour / reveal / censor"
        changes.append({"id": ln["id"], "old_end": ln["clip_end"],
                        "new_end": _hms(nb), "old_ratio": (b - a) / n,
                        "new_ratio": (nb - a) / n, "why": why})
        ln["clip_end"] = _hms(nb)
    basis = (f"{len(measured)} measured narration file(s)" if measured
             else "word-count estimate (no narration mp3s here)")
    basis += "; SHORT-CLIP checked against the cut list" if cutlist else \
        "; NO cut list here, so SHORT-CLIP was not checked - the render will"
    return draft, changes, basis


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--ratio", type=float, default=None)
    a = ap.parse_args()

    draft, changes, basis = plan(a.project, a.ratio)
    print(f"widen_windows: {len(changes)} line(s) widened ({basis})")
    for c in changes:
        print(f"  line {c['id']:>3}: {c['old_ratio']:.2f}x -> "
              f"{c['new_ratio']:.2f}x  ({c['old_end']} -> {c['new_end']}; "
              f"{c['why']})")
    if not a.apply:
        print("Dry run - nothing written. Re-run with --apply.")
        return 0
    pdir = Path(config.project_dir(a.project))
    bak = pdir / "draft_prewiden.json"
    if not bak.exists():
        bak.write_text((pdir / "draft.json").read_text(encoding="utf-8-sig"),
                       encoding="utf-8")
        print(f"Backed up the draft to {bak.name}")
    io.open(pdir / "draft.json", "w", encoding="utf-8").write(
        json.dumps(draft, indent=2, ensure_ascii=False))
    print("Wrote draft.json. Next: .\\run.ps1 -Project "
          f"{a.project} -From voice")
    return 0


if __name__ == "__main__":
    sys.exit(main())
