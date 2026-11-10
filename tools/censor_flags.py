# -*- coding: utf-8 -*-
"""censor_flags.py - look at the blur flags render refuses, and decide them.

    python tools/censor_flags.py --project P                 # list + frames
    python tools/censor_flags.py --project P --clear 01:11:10.076 00:06:24.466 --note "party dresses, no gore"

render stops on [CENSOR-POLICY] when a shot in shots.json is flagged for blur
(`censor`: blur_light / blur / blur_heavy) with no `censor_region`: a
full-frame blur loses the shot. The flags come from the machine tagger, and
it over-flags - Tokyo Drift's 14 kept 4 after a look at the frames (towels,
cocktail dresses, a kiss and dust taken for blood were dropped). The policy
(config.CENSOR_CRITERIA) blurs only blood/gore and nudity.

Listing prints each flagged shot with what the tagger wrote about it and
saves one frame from its middle to projects/<p>/censor_check/<time>.jpg, so
the decision is made by looking, not by reading the tag.

--clear sets those shots to `censor: none` and records why
(`censor_cleared`: the note), in shots.json only. A shot that really shows
gore or nudity is NOT cleared: give it a `censor_region` box (source-frame
pixels) or bind its line to another shot.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402


def _source(pdir: Path):
    for name in ("source.mp4", "source.mkv", "source.mov"):
        if (pdir / name).exists():
            return pdir / name
    return None


def frame(pdir: Path, at: float, out: Path) -> bool:
    src = _source(pdir)
    if src is None:
        return False
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{at:.3f}", "-i",
             str(src), "-frames:v", "1", "-q:v", "3", str(out)],
            capture_output=True, timeout=60)
        return r.returncode == 0 and out.exists()
    except (OSError, subprocess.TimeoutExpired):
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--clear", nargs="+", metavar="CLIP_START",
                    help="clip_start of each flagged shot to set to none")
    ap.add_argument("--note", default="",
                    help="why (required with --clear)")
    ap.add_argument("--no-frames", action="store_true")
    a = ap.parse_args(argv)
    from pipeline import censor
    pdir = Path(config.project_dir(a.project))
    sp = pdir / "shots.json"
    shots = json.loads(sp.read_text(encoding="utf-8-sig"))
    flagged = [s for s in shots.get("shots", [])
               if str(s.get("censor") or "none") != "none"]

    if a.clear:
        if not a.note.strip():
            ap.error("--clear needs --note: say what the frames show")
        want = set(a.clear)
        hit = [s for s in flagged if s.get("clip_start") in want]
        missing = want - {s.get("clip_start") for s in hit}
        if missing:
            print(f"censor_flags: not a flagged shot: {sorted(missing)} - "
                  f"nothing changed")
            return 1
        for s in hit:
            s["censor_cleared"] = f"{s.get('censor')} -> none: {a.note.strip()}"
            s["censor"] = "none"
            s.pop("censor_region", None)
        sp.write_text(json.dumps(shots, ensure_ascii=False, indent=2),
                      encoding="utf-8")
        left = censor.criteria_problems(pdir)
        print(f"censor_flags: {len(hit)} shot(s) cleared in shots.json; "
              f"{len(left)} flag(s) still break the policy")
        return 0 if not left else 2

    out = pdir / "censor_check"
    if not a.no_frames:
        out.mkdir(exist_ok=True)
    bad = {p.split(" ")[0] for p in censor.criteria_problems(pdir)}
    print(f"censor_flags: {len(flagged)} flagged shot(s); policy: blur only "
          f"{', '.join(getattr(config, 'CENSOR_CRITERIA', ()))}")
    for s in flagged:
        cs, ce = s.get("clip_start"), s.get("clip_end")
        mid = (censor._pt(cs) + censor._pt(ce)) / 2.0
        img = out / (cs.replace(":", "-") + ".jpg")
        got = (not a.no_frames) and frame(pdir, mid, img)
        print(f"\n  {cs}..{ce}  {s.get('censor')}"
              + ("  NO REGION - render refuses this" if cs in bad else
                 f"  region {s.get('censor_region')}"))
        print(f"    tagger: {str(s.get('action') or '')[:220]}")
        if s.get("depicts"):
            print(f"    depicts: {s.get('depicts')}")
        if got:
            print(f"    frame: {img}")
    print("\nLook at each frame. Not blood/gore or nudity -> clear it:\n"
          f"  python tools/censor_flags.py --project {a.project} --clear "
          f"<clip_start> ... --note \"what the frames show\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
