"""
Find the h264_qsv `global_quality` that matches libx264 CRF 20, by measuring.

    python tools/calibrate_encoder.py --project tokyodrift2006

METHOD
Take a 60s sample of the REAL film (not colour bars - synthetic content
compresses nothing like photographed motion, and the 4.75x speedup measured
on testsrc2 is not a quality claim). Encode it with libx264 CRF 20 to get the
reference score. Encode it with h264_qsv at a sweep of global_quality values.
Score every encode with VMAF **against the untouched sample**, which is the
only valid reference - scoring QSV against the x264 output would measure
agreement with x264's mistakes.

Then pick the lowest-cost global_quality whose VMAF is at least the CRF 20
score minus a small tolerance. "Lowest cost" because beyond parity we are
paying encode time for quality nobody asked for.

The sample is taken from the middle of the film and run through the SAME
filter chain the render uses (lanczos scale + letterbox pad + fps), so the
thing being measured is what actually gets encoded.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from pipeline import encoder as enc  # noqa: E402

OUT = Path("docs/stage2/encoder_calibration.json")
TOLERANCE = 0.5     # VMAF points we are willing to give up for speed
SWEEP = (18, 20, 22, 23, 24, 25, 26, 28)


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _vmaf(ff: str, ref: Path, dist: Path) -> float | None:
    """VMAF of `dist` against `ref`. Returns the pooled mean.

    `log_path` is a BARE FILENAME and ffmpeg is run with cwd set to the work
    directory. A full Windows path cannot be passed here: it contains both a
    drive colon and - in this repo - a space, and inside a filtergraph the
    colon is the option separator. Escaping it defeated three attempts;
    sidestepping it with a relative name is exact and needs no escaping.
    """
    log = dist.with_suffix(".vmaf.json")
    cmd = [ff, "-hide_banner", "-loglevel", "error",
           "-i", str(dist), "-i", str(ref),
           "-lavfi",
           (f"[0:v]setpts=PTS-STARTPTS[d];[1:v]setpts=PTS-STARTPTS[r];"
            f"[d][r]libvmaf=log_fmt=json:log_path={log.name}"),
           "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(log.parent))
    if r.returncode != 0:
        print(f"    VMAF failed: {(r.stderr or '')[-200:]}")
        return None
    try:
        d = json.loads(log.read_text(encoding="utf-8"))
        return float(d["pooled_metrics"]["vmaf"]["mean"])
    except Exception:
        m = re.search(r"VMAF score:\s*([0-9.]+)", (r.stderr or ""))
        return float(m.group(1)) if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--seconds", type=float, default=60.0)
    a = ap.parse_args()

    ff = config.ffmpeg()
    pdir = config.project_dir(a.project)
    src = pdir / "source.mp4"
    if not src.exists():
        print(f"no source.mp4 in {pdir}")
        return 1

    p = enc.probe_qsv(ff, force=True)
    print(f"QSV probe: ok={p['ok']} listed={p['listed']} - {p['why']}")
    if not p["ok"]:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(
            {"qsv_available": False, "why": p["why"],
             "chosen_global_quality": None}, indent=2), encoding="utf-8")
        print("QSV unusable on this machine - recorded, libx264 stays.")
        return 0

    work = pdir / "_work_cal"
    work.mkdir(parents=True, exist_ok=True)

    # Sample from the middle of the film - the opening is logos and the
    # closing is credits, neither of which represents the footage we encode.
    dur = float(subprocess.run(
        [config.ffprobe(), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(src)],
        capture_output=True, text=True).stdout.strip() or 0.0)
    ss = max(0.0, dur / 2.0)
    w, h = int(config.OUTPUT_WIDTH), int(config.OUTPUT_HEIGHT)
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease:"
          f"flags={config.VIDEO_SCALER},"
          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,"
          f"fps={config.OUTPUT_FPS}")

    # The reference: the sample put through the render's filter chain and
    # stored LOSSLESS, so every codec below is compared against the same
    # pixels the encoders are handed.
    ref = work / "ref_lossless.mp4"
    print(f"\nsample: {a.seconds:.0f}s from {ss:.0f}s of {dur:.0f}s")
    print("building lossless reference...")
    r = _run([ff, "-hide_banner", "-loglevel", "error", "-y",
              "-ss", f"{ss:.3f}", "-t", f"{a.seconds:.3f}", "-i", str(src),
              "-vf", vf, "-an",
              "-c:v", "libx264", "-preset", "ultrafast", "-qp", "0",
              "-pix_fmt", "yuv420p", str(ref)])
    if r.returncode != 0:
        print(f"reference build failed: {(r.stderr or '')[-300:]}")
        return 1
    print(f"  {ref.stat().st_size/1048576:.0f} MB")

    results = []

    # libx264 CRF 20 - the quality bar we must match
    x264 = work / "x264_crf20.mp4"
    t0 = time.perf_counter()
    _run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(ref),
          "-c:v", "libx264", "-preset", config.VIDEO_PRESET,
          "-crf", str(config.VIDEO_CRF), "-pix_fmt", config.VIDEO_PIX_FMT,
          str(x264)])
    t_x264 = time.perf_counter() - t0
    v_x264 = _vmaf(ff, ref, x264)
    mb_x264 = x264.stat().st_size / 1048576
    if v_x264 is None:
        print("could not score the libx264 encode - there is no bar to match, "
              "so there is nothing to calibrate against. Aborting rather than "
              "picking a quality number without evidence.")
        return 1
    print(f"\nlibx264 crf{config.VIDEO_CRF} preset {config.VIDEO_PRESET}: "
          f"VMAF {v_x264:.3f}  {t_x264:.1f}s  {mb_x264:.1f} MB  <-- the bar")

    print("\nh264_qsv sweep:")
    print(f"  {'gq':>4} {'VMAF':>9} {'vs bar':>8} {'sec':>7} {'MB':>7}")
    for gq in SWEEP:
        o = work / f"qsv_gq{gq}.mp4"
        t0 = time.perf_counter()
        rr = _run([ff, "-hide_banner", "-loglevel", "error", "-y",
                   "-i", str(ref),
                   "-c:v", "h264_qsv", "-global_quality", str(gq),
                   "-look_ahead", "0", "-async_depth", "4",
                   "-pix_fmt", "nv12", str(o)])
        el = time.perf_counter() - t0
        if rr.returncode != 0 or not o.exists():
            print(f"  {gq:>4}   encode failed")
            continue
        v = _vmaf(ff, ref, o)
        mb = o.stat().st_size / 1048576
        if v is None:
            print(f"  {gq:>4}   VMAF failed")
            continue
        results.append({"global_quality": gq, "vmaf": round(v, 3),
                        "seconds": round(el, 1), "mb": round(mb, 1)})
        print(f"  {gq:>4} {v:9.3f} {v-v_x264:+8.3f} {el:7.1f} {mb:7.1f}")

    # Choose the CHEAPEST setting that still meets the bar. Higher
    # global_quality = lower quality = smaller/faster, so walk from the
    # cheapest end and take the first that clears the bar.
    passing = [r0 for r0 in results if r0["vmaf"] >= v_x264 - TOLERANCE]
    chosen = max(passing, key=lambda r0: r0["global_quality"]) if passing else None

    rec = {
        "qsv_available": True,
        "measured_on": a.project,
        "sample_seconds": a.seconds,
        "sample_from_seconds": round(ss, 1),
        "reference": "lossless qp=0 of the render's own filter chain",
        "bar": {"codec": "libx264", "crf": int(config.VIDEO_CRF),
                "preset": config.VIDEO_PRESET, "vmaf": round(v_x264, 3),
                "seconds": round(t_x264, 1), "mb": round(mb_x264, 1)},
        "tolerance_vmaf": TOLERANCE,
        "sweep": results,
        "chosen_global_quality": chosen["global_quality"] if chosen else None,
        "chosen_vmaf": chosen["vmaf"] if chosen else None,
        "speedup_vs_x264": (round(t_x264 / chosen["seconds"], 2)
                            if chosen and chosen["seconds"] > 0 else None),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=2), encoding="utf-8")

    print()
    if chosen:
        print(f"CHOSEN global_quality={chosen['global_quality']} "
              f"(VMAF {chosen['vmaf']:.3f} vs bar {v_x264:.3f}, "
              f"{rec['speedup_vs_x264']}x faster, "
              f"{chosen['mb']:.1f} MB vs {mb_x264:.1f} MB)")
    else:
        print("NO global_quality reached the CRF 20 bar within tolerance. "
              "Recorded; libx264 stays. This is the honest outcome, not a "
              "reason to lower the bar.")
    print(f"written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
