"""One decode of the finished film, shared by the checks that read its picture.

WHY
---
MOTION-CHECK (freezedetect) and REPEAT-SCENE (perceptual frame hashes) each
decoded every frame of final.mp4 on their own - two full-resolution decodes of
a 17-minute 1080p film per render, minutes each, of the same frames. The
decode is the cost; the two filters on top of it are cheap. So this runs ONE
ffmpeg over the file with the decoded picture split into both filter chains:

    [0:v:0] split -> freezedetect          -> null         (log on stderr)
                  -> crop,fps,scale,gray   -> rawvideo     (frames on stdout)

Both chains are the exact filter strings the standalone checks use
(motion_check.freeze_filter, dupe_check.hash_filter), so each check sees the
same numbers it would have measured itself; tools/test_post_checks.py proves
the outputs are identical.

FAILURE IS NOT A RESULT
-----------------------
If the shared decode fails (non-zero exit, or either half produced nothing a
working decode would), its results are DISCARDED and each check runs its own
original scan. A failed combined run must never hand MOTION-CHECK an empty
freeze list - an empty list reads as "no freezes", i.e. a pass for a file
nobody looked at.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def scan(ff: str, final: Path, interval: float | None = None) -> dict:
    """{"freezes": [...] | None, "hashes": [...] | None, "crop", "interval",
    "shared": bool}. Never raises; None fields mean "measure it yourself"."""
    from pipeline import dupe_check as _dup
    from pipeline import motion_check as _mc

    iv = float(_dup.SAMPLE_INTERVAL_SEC if interval is None else interval)
    res = {"freezes": None, "hashes": None, "crop": None, "interval": iv,
           "shared": False}
    final = Path(final)
    if not final.exists():
        return res
    try:
        crop = _dup.content_crop(final)
        res["crop"] = crop
        graph = (f"[0:v:0]split=2[fz][hs];"
                 f"[fz]{_mc.freeze_filter()}[fzo];"
                 f"[hs]{_dup.hash_filter(iv, crop)}[hso]")
        cmd = [ff, "-hide_banner", "-nostats", "-i", str(final),
               "-filter_complex", graph,
               "-map", "[fzo]", "-f", "null", "-",
               "-map", "[hso]", "-f", "rawvideo", "-pix_fmt", "gray",
               "pipe:1"]
        r = subprocess.run(cmd, capture_output=True)
        log = (r.stderr or b"").decode("utf-8", errors="replace")
        raw = r.stdout or b""
        if r.returncode != 0 or not raw:
            # Could not look: hand nothing over, so each check measures the
            # file itself rather than trusting a half-run decode.
            return res
        res["freezes"] = _mc.parse_freezes(log)
        res["hashes"] = _dup.hashes_from_raw(raw, iv)
        res["shared"] = True
    except Exception:
        res["freezes"] = res["hashes"] = None
        res["shared"] = False
    return res
