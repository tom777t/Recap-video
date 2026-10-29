"""Does the finished film show the same picture twice? Measured on the frames.

WHY SOURCE-SPAN BOOKKEEPING IS NOT ENOUGH
-----------------------------------------
`motion_check.reuse` compares the SOURCE windows two lines were cut from, and
that catches literal reuse of the same footage. It cannot catch the thing a
viewer actually notices, because this film is built out of shot/reverse-shot:
two different source windows, minutes apart in the timeline, can hold a nearly
identical frame - the same character at the same angle in the same room. The
bookkeeping says "different footage" and is correct; the screen says "I have
seen this already" and is also correct.

So this measures the PICTURE. Frames are sampled from final.mp4, reduced to a
perceptual hash, and compared to each other.

THREE WAYS A NAIVE VERSION OF THIS LIES, all handled below:

  * the letterbox. The output is 1920x816 of content in a 1920x1080 frame with
    132px black bars. Over a third of every frame is identical black in every
    frame of the film, which drags every hash towards every other hash. The
    bars are cropped before hashing.
  * flat frames. A fade to black, a dissolve, a white flash - these are all
    near-uniform, all hash alike, and none of them is repeated footage. Frames
    below a variance floor are skipped and reported as skipped, not as clean.
  * adjacent frames. Two samples one second apart inside the same shot SHOULD
    look identical. Only pairs separated by more than MIN_GAP_SEC are compared.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import config

# Sampling interval. 1.0s is ~1050 frames on a 17-minute film, which is 550k
# pair comparisons - fast in numpy and fine-grained enough that a repeated
# shot of a second or more cannot slip between samples.
SAMPLE_INTERVAL_SEC = 1.0
# Hash size: a 32x32 grayscale frame, DCT'd, low-frequency 8x8 block -> 64 bits.
HASH_SIDE = 8
DCT_SIDE = 32
# Hamming distance (of 64) at or below which two frames are "the same shot".
#
# CALIBRATED, not chosen. calibrate() measured 29,439 cross-shot pairs on the
# real final.mp4 with the letterbox cropped out:
#     min 16    p01 22    p05 26    p50 32
# so no two genuinely different shots in this film came within 16 bits of each
# other. A frame compared against a real copy of itself scores 0 - verified by
# concatenating a repeat of a shot 90s later and measuring 0/64.
# 10 sits 6 bits below the closest observed different-shot pair and 10 above an
# exact match, so it has room on both sides. Cropping matters to this number:
# with the 132px bars left in, a quarter of every frame is the same black and
# the closest different-shot pair fell from 16 to 12.
MAX_DISTANCE = 10
# Pairs closer together in the OUTPUT than this are the same shot and expected
# to match.
MIN_GAP_SEC = 8.0
# Frames flatter than this (std of the 32x32 gray block, 0..255) are fades,
# flashes and black - skipped, because they all look alike and none of them is
# a repeated scene.
MIN_VARIANCE = 8.0


def content_crop(path: Path, probes: int = 9) -> str | None:
    """ffmpeg crop= for the picture inside the letterbox, or None.

    MEASURED over frames spread across the WHOLE file, by row brightness.
    ffmpeg's own `cropdetect` was tried first and got it wrong here: pointed at
    a fixed 30-50s window it landed inside the prepended intro block, whose
    frames at that point are entirely black, so it reported no bars at all -
    `crop=1920:1080:0:0`. The bars are 132px top and bottom on this film, 24%
    of every frame, and leaving them in drags every hash towards every other
    hash because a quarter of each one is the same black in all of them.

    A row counts as content if it is non-black in ANY probed frame, so one
    dark scene cannot shrink the crop.
    """
    import numpy as np
    dur = _duration(path)
    if dur <= 0:
        return None
    w, h = _dimensions(path)
    if not w or not h:
        return None
    rows_lit = np.zeros(h, dtype=bool)
    got = 0
    for i in range(max(2, probes)):
        t = dur * (i + 0.5) / max(2, probes)
        r = subprocess.run(
            [config.ffmpeg(), "-v", "error", "-ss", f"{t:.3f}",
             "-i", str(path), "-frames:v", "1", "-vf", "format=gray",
             "-f", "rawvideo", "-pix_fmt", "gray", "-"],
            capture_output=True)
        if len(r.stdout or b"") < w * h:
            continue
        a = np.frombuffer(r.stdout[:w * h], dtype=np.uint8).reshape(h, w)
        rows_lit |= (a.mean(axis=1) > 8.0)
        got += 1
    if got == 0 or not rows_lit.any():
        return None
    top = int(np.argmax(rows_lit))
    bot = int(h - np.argmax(rows_lit[::-1]))
    ch = bot - top
    if ch <= 0 or ch >= h - 4:
        return None                      # no meaningful letterbox
    return f"crop={w}:{ch}:0:{top}"


def _duration(path: Path) -> float:
    r = subprocess.run(
        [config.ffprobe(), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=duration", "-of", "default=nw=1:nk=1",
         str(path)], capture_output=True, text=True)
    try:
        return float((r.stdout or "0").strip().splitlines()[0])
    except (ValueError, IndexError):
        return 0.0


def _dimensions(path: Path) -> tuple:
    r = subprocess.run(
        [config.ffprobe(), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0",
         str(path)], capture_output=True, text=True)
    try:
        w, h = (r.stdout or "").strip().splitlines()[0].split(",")[:2]
        return int(w), int(h)
    except (ValueError, IndexError):
        return 0, 0


def frame_hashes(path: Path, interval: float = SAMPLE_INTERVAL_SEC,
                 crop: str | None = None) -> list:
    """[(t_seconds, hash_int, variance)] sampled across the whole file."""
    import numpy as np

    vf = []
    if crop:
        vf.append(crop)
    vf += [f"fps=1/{max(0.05, float(interval)):.4f}",
           f"scale={DCT_SIDE}:{DCT_SIDE}", "format=gray"]
    cmd = [config.ffmpeg(), "-v", "error", "-i", str(path),
           "-vf", ",".join(vf), "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    r = subprocess.run(cmd, capture_output=True)
    buf = r.stdout or b""
    n = DCT_SIDE * DCT_SIDE
    count = len(buf) // n
    if count == 0:
        return []
    arr = np.frombuffer(buf[:count * n], dtype=np.uint8).reshape(
        count, DCT_SIDE, DCT_SIDE).astype("float64")

    # 2-D DCT-II via matrix multiply - no scipy dependency.
    k = np.arange(DCT_SIDE)
    basis = np.cos(np.pi * (2 * k[:, None] + 1) * k[None, :]
                   / (2 * DCT_SIDE))
    out = []
    for i in range(count):
        img = arr[i]
        var = float(img.std())
        d = basis.T @ img @ basis
        block = d[:HASH_SIDE, :HASH_SIDE].copy()
        block[0, 0] = 0.0                  # drop DC: overall brightness
        med = float(np.median(block))
        bits = (block > med).flatten()
        h = 0
        for b in bits:
            h = (h << 1) | int(b)
        out.append((round(i * float(interval), 3), h, round(var, 2)))
    return out


def _dist(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def near_duplicates(hashes: list, max_distance: int = MAX_DISTANCE,
                    min_gap: float = MIN_GAP_SEC,
                    min_variance: float = MIN_VARIANCE) -> list:
    """Pairs of OUTPUT timestamps whose pictures are near-identical.

    Returns [{a, b, distance, gap}] sorted worst (most similar) first, with
    one entry per cluster rather than one per frame pair - a repeated 4-second
    shot sampled every second would otherwise report 16 times and bury
    everything else.
    """
    usable = [(t, h) for t, h, v in hashes if v >= min_variance]
    hits = []
    for i, (ta, ha) in enumerate(usable):
        for tb, hb in usable[i + 1:]:
            if tb - ta < min_gap:
                continue
            d = _dist(ha, hb)
            if d <= max_distance:
                hits.append({"a": ta, "b": tb, "distance": d,
                             "gap": round(tb - ta, 2)})
    # collapse clusters: keep the best hit per (rounded) pair neighbourhood
    hits.sort(key=lambda r: (r["distance"], -r["gap"]))
    kept: list = []
    for h in hits:
        if any(abs(h["a"] - k["a"]) < MIN_GAP_SEC
               and abs(h["b"] - k["b"]) < MIN_GAP_SEC for k in kept):
            continue
        kept.append(h)
    return kept


def check(path: Path, interval: float = SAMPLE_INTERVAL_SEC) -> tuple:
    """(ok, findings, info). Measures final.mp4 and nothing else."""
    crop = content_crop(Path(path))
    hs = frame_hashes(Path(path), interval, crop)
    info = {"crop": crop, "sampled": len(hs),
            "skipped_flat": sum(1 for _t, _h, v in hs if v < MIN_VARIANCE)}
    if not hs:
        return True, [], info
    dupes = near_duplicates(hs)
    info["pairs"] = dupes
    find = []
    for d in dupes:
        find.append(
            f"the picture at {_hms(d['a'])} and {_hms(d['b'])} is "
            f"near-identical (hamming {d['distance']}/64, "
            f"{d['gap']:.0f}s apart)")
    return (not find), find, info


def _hms(t: float) -> str:
    t = float(t)
    return f"{int(t // 60)}:{t % 60:05.2f}"


def calibrate(path: Path, interval: float = SAMPLE_INTERVAL_SEC) -> dict:
    """Distance distribution on a real file, for choosing MAX_DISTANCE.

    A threshold on a perceptual hash is meaningless without knowing what
    ordinary DIFFERENT shots in this film score. Reports the percentiles so
    the bar can sit below the bulk of them rather than being picked by feel.
    """
    import numpy as np
    crop = content_crop(Path(path))
    hs = frame_hashes(Path(path), interval, crop)
    usable = [(t, h) for t, h, v in hs if v >= MIN_VARIANCE]
    ds = []
    for i, (ta, ha) in enumerate(usable):
        for tb, hb in usable[i + 1:]:
            if tb - ta < MIN_GAP_SEC:
                continue
            ds.append(_dist(ha, hb))
    if not ds:
        return {"pairs": 0}
    a = np.array(ds)
    return {"pairs": int(a.size), "crop": crop,
            "sampled": len(hs), "usable": len(usable),
            "min": int(a.min()), "p01": float(np.percentile(a, 1)),
            "p05": float(np.percentile(a, 5)),
            "p50": float(np.percentile(a, 50)),
            "mean": float(a.mean())}
