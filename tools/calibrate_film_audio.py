"""Calibrate [FILM-AUDIO] on REAL material from this project.

WHY
---
The present/absent bars (0.040 / 0.025) were sited on a SYNTHETIC control:
pink noise as the "stem", a 330 Hz tone as the "music". That gave

    stem present at -17 dB -> corr 0.270
    stem absent            -> corr 0.006

a 45x separation, and it was not representative of anything. On the real
render the same check measured

    action/tense windows (stem ON)  mean 0.048
    everywhere else     (stem OFF)  mean 0.029

a 1.65x separation with the two populations overlapping: five "off" lines sat
at 0.026-0.040 and five "on" windows sat below the 0.040 present bar. A bar
cannot be sited in the middle of that.

A tone is trivially separable from noise; real film audio sits under real
narration and real music, all of it broadband. So the control has to be built
from THIS project's own narration, bed and stem, at the real -17 dB.

This tool builds that control and reports the separation. It does not move any
bar by itself: if the separation is weak, the honest answer is that the METHOD
needs to improve, not that the bar needs to move.

Run:  python tools/calibrate_film_audio.py [--project NAME] [--window 8]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from pipeline import audio_check as ac  # noqa: E402


def _ff(*a) -> int:
    r = subprocess.run([config.ffmpeg(), "-y", "-hide_banner", "-loglevel",
                        "error", *a], capture_output=True, text=True)
    return r.returncode


def build_control(pdir: Path, stem: Path, narr: Path, bed: Path,
                  src_at: float, dur: float, out_dir: Path,
                  film_db: float) -> tuple:
    """(with_stem, without_stem) - the same span mixed both ways.

    Mirrors what _build_clip really does: the narration at full level, the
    film's track at config.FILM_AUDIO_DB under it, and the music bed under
    both. The ONLY difference between the two files is whether the stem is in
    the mix.
    """
    a = out_dir / "ctl_with.wav"
    b = out_dir / "ctl_without.wav"
    duck = float(getattr(config, "MUSIC_DUCK_DB", -22.0))
    common = ["-ss", f"{src_at:.3f}", "-t", f"{dur:.3f}", "-i", str(stem),
              "-i", str(narr)]
    bedin = ["-stream_loop", "-1", "-t", f"{dur:.3f}", "-i", str(bed)]
    # with the stem
    rc1 = _ff(*common, *bedin, "-filter_complex",
              f"[0:a]volume={film_db:.1f}dB,aformat=sample_rates=48000:"
              f"channel_layouts=stereo[f];"
              f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,"
              f"apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}[v];"
              f"[2:a]volume={duck:.1f}dB,aformat=sample_rates=48000:"
              f"channel_layouts=stereo[m];"
              f"[v][f][m]amix=inputs=3:duration=first:normalize=0[a]",
              "-map", "[a]", "-t", f"{dur:.3f}", str(a))
    # without the stem - everything else identical
    rc2 = _ff("-i", str(narr), *bedin, "-filter_complex",
              f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,"
              f"apad=whole_dur={dur:.3f},atrim=0:{dur:.3f}[v];"
              f"[1:a]volume={duck:.1f}dB,aformat=sample_rates=48000:"
              f"channel_layouts=stereo[m];"
              f"[v][m]amix=inputs=2:duration=first:normalize=0[a]",
              "-map", "[a]", "-t", f"{dur:.3f}", str(a.parent / b.name))
    return (a if rc1 == 0 else None, b if rc2 == 0 else None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="tokyodrift2006")
    ap.add_argument("--window", type=float, default=8.0,
                    help="correlation window in seconds")
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--write", action="store_true",
                    help="write config/film_audio_control.json")
    a = ap.parse_args()

    pdir = Path(config.project_dir(a.project))
    stem = pdir / "stems" / "no_vocals.wav"
    bed = pdir / "music" / "bed.mp3"
    draft = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    if not stem.exists():
        print(f"no stem at {stem}")
        return 1
    if not bed.exists():
        print(f"no bed at {bed}")
        return 1

    from pipeline.draft import parse_ts
    import tempfile
    out_dir = Path(tempfile.mkdtemp(prefix="fa_ctl_"))
    film_db = float(config.FILM_AUDIO_DB)

    rows = []
    done = 0
    for ln in draft["lines"]:
        if done >= a.samples:
            break
        if not ln.get("clip_start") or not str(ln.get("narration") or "").strip():
            continue
        nmp3 = pdir / f"narration/line_{ln['id']:03d}.mp3"
        if not nmp3.exists():
            continue
        src_at = parse_ts(ln["clip_start"])
        w, wo = build_control(pdir, stem, nmp3, bed, src_at, a.window,
                              out_dir, film_db)
        if w is None or wo is None:
            continue
        s = ac._pcm(stem, src_at, a.window)
        c_on = ac.correlation(ac._pcm(w, 0.0, a.window), s)
        c_off = ac.correlation(ac._pcm(wo, 0.0, a.window), s)
        rows.append({"line": ln["id"], "src_at": round(src_at, 2),
                     "with_stem": round(c_on, 4),
                     "without_stem": round(c_off, 4)})
        print(f"  line {ln['id']:>3} src {src_at:8.2f}s   "
              f"with stem {c_on:.4f}   without {c_off:.4f}   "
              f"ratio {c_on / max(c_off, 1e-6):5.1f}x")
        done += 1

    import shutil
    shutil.rmtree(out_dir, ignore_errors=True)
    if not rows:
        print("no control windows could be built")
        return 1

    on = [r["with_stem"] for r in rows]
    off = [r["without_stem"] for r in rows]
    on.sort()
    off.sort()
    print()
    print(f"CONTROL on {len(rows)} real window(s), {a.window:.0f}s each, "
          f"stem at {film_db:.0f} dB")
    print(f"  with stem   : min {min(on):.4f}  median {on[len(on)//2]:.4f}  "
          f"max {max(on):.4f}")
    print(f"  without stem: min {min(off):.4f}  median "
          f"{off[len(off)//2]:.4f}  max {max(off):.4f}")
    sep = min(on) / max(max(off), 1e-6)
    print(f"  worst-case separation: {sep:.2f}x "
          f"(lowest present / highest absent)")
    if sep <= 1.5:
        print("  => the populations OVERLAP. Moving the bars cannot fix this; "
              "the measurement method has to improve.")
    else:
        lo, hi = max(off), min(on)
        present = round(lo + (hi - lo) * 0.5, 3)
        absent = round(lo + (hi - lo) * 0.25, 3)
        print(f"  => a present bar of {present} and an absent bar of {absent} "
              f"sit inside the gap {lo:.4f}..{hi:.4f}")
    if a.write:
        rec = {"project": a.project, "window_sec": a.window,
               "film_audio_db": film_db, "rows": rows,
               "with_stem": {"min": min(on), "median": on[len(on) // 2],
                             "max": max(on)},
               "without_stem": {"min": min(off), "median": off[len(off) // 2],
                                "max": max(off)},
               "worst_separation": round(sep, 3)}
        p = Path(ROOT) / "config" / "film_audio_control.json"
        p.write_text(json.dumps(rec, indent=1), encoding="utf-8")
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
