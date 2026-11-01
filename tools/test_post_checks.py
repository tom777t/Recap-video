"""Post-render checks: one decode of the finished film, same verdicts.

THE COST
--------
MOTION-CHECK (freezedetect) and REPEAT-SCENE (frame hashes) each decoded every
frame of final.mp4; FILE-CHECK scanned every packet three times (pts_gaps) and
counted them twice; QUALITY-CONTRACT probed the header five times; every clip
was probed by _verify_clip and again, seconds later, by the xfade assembler,
and a cache hit re-measured bytes that were measured when they were built.

THE CHANGE (pipeline/film_scan.py, probe memo, quality memo, cache sidecars)
---------------------------------------------------------------------------
One decode feeds both picture checks; probes are remembered per FILE VERSION
(size+mtime+inode); a cached clip carries its own measurement. None of this
may change a verdict, so every case below compares against the standalone
measurement on a real file built with ffmpeg.

Cases
-----
  SCAN-IDENTICAL       the shared decode yields exactly the freezes, crop and
                       hashes the standalone checks measure, and both checks
                       return the same verdict and findings with and without it.
  SCAN-ONE-DECODE      the shared scan decodes the whole file ONCE (the old
                       path decoded it twice); prints the time saved.
  SCAN-FAIL-NOT-PASS   a shared decode that fails hands over NOTHING, and the
                       checks measure for themselves - the freeze is still
                       found. A failed scan must never read as "no freezes".
  CROP-MEASURED        the letterbox crop is found on a 1920x816-in-1080 file.
  PROBE-MEMO           a second probe of an unchanged file is not re-run; a
                       rewritten file is measured again; a failed probe is not
                       remembered.
  CACHE-SIDECAR        a cache hit adopts the measurement stored with its
                       entry; a changed entry or copy is measured again.

Run:  python tools/test_post_checks.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="postchk_"))
_FILM = _TMP / "film.mp4"


def _film() -> Path:
    """42s, 1920x1080 with 132px bars: 20s of moving picture, a 2s FREEZE
    (cloned last frame), then the same 20s again (a repeated scene)."""
    if _FILM.exists():
        return _FILM
    cmd = [config.ffmpeg(), "-y", "-v", "error",
           "-f", "lavfi", "-i", "testsrc2=s=1920x816:r=30:d=20",
           "-filter_complex",
           "[0:v]split=2[a][b];[a]tpad=stop_mode=clone:stop_duration=2[a2];"
           "[b]setpts=PTS-STARTPTS[b2];[a2][b2]concat=n=2:v=1:a=0,"
           "pad=1920:1080:0:132,format=yuv420p[v]",
           "-map", "[v]", "-c:v", "libx264", "-preset", "ultrafast",
           str(_FILM)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-400:])
    return _FILM


class _Count:
    """Count ffmpeg/ffprobe runs against one file while active."""

    def __init__(self, needle: str):
        self.needle, self.calls = needle, []

    def __enter__(self):
        self._real = subprocess.run

        def run(cmd, *a, **k):
            s = " ".join(map(str, cmd)) if isinstance(cmd, (list, tuple)) \
                else str(cmd)
            if self.needle in s:
                self.calls.append(s)
            return self._real(cmd, *a, **k)
        subprocess.run = run
        return self

    def __exit__(self, *exc):
        subprocess.run = self._real

    def full_decodes(self):
        return [c for c in self.calls
                if os.path.basename(c.split()[0]).startswith("ffmpeg")
                and " -ss " not in c]


def test_scan_identical():
    from pipeline import dupe_check as dc
    from pipeline import film_scan as fs
    from pipeline import motion_check as mc
    f = _film()
    ff = config.ffmpeg()
    alone_fz = mc.freezes(ff, f)
    crop = dc.content_crop(f)
    alone_hs = dc.frame_hashes(f, dc.SAMPLE_INTERVAL_SEC, crop)
    sc = fs.scan(ff, f)
    if not sc["shared"]:
        return False, "the shared decode did not run on a valid file"
    if sc["freezes"] != alone_fz:
        return False, f"freezes differ: {sc['freezes']} vs {alone_fz}"
    if sc["crop"] != crop:
        return False, f"crop differs: {sc['crop']} vs {crop}"
    if sc["hashes"] != alone_hs:
        return False, (f"hashes differ ({len(sc['hashes'])} vs "
                       f"{len(alone_hs)} frames)")
    draft = {"lines": []}
    m1 = mc.check(ff, f, draft)
    m2 = mc.check(ff, f, draft, scan=sc)
    d1 = dc.check(f)
    d2 = dc.check(f, scan=sc)
    if m1 != m2:
        return False, f"MOTION-CHECK verdict changed: {m1[:2]} vs {m2[:2]}"
    if d1 != d2:
        return False, f"REPEAT-SCENE verdict changed: {d1[:2]} vs {d2[:2]}"
    if m1[0] is not False or not alone_fz:
        return False, "fixture freeze was not detected - the fixture is wrong"
    if d1[0] is not False:
        return False, "fixture repeat was not detected - the fixture is wrong"
    return True, (f"{len(alone_fz)} freeze(s), {len(alone_hs)} hashes, crop "
                  f"{crop}: identical; MOTION {m1[0]} / REPEAT {d1[0]} "
                  f"verdicts unchanged")


def test_scan_one_decode():
    from pipeline import dupe_check as dc
    from pipeline import film_scan as fs
    from pipeline import motion_check as mc
    f = _film()
    ff = config.ffmpeg()
    with _Count(str(f)) as old:
        t0 = time.time()
        mc.freezes(ff, f)
        dc.frame_hashes(f, dc.SAMPLE_INTERVAL_SEC, dc.content_crop(f))
        t_old = time.time() - t0
    with _Count(str(f)) as new:
        t0 = time.time()
        fs.scan(ff, f)
        t_new = time.time() - t0
    n_old, n_new = len(old.full_decodes()), len(new.full_decodes())
    if n_new != 1:
        return False, f"shared scan made {n_new} full decode(s), want 1"
    if n_old != 2:
        return False, f"baseline made {n_old} full decodes (expected 2)"
    return True, (f"full decodes {n_old} -> {n_new}; {t_old:.2f}s -> "
                  f"{t_new:.2f}s on a 42s 1080p file "
                  f"({t_old - t_new:+.2f}s saved)")


def test_scan_fail_not_pass():
    from pipeline import dupe_check as dc
    from pipeline import film_scan as fs
    from pipeline import motion_check as mc
    f = _film()
    ff = config.ffmpeg()
    real = subprocess.run

    def broken(cmd, *a, **k):
        if "-filter_complex" in cmd:
            return subprocess.CompletedProcess(cmd, 1, b"", b"boom")
        return real(cmd, *a, **k)
    subprocess.run = broken
    try:
        sc = fs.scan(ff, f)
    finally:
        subprocess.run = real
    if sc["freezes"] is not None or sc["hashes"] is not None or sc["shared"]:
        return False, f"a failed decode still handed over results: {sc}"
    ok, probs, fz = mc.check(ff, f, {"lines": []}, scan=sc)
    if ok is not False or not fz:
        return False, ("after a failed shared decode the freeze was not "
                       "measured - a failed scan read as 'no freezes'")
    dok, _df, _di = dc.check(f, scan=sc)
    if dok is not False:
        return False, "after a failed shared decode the repeat was not found"
    return True, ("failed shared decode -> nothing handed over; both checks "
                  "measured the file themselves and still FAIL it")


def test_crop_measured():
    from pipeline import dupe_check as dc
    c = dc.content_crop(_film())
    want = "crop=1920:816:0:132"
    return c == want, f"crop {c} (want {want})"


def test_probe_memo():
    from pipeline import probe
    probe.clear_memo()
    f = _TMP / "memo.mp4"
    shutil.copy2(_film(), f)
    with _Count(str(f)) as c1:
        a = probe.pts_gaps(f, "v")
        b = probe.pts_gaps(f, "v")
        s1 = probe.streams(f)
    if a != b or len(c1.calls) != 2:
        return False, (f"second pts_gaps re-ran ffprobe "
                       f"({len(c1.calls)} calls for 2 distinct questions)")
    # rewrite with different content: must be measured again
    subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc=s=320x240:r=30:d=3", "-c:v", "libx264",
                    "-preset", "ultrafast", str(f)], capture_output=True)
    with _Count(str(f)) as c2:
        s2 = probe.streams(f)
    if len(c2.calls) != 1 or s2 == s1:
        return False, "a rewritten file was answered from memory"
    bad = _TMP / "bad.mp4"
    bad.write_bytes(b"\0" * 1000)
    with _Count(str(bad)) as c3:
        probe.streams(bad)
        probe.streams(bad)
    if len(c3.calls) != 2:
        return False, "a FAILED probe was remembered and reused"
    return True, ("unchanged file probed once per question; rewritten file "
                  "re-measured; failed probe never remembered")


def test_cache_sidecar():
    from pipeline import probe
    probe.clear_memo()
    clip = _TMP / "clip.mp4"
    cached = _TMP / "cache_sig.mp4"
    shutil.copy2(_film(), clip)
    measured = probe.streams(clip)
    shutil.copy2(clip, cached)
    probe.remember_cached(clip, cached)
    if not Path(str(cached) + ".probe.json").exists():
        return False, "no sidecar written next to the cache entry"
    hit = _TMP / "hit.mp4"
    shutil.copy2(cached, hit)
    probe.clear_memo()
    if not probe.adopt_cached(cached, hit):
        return False, "a matching sidecar was not adopted"
    with _Count(str(hit)) as c:
        got = probe.streams(hit)
    if c.calls or got != measured:
        return False, "the adopted measurement was not used, or differs"
    # tamper with the cache entry: sidecar no longer describes it
    with open(cached, "ab") as fh:
        fh.write(b"\0" * 16)
    hit2 = _TMP / "hit2.mp4"
    shutil.copy2(cached, hit2)
    probe.clear_memo()
    if probe.adopt_cached(cached, hit2):
        return False, "a sidecar was adopted for a changed cache entry"
    return True, ("cache hit adopts its stored measurement; a changed entry "
                  "is measured again")


TESTS = {
    "SCAN-IDENTICAL":     test_scan_identical,
    "SCAN-ONE-DECODE":    test_scan_one_decode,
    "SCAN-FAIL-NOT-PASS": test_scan_fail_not_pass,
    "CROP-MEASURED":      test_crop_measured,
    "PROBE-MEMO":         test_probe_memo,
    "CACHE-SIDECAR":      test_cache_sidecar,
}

if __name__ == "__main__":
    want = sys.argv[1:] or list(TESTS)
    bad = 0
    try:
        for name in want:
            fn = TESTS.get(name)
            if fn is None:
                print(f"?? no such test: {name}")
                continue
            try:
                ok, msg = fn()
            except Exception as e:
                import traceback
                traceback.print_exc()
                ok, msg = False, f"{type(e).__name__}: {e}"
            print(f'{"PASS" if ok else "FAIL"}  {name:<20} {msg}')
            bad += (not ok)
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    print("-" * 60)
    print("test_post_checks: all pass" if not bad else
          f"test_post_checks: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
