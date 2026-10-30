"""
Time a render, so "faster" is a measurement rather than a feeling.

    python tools/bench_render.py --project tokyodrift2006 --label baseline-first
    python tools/bench_render.py --project tokyodrift2006 --label baseline-rerender

WHY THIS EXISTS AND WHY IT DOES NOT CALL validate_draft
`recap.py render` runs `validate_draft`, which exits non-zero when any craft
gate fails. That is correct for publishing and useless for benchmarking: the
pre-rewrite Tokyo Drift draft fails PACING-CONTOUR, PERSONA and
FACT-CONSISTENCY on purpose - it is the draft being replaced - and a render
timing has nothing to do with whether the prose is good.

So this harness loads draft.json directly. That is safe and not a smuggled
bypass, for a reason worth stating: `render()` reads exactly ONE key off the
draft dict, `draft["lines"]`, plus a `_dir` that validate_draft only
setdefault()s. Verified by grepping every `draft[...]`/`draft.get(...)` in
render.py. No gate is relaxed, no shipped path changes, and
`recap.py render` still refuses a bad draft exactly as before.

Everything else - TTS, music discovery, caption resolution, the render call
itself - mirrors recap.py:263-306 argument for argument, so the thing being
timed is the real render and not a simplified stand-in.

Results append to docs/stage2/render_timings.json so the before/after table is
assembled from recorded measurements rather than from memory.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

TIMINGS = Path("docs/stage2/render_timings.json")


def _ffprobe_dur(p: Path) -> float | None:
    if not p.exists():
        return None
    r = subprocess.run(
        [config.ffprobe(), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(p)],
        capture_output=True, text=True)
    try:
        return round(float(r.stdout.strip()), 2)
    except ValueError:
        return None


def _dir_stats(d: Path) -> dict:
    if not d.exists():
        return {"files": 0, "mb": 0.0}
    fs = [f for f in d.rglob("*") if f.is_file()]
    return {"files": len(fs),
            "mb": round(sum(f.stat().st_size for f in fs) / 1048576.0, 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--label", required=True,
                    help="name for this measurement, e.g. baseline-first")
    ap.add_argument("--force-clips", action="store_true")
    ap.add_argument("--captions", action="store_true")
    ap.add_argument("--keep-temp", action="store_true")
    ap.add_argument("--draft-mode", action="store_true",
                    help="540p draft render (Phase 1 addition)")
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    pdir = config.project_dir(a.project)
    draft_path = pdir / "draft.json"
    if not draft_path.exists():
        print(f"no draft.json in {pdir}")
        return 1
    draft = json.loads(draft_path.read_text(encoding="utf-8-sig"))
    draft.setdefault("_dir", str(pdir))

    n_lines = len(draft["lines"])
    print(f"=== bench: {a.label} ===")
    print(f"draft: {n_lines} lines")

    # Snapshot the cache state BEFORE, because "first render" vs "re-render"
    # is defined by it and a mislabelled warm cache is the easiest way to
    # publish a fake speedup.
    cache_before = _dir_stats(pdir / "_clipcache")
    print(f"clip cache before: {cache_before['files']} files "
          f"({cache_before['mb']} MB)")

    if a.draft_mode:
        os.environ["RECAP_DRAFT_MODE"] = "1"

    from pipeline.tts import generate_tts
    t_tts0 = time.perf_counter()
    narration = generate_tts(a.project, draft, allow_edge=True)
    t_tts = time.perf_counter() - t_tts0
    print(f"TTS stage: {t_tts:.1f}s ({len(narration)} lines)")

    music = None
    for name in ("music.mp3", "music.m4a", "music.wav", "music.ogg"):
        if (pdir / name).exists():
            music = pdir / name
            break

    use_caps = True if a.captions else config.DEFAULT_CAPTIONS

    from pipeline.render import render
    t0 = time.perf_counter()
    rc = 0
    try:
        render(a.project, draft, narration, music=music, captions=use_caps,
               keep_temp=a.keep_temp, force_clips=a.force_clips)
    except SystemExit as e:
        rc = int(e.code or 0)
    except Exception as e:  # noqa: BLE001
        print(f"RENDER RAISED: {type(e).__name__}: {e}")
        rc = 99
    t_render = time.perf_counter() - t0

    final = pdir / "final.mp4"
    rec = {
        "label": a.label,
        "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project": a.project,
        "draft_lines": n_lines,
        "exit": rc,
        "tts_seconds": round(t_tts, 1),
        "render_seconds": round(t_render, 1),
        "render_minutes": round(t_render / 60.0, 2),
        "total_minutes": round((t_tts + t_render) / 60.0, 2),
        "final_mb": (round(final.stat().st_size / 1048576.0, 1)
                     if final.exists() else None),
        "final_duration_s": _ffprobe_dur(final),
        "clipcache_before": cache_before,
        "clipcache_after": _dir_stats(pdir / "_clipcache"),
        "draft_mode": bool(a.draft_mode),
        "force_clips": bool(a.force_clips),
        "encoder": os.environ.get("RECAP_ENCODER_USED", ""),
        "cpu": platform.processor(),
        "note": a.note,
    }

    print(f"\nrender: {t_render:.1f}s = {t_render/60:.2f} min   (exit {rc})")
    print(f"final : {rec['final_mb']} MB, {rec['final_duration_s']}s")
    print(f"clip cache after: {rec['clipcache_after']['files']} files")

    TIMINGS.parent.mkdir(parents=True, exist_ok=True)
    try:
        hist = json.loads(TIMINGS.read_text(encoding="utf-8"))
    except Exception:
        hist = []
    hist.append(rec)
    TIMINGS.write_text(json.dumps(hist, indent=2), encoding="utf-8")
    print(f"appended to {TIMINGS}")
    return rc


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
