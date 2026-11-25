# -*- coding: utf-8 -*-
"""subcover.py - hide subtitles burned into the downloaded film (owner,
19 Nov: the next films come with subtitles in the picture).

A burned-in subtitle cannot be switched off: it is pixels. Left in, the
video shows the film's own words in a language and timing that have nothing
to do with the narration, on top of the channel's captions.

  detect()     WHERE the subtitles are: frames sampled across the whole film,
               and for each row of the picture, how often it carries text -
               bright pixels with hard edges on both sides (a letter's stroke
               against its outline or the scene). Subtitles come and go but
               always on the same rows near the bottom, so those rows light up
               in many frames while a bright sky or a window lights up rows
               anywhere. The band is the run of rows in the lower part of the
               frame that carries text far more often than the rows above it.
               Saved to projects/<name>/subtitle_band.json, which can be
               edited by hand (or set {"found": false}) and is then taken as
               written.
  prefix()     the ffmpeg filter that goes first in every chain reading the
               film:
                 blur  (default when the subtitles sit IN the picture) - blur
                       the band where it is; the frame keeps its size and
                       nothing is cut. Owner, 25 Nov, on Lost in the Stars:
                       "mình kêu làm mờ chứ có phải cắt đen như v đâu, chỉ
                       mờ một khoảng ở caption th" - the crop had cut the
                       bottom 114 rows of a 1920x816 picture and the letterbox
                       grew to fill them.
                 crop  (default when the subtitles sit in the black BAR
                       under the picture) - keep the picture down to the top of the
                       subtitle band; with a letterbox, also drop the bars, so
                       the result is centred again by the usual scale + pad. A
                       subtitle that sits in the black bar costs no picture
                       at all; one inside the picture costs the strip under
                       it, and the letterbox gets a little wider.
                 black - paint the band black (the frame keeps its size).
  map_region() a censor box drawn on a SOURCE frame, moved into the cropped
               frame (render.region_to_output then maps it as before).

SUBTITLE_COVER: "auto" (detect; cover only what was found: blur in the
picture, crop in the bar), "blur" / "crop" / "black" (same, forcing the
mode), "off".
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import config

VERSION = 2
_STATE: dict = {"pdir": None, "band": None}
_N = [0]


def _mode() -> str:
    m = str(getattr(config, "SUBTITLE_COVER", "auto")).lower()
    return m if m in ("auto", "blur", "crop", "black", "off") else "auto"


def in_bar(b: dict) -> bool:
    """The band sits in the black bar under the picture: unlit rows lie
    between the bottom of the picture and the band."""
    ct, cb = (b.get("content") or [0, int(b.get("src_h") or 0)])[:2]
    return int(cb) < int(b["y0"]) - 1


def cover(b: dict | None) -> str:
    """How this band is hidden: "blur", "crop" or "black" ("" for none)."""
    if not b:
        return ""
    m = _mode()
    if m == "auto":
        return "crop" if in_bar(b) else "blur"
    return m


def blur_box(b: dict) -> tuple:
    """(y, h, sigma): the band on even rows (4:2:0 chroma), and a blur
    strong enough that no letter survives (about a fifth of its height)."""
    h_src = int(b.get("src_h") or 0) or 10 ** 6
    y = int(b["y0"]) // 2 * 2
    hh = (int(b["y1"]) - y + 1) // 2 * 2
    hh = max(2, min(hh, (h_src - y) // 2 * 2))
    return y, hh, max(6.0, round(hh * 0.18, 1))


def _probe(path: Path) -> tuple:
    r = subprocess.run([config.ffprobe(), "-v", "error", "-select_streams",
                        "v:0", "-show_entries",
                        "stream=width,height:format=duration", "-of",
                        "json", str(path)], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout or "{}")
        s = d["streams"][0]
        return int(s["width"]), int(s["height"]), float(
            d.get("format", {}).get("duration") or 0.0)
    except (KeyError, IndexError, ValueError, TypeError):
        return 0, 0, 0.0


def text_rows(gray, bright: int = None, edge: int = None):
    """Per-row share of 'text pixels' in the middle 80% of the width: bright,
    with a hard edge to the left AND to the right within 3 px (a stroke)."""
    import numpy as np
    bright = int(bright if bright is not None
                 else getattr(config, "SUBTITLE_BRIGHT", 175))
    edge = int(edge if edge is not None
               else getattr(config, "SUBTITLE_EDGE", 60))
    g = gray.astype(np.int16)
    h, w = g.shape
    a, b = int(w * 0.1), int(w * 0.9)
    core = g[:, a:b]
    left = np.zeros_like(core, dtype=bool)
    right = np.zeros_like(core, dtype=bool)
    for k in (1, 2, 3):
        left |= (core - g[:, a - k:b - k]) > edge
        right |= (core - g[:, a + k:b + k]) > edge
    hit = (core > bright) & left & right
    return hit.mean(axis=1)


def find_band(freq, h: int, content: tuple | None = None) -> dict:
    """The subtitle band from per-row text frequency, or found=False."""
    import numpy as np
    f = np.asarray(freq, dtype=float)
    ct, cb = content or (0, h)
    top_part = f[ct:ct + int((cb - ct) * 0.5)]
    base = float(np.median(top_part)) if len(top_part) else 0.0
    floor = max(float(getattr(config, "SUBTITLE_MIN_FREQ", 0.06)),
                base * 3.0 + 0.02)
    lo = int(h * 0.55)
    rows = [r for r in range(lo, h) if f[r] >= floor]
    if not rows:
        return {"found": False, "why": f"no row in the lower part carries "
                f"text in {floor:.0%} of frames (baseline {base:.1%})"}
    # the largest group of rows, bridging gaps up to 3% of the height
    gap = max(2, int(h * 0.03))
    groups, cur = [], [rows[0]]
    for r in rows[1:]:
        if r - cur[-1] <= gap:
            cur.append(r)
        else:
            groups.append(cur)
            cur = [r]
    groups.append(cur)
    g = max(groups, key=lambda x: (sum(f[r] for r in x), len(x)))
    y0, y1 = g[0], g[-1] + 1
    span = y1 - y0
    if span < h * 0.015 or span > h * 0.22:
        return {"found": False, "why": f"text rows {y0}-{y1} are not a "
                f"subtitle-shaped band ({span}px of {h})"}
    m = max(2, int(h * 0.015))
    return {"found": True, "y0": max(0, y0 - m), "y1": min(h, y1 + m),
            "peak": round(float(f[y0:y1].max()), 3),
            "baseline": round(base, 4),
            "why": f"rows {y0}-{y1} carry text in up to "
                   f"{float(f[y0:y1].max()):.0%} of frames (rows above: "
                   f"{base:.1%})"}


def detect(source: Path, probes: int = None, frames=None) -> dict:
    """Measure the band on `source` (or on `frames`, a list of gray arrays,
    in tests). Returns the dict saved to subtitle_band.json."""
    import numpy as np
    probes = int(probes or getattr(config, "SUBTITLE_PROBES", 120))
    w, h, dur = _probe(source) if frames is None else (
        frames[0].shape[1], frames[0].shape[0], 0.0)
    if not w or not h:
        return {"found": False, "why": "the source could not be read"}
    sw = 640
    sh = max(2, int(round(h * sw / w / 2)) * 2)
    if frames is None:
        frames = []
        for i in range(probes):
            t = dur * (0.04 + 0.92 * (i + 0.5) / probes)
            r = subprocess.run(
                [config.ffmpeg(), "-v", "error", "-ss", f"{t:.3f}", "-i",
                 str(source), "-frames:v", "1", "-vf",
                 f"scale={sw}:{sh},format=gray", "-f", "rawvideo", "-"],
                capture_output=True)
            buf = r.stdout or b""
            if len(buf) >= sw * sh:
                frames.append(np.frombuffer(buf[:sw * sh], np.uint8)
                              .reshape(sh, sw))
    else:
        sw, sh = w, h
    if len(frames) < 10:
        return {"found": False, "why": f"only {len(frames)} frames read"}
    share = float(getattr(config, "SUBTITLE_ROW_SHARE", 0.025))
    lit = np.zeros(sh, dtype=bool)
    hits = np.zeros(sh)
    for g in frames:
        hits += text_rows(g) >= share
        lit |= g.mean(axis=1) > 8.0
    freq = hits / len(frames)
    content = _picture(lit, sh)
    band = find_band(freq, sh, content)
    if band["found"]:
        # The picture is the lit run around the middle that does not reach
        # into the band: subtitles printed in the black bar light those rows
        # too, and must not be taken for picture.
        content = _picture(lit, sh, exclude=(band["y0"], band["y1"]))
    k = h / sh
    out = {"found": band["found"], "src_w": w, "src_h": h,
           "frames": len(frames),
           "content": [int(content[0] * k), int(round(content[1] * k))]}
    if band["found"]:
        y0, y1 = int(band["y0"] * k), int(round(band["y1"] * k))
        out.update(y0=y0, y1=y1, peak=band["peak"],
                   why=f"rows {y0}-{y1} of {h} carry text in up to "
                       f"{band['peak']:.0%} of {len(frames)} frames (the "
                       f"upper half of the picture: "
                       f"{band['baseline']:.1%})")
    else:
        out["why"] = band["why"]
    return out


def _picture(lit, h: int, exclude: tuple | None = None) -> tuple:
    """(top, bottom) of the run of lit rows that holds the middle row."""
    import numpy as np
    m = np.array(lit, dtype=bool)
    if exclude:
        m[int(exclude[0]):int(exclude[1])] = False
    if not m.any():
        return 0, h
    mid = h // 2
    if not m[mid]:
        return int(np.argmax(m)), int(h - np.argmax(m[::-1]))
    top = mid
    while top > 0 and m[top - 1]:
        top -= 1
    bot = mid
    while bot < h and m[bot]:
        bot += 1
    return top, bot


def load(pdir: Path, source: Path | None = None, measure=True) -> dict:
    """The project's band: subtitle_band.json as written (detected once and
    saved, or edited by hand), else detected now when `measure`."""
    p = Path(pdir) / "subtitle_band.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if not measure:
        return {"found": False, "why": "not measured"}
    src = source or (Path(pdir) / "source.mp4")
    if not Path(src).exists():
        return {"found": False, "why": "no source"}
    band = detect(Path(src))
    try:
        p.write_text(json.dumps(band, indent=1), encoding="utf-8")
    except OSError:
        pass
    return band


def begin(pdir: Path, source: Path | None = None) -> dict:
    """Set the band for one render. Returns it (found False when off)."""
    if _mode() == "off":
        band = {"found": False, "why": "SUBTITLE_COVER is off"}
    else:
        band = load(pdir, source)
    _STATE.update(pdir=Path(pdir), band=band)
    return band


def end() -> None:
    _STATE.update(pdir=None, band=None)


def _band_for(pdir: Path | None) -> dict | None:
    if _mode() == "off":
        return None
    if pdir is not None and (_STATE.get("pdir") != Path(pdir)):
        b = load(pdir, measure=False)
    else:
        b = _STATE.get("band")
    return b if b and b.get("found") else None


def rect(pdir: Path | None = None):
    """(x, y, w, h) of the source kept by a crop, or None."""
    b = _band_for(pdir)
    if cover(b) != "crop":
        return None
    w, h = int(b["src_w"]), int(b["src_h"])
    ct, cb = (b.get("content") or [0, h])[:2]
    y0 = int(b["y0"])
    top = int(ct) if int(ct) < y0 else 0
    bot = min(int(cb), y0) if y0 > top else int(cb)
    hh = (bot - top) // 2 * 2
    if hh < h * 0.3:
        return None
    return 0, top, w, hh


def prefix(pdir: Path | None = None) -> str:
    """The filter that goes FIRST on every frame read from the film, with a
    trailing comma, or ""."""
    b = _band_for(pdir)
    if not b:
        return ""
    how = cover(b)
    if how == "black":
        y0, y1 = int(b["y0"]), int(b["y1"])
        return (f"drawbox=x=0:y={y0}:w=iw:h={y1 - y0}:color=black:t=fill,")
    if how == "blur":
        y, hh, sigma = blur_box(b)
        _N[0] += 1
        k = f"scb{_N[0]}"       # labels unique per use: one graph may read
        return (f"split=2[{k}a][{k}b];"         # the film several times
                f"[{k}b]crop=iw:{hh}:0:{y},gblur=sigma={sigma}:steps=3[{k}c];"
                f"[{k}a][{k}c]overlay=0:{y},")
    r = rect(pdir)
    if not r:
        return ""
    x, y, w, h = r
    return f"crop={w}:{h}:{x}:{y},"


def map_region(x: int, y: int, w: int, h: int, src_w: int, src_h: int,
               pdir: Path | None = None) -> tuple:
    """A censor box in SOURCE pixels -> (x, y, w, h, src_w, src_h) in the
    frame after the crop (unchanged when nothing is cropped)."""
    r = rect(pdir)
    if not r:
        return x, y, w, h, src_w, src_h
    rx, ry, rw, rh = r
    y2 = max(0, min(rh, y + h - ry))
    y1 = max(0, min(rh, y - ry))
    return x, y1, w, max(1, y2 - y1), rw, rh


def signature(pdir: Path | None = None) -> str:
    """What the cover does, for cache keys - never prefix() itself, whose
    blur labels are numbered per use."""
    b = _band_for(pdir)
    how = cover(b)
    if not how:
        return f"sc{VERSION}:none"
    if how == "blur":
        return f"sc{VERSION}:blur:{blur_box(b)}"
    if how == "black":
        return f"sc{VERSION}:black:{b['y0']}:{b['y1']}"
    return f"sc{VERSION}:crop:{rect(pdir)}"


if __name__ == "__main__":
    # python -m pipeline.subcover <project> [--again]
    #   find the band now (or show the saved one) and say what will be covered
    import sys
    if len(sys.argv) < 2:
        print("usage: python -m pipeline.subcover <project> [--again]")
        sys.exit(2)
    _pd = config.project_dir(sys.argv[1])
    if "--again" in sys.argv[2:]:
        (_pd / "subtitle_band.json").unlink(missing_ok=True)
    _b = begin(_pd)
    print(json.dumps(_b, indent=1))
    print(f"cover: {cover(_band_for(None)) or 'nothing'} "
          f"{prefix().rstrip(',')} "
          f"(SUBTITLE_COVER={_mode()}; edit {_pd / 'subtitle_band.json'} "
          f"to change)")
