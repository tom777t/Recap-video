"""The picture-quality contract, asserted on the finished file.

WHY
---
Picture quality is decided by about six settings spread across four ffmpeg
invocations, and nothing checked that the file on disk matched them. A render
could silently fall back - wrong resolution, wrong frame rate, a dropped
pix_fmt, an encode that bailed to a trickle bitrate - and the only detector was
somebody watching it later and saying "this looks worse".

So the settings live in config.RENDER_QUALITY_CONTRACT and this module measures
final.mp4 against them. It is a CONTRACT, not a preference: tools/
test_quality.py fails if the constants drift from the contract, so changing the
output format is a deliberate two-file edit rather than a one-character
accident.

WHAT QUALITY ACTUALLY DEPENDS ON HERE
-------------------------------------
In descending order of effect, measured on tokyodrift2006:

 1. THE SOURCE. source.mp4 is 1280x544. The 1080p output is a 1.50x upscale to
    1920x816 in a padded frame. No setting below recovers detail that was never
    in the file. This is the ceiling.
 2. HOW MUCH SLOW-MOTION. Stretching a short window over long narration
    (setpts) duplicates frames and reads as soft, juddery picture. This is the
    one that visibly changed: widening 28 windows cut stretch factors that had
    been up to 3.9x. It is governed by BINDING_SLOWDOWN_MAX, not by any encoder
    flag.
 3. GENERATION COUNT. A frame is encoded three times (clip -> xfade -> music
    mix). All three ran at CRF 20, so two of them discarded detail the final
    encode could not get back. Intermediates are now CRF 16.
 4. THE SCALER. Default bicubic -> lanczos, which matters on a 1.5x upscale.
 5. CRF / preset on the final encode: 20 / medium.

Known remaining limits, deliberately NOT changed here because they are
editorial decisions rather than defects - see report_limits():
 * 23.976 fps source -> 30 fps output duplicates roughly a quarter of frames on
   an uneven cadence, which is visible as judder on pans.
 * Ken Burns zoom (MOTION_ZOOM 0.08) adds up to another 8% of upscale on top of
   the 50% already applied.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console

console = Console()


def _probe(ffprobe: str, path: Path) -> dict:
    out = {}
    r = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate,codec_name,pix_fmt",
         "-show_entries", "format=bit_rate,duration",
         "-of", "default=noprint_wrappers=1", str(path)],
        capture_output=True, text=True)
    for line in (r.stdout or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _fps_of(raw: str) -> float:
    try:
        if "/" in raw:
            a, b = raw.split("/", 1)
            return float(a) / float(b) if float(b) else 0.0
        return float(raw)
    except (ValueError, ZeroDivisionError):
        return 0.0


def check_output(ffprobe: str, final: Path, contract: dict | None = None
                 ) -> tuple[bool, list[str]]:
    """Measure `final` against the quality contract.

    Returns (ok, [problems]). Never raises on a missing probe field: an
    unreadable file is reported as a problem, not swallowed as a pass.
    """
    import config
    c = dict(contract or config.RENDER_QUALITY_CONTRACT)
    if not final.exists():
        return False, [f"{final.name} does not exist"]
    info = _probe(ffprobe, final)
    if not info:
        return False, [f"could not probe {final.name}"]

    bad = []
    for key, field in (("width", "width"), ("height", "height")):
        want = int(c[key])
        try:
            got = int(info.get(field, 0))
        except ValueError:
            got = 0
        if got != want:
            bad.append(f"{key} is {got}, contract says {want}")

    want_fps = float(c["fps"])
    got_fps = _fps_of(info.get("r_frame_rate", "0"))
    if abs(got_fps - want_fps) > 0.05:
        bad.append(f"frame rate is {got_fps:.3f}, contract says {want_fps:.3f}")

    if info.get("pix_fmt") != c["pix_fmt"]:
        bad.append(f"pix_fmt is {info.get('pix_fmt')!r}, contract says "
                   f"{c['pix_fmt']!r}")
    if info.get("codec_name") != c["codec"]:
        bad.append(f"codec is {info.get('codec_name')!r}, contract says "
                   f"{c['codec']!r}")

    return (not bad), bad


def measured_bitrate_kbps(ffprobe: str, path: Path) -> float:
    """Final bitrate, for information. NOT a pass/fail criterion - see
    config.RENDER_BITRATE_REFERENCE_KBPS for why."""
    try:
        return float(_probe(ffprobe, path).get("bit_rate", 0)) / 1000.0
    except ValueError:
        return 0.0


def report(ffprobe: str, final: Path) -> bool:
    ok, bad = check_output(ffprobe, final)
    if ok:
        import config
        c = config.RENDER_QUALITY_CONTRACT
        kbps = measured_bitrate_kbps(ffprobe, final)
        console.print(f"[cyan]Quality:[/] {c['width']}x{c['height']} "
                      f"@ {c['fps']}fps {c['pix_fmt']}, CRF "
                      f"{config.VIDEO_CRF}/{config.VIDEO_PRESET} final, CRF "
                      f"{config.VIDEO_CRF_INTERMEDIATE} intermediates, "
                      f"{config.VIDEO_SCALER} scaler - contract met"
                      + (f" ({kbps:.0f} kbit/s)" if kbps else ""))
        return True
    console.print("[red]Quality contract NOT met:[/]")
    for b in bad:
        console.print(f"[red]    {b}[/]")
    return False


def source_headroom(ffprobe: str, source: Path) -> dict:
    """How much of the output resolution the SOURCE can actually fill.

    Printed before a render so "1080p" is never mistaken for a 1080p picture.
    """
    import config
    info = _probe(ffprobe, source)
    try:
        sw, sh = int(info.get("width", 0)), int(info.get("height", 0))
    except ValueError:
        sw = sh = 0
    if not sw or not sh:
        return {}
    w, h = int(config.OUTPUT_WIDTH), int(config.OUTPUT_HEIGHT)
    f = min(w / sw, h / sh)
    return {"src_w": sw, "src_h": sh, "scale": f,
            "fit_w": round(sw * f), "fit_h": round(sh * f),
            "upscale_pct": (f - 1.0) * 100.0,
            "bars_px": int((h - round(sh * f)) / 2)}


def report_source(ffprobe: str, source: Path) -> None:
    hd = source_headroom(ffprobe, source)
    if not hd:
        return
    if hd["scale"] > 1.01:
        console.print(
            f"[yellow]Source:[/] {hd['src_w']}x{hd['src_h']} upscaled "
            f"{hd['upscale_pct']:.0f}% to {hd['fit_w']}x{hd['fit_h']}"
            + (f" with {hd['bars_px']}px bars" if hd["bars_px"] else "")
            + ". The output is 1080p; the PICTURE is not - no encoder setting "
              "adds detail the source never had.")
    else:
        console.print(f"[cyan]Source:[/] {hd['src_w']}x{hd['src_h']} - fills "
                      f"the output frame without upscaling.")
