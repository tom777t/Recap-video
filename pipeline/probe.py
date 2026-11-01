"""Measure the FINISHED FILE. Nothing in here reads the plan.

WHY THIS MODULE EXISTS
----------------------
A 148 MB final.mp4 shipped with its picture frozen from 4:15 to the end -
13 minutes 19 seconds of still frame - and every gate passed. Measured
afterwards:

    video stream   255.767s   7673 frames @ 30fps
    audio stream  1054.469s
    container     1054.469s   (reports the LONGER stream, so it looked fine)

The picture was not frozen. The picture was ABSENT: the video stream ends at
4:15 and the player holds the last frame. freezedetect found nothing because
there are no frames there to compare, and the duration gates compared
`sum(clip durations) - XFADE*(n-1)` against the same expression accumulated in
a loop - both sides came from the plan, so they could not disagree.

That is the whole defect class: every check validated the PLAN and then trusted
the renderer. This module only ever opens the file.

The rule it enforces: the video stream must be as long as the audio stream, and
both must be as long as the render said they would be. A short video stream is
fatal, because it is invisible in every player until the moment it is not.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import config

# How far the two streams may disagree before it is a defect. One frame at
# 30fps is 33ms; AAC frames are 21ms. A quarter of a second is generous for
# container rounding and still 50x smaller than the smallest defect worth
# shipping.
AV_SYNC_MAX_SEC = 0.25
# A gap between consecutive video packets larger than this many frame
# intervals is a hole in the picture.
PTS_GAP_FRAMES = 3.0


# ---- one measurement per file version ---------------------------------------
# The post-render section asked the same questions of final.mp4 several times
# (pts_gaps three times, packet_count twice - each a scan of every packet in a
# 17-minute film), and the xfade assembler re-probed every clip _verify_clip
# had probed seconds earlier. The answer cannot change while the file does
# not, so it is remembered per FILE VERSION: the key holds the path, size,
# mtime, inode and device, and any rewrite of the file is a new key and a fresh
# measurement. Only successful probes of a file that did not change while it
# was being read are remembered - a failure is always re-asked, never reused.
_MEMO: dict = {}
_MEMO_MAX = 8192


def _file_key(path: str):
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (os.path.abspath(path), st.st_size, st.st_mtime_ns, st.st_ino,
            st.st_dev)


def clear_memo() -> None:
    _MEMO.clear()


def _ffprobe(*args: str) -> str:
    fk = _file_key(args[-1]) if args else None
    key = (args[:-1], fk) if fk else None
    if key is not None and key in _MEMO:
        return _MEMO[key]
    r = subprocess.run([config.ffprobe(), "-v", "error", *args],
                       capture_output=True, text=True)
    out = r.stdout or ""
    if (key is not None and r.returncode == 0
            and _file_key(args[-1]) == fk):
        if len(_MEMO) >= _MEMO_MAX:
            _MEMO.clear()
        _MEMO[key] = out
    return out


_STREAM_ARGS = ("-show_entries",
                "stream=index,codec_type,codec_name,duration,nb_frames,"
                "r_frame_rate,time_base,start_time",
                "-of", "json")


def _sidecar(cache_path: Path) -> Path:
    return Path(str(cache_path) + ".probe.json")


def remember_cached(measured: Path, cache_path: Path) -> None:
    """Store the stream measurement of a clip next to its cache entry.

    `measured` is the clip that was just verified and `cache_path` the byte
    copy of it (shutil.copy2, which keeps size and mtime). The sidecar records
    the cache file's size and mtime, so it only ever describes those bytes.
    Best effort: a missing sidecar just means the next hit measures again.
    """
    try:
        cst, mst = os.stat(cache_path), os.stat(measured)
        if (cst.st_size, cst.st_mtime_ns) != (mst.st_size, mst.st_mtime_ns):
            return
        raw = _ffprobe(*_STREAM_ARGS, str(measured))
        if not raw.strip():
            return
        _sidecar(cache_path).write_text(json.dumps(
            {"size": cst.st_size, "mtime_ns": cst.st_mtime_ns,
             "streams": raw}), encoding="utf-8")
    except (OSError, ValueError):
        pass


def adopt_cached(cache_path: Path, copy: Path) -> bool:
    """Reuse a cache entry's stored measurement for its fresh copy.

    True when the sidecar matches the cache file AND the copy (same size and
    mtime as recorded), in which case streams(copy) is answered from it.
    Anything else - no sidecar, a stale one, a copy that differs - returns
    False and the clip is measured as before.
    """
    try:
        rec = json.loads(_sidecar(cache_path).read_text(encoding="utf-8"))
        want = (int(rec["size"]), int(rec["mtime_ns"]))
        cst, kst = os.stat(cache_path), os.stat(copy)
        if (cst.st_size, cst.st_mtime_ns) != want:
            return False
        if (kst.st_size, kst.st_mtime_ns) != want:
            return False
        raw = str(rec["streams"])
        json.loads(raw)                       # must be a real probe answer
    except (OSError, ValueError, KeyError, TypeError):
        return False
    fk = _file_key(str(copy))
    if fk is None:
        return False
    _MEMO[(_STREAM_ARGS, fk)] = raw
    return True


def streams(path: Path) -> dict:
    """Per-stream facts, measured. Durations come from the STREAMS.

    The container's own `format=duration` reports the longest stream, which is
    exactly why the truncated film looked correct: its audio was full length.
    Never judge a file by the container header.
    """
    out = _ffprobe(*_STREAM_ARGS, str(path))
    try:
        raw = json.loads(out).get("streams") or []
    except (ValueError, AttributeError):
        raw = []
    res: dict = {"video": None, "audio": None, "all": []}
    for s in raw:
        fps = 0.0
        rfr = str(s.get("r_frame_rate") or "0/0")
        if "/" in rfr:
            try:
                num, den = rfr.split("/")
                fps = float(num) / float(den) if float(den) else 0.0
            except (ValueError, ZeroDivisionError):
                fps = 0.0
        rec = {
            "index": s.get("index"),
            "type": s.get("codec_type"),
            "codec": s.get("codec_name"),
            "duration": float(s.get("duration") or 0.0),
            "nb_frames": int(s.get("nb_frames") or 0),
            "fps": fps,
            "start_time": float(s.get("start_time") or 0.0),
        }
        res["all"].append(rec)
        if rec["type"] == "video" and res["video"] is None:
            res["video"] = rec
        elif rec["type"] == "audio" and res["audio"] is None:
            res["audio"] = rec
    return res


def packet_count(path: Path, kind: str = "v") -> int:
    """Count real packets. `nb_frames` is a header field and can be absent or
    wrong; this decodes the index, which is cheap and true."""
    out = _ffprobe("-select_streams", kind, "-count_packets",
                   "-show_entries", "stream=nb_read_packets",
                   "-of", "default=nw=1:nk=1", str(path))
    try:
        return int((out or "0").strip().splitlines()[0])
    except (ValueError, IndexError):
        return 0


def pts_gaps(path: Path, kind: str = "v", limit: int = 12) -> list:
    """HOLES in the presentation timeline. Returns [{at, gap}].

    SORTED FIRST, and that is the whole subtlety. ffprobe lists packets in
    DECODE order, so with B-frames the pts_time legitimately jumps forward and
    then back by a frame or two at a time. A first version of this compared
    consecutive packets in decode order and reported 900+ "backward jumps" on a
    file whose only real defect was its length - normal B-pyramid reordering
    read as corruption, which would have buried the one finding that mattered.

    What a defect actually looks like once the timestamps are sorted: a gap
    where the picture does not advance, or a duplicate timestamp. Decode order
    is irrelevant to both.
    """
    out = _ffprobe("-select_streams", kind, "-show_entries",
                   "packet=pts_time", "-of", "json", str(path))
    try:
        pkts = json.loads(out).get("packets") or []
    except (ValueError, AttributeError):
        return []
    ts = []
    for p in pkts:
        try:
            ts.append(float(p.get("pts_time")))
        except (TypeError, ValueError):
            continue
    if len(ts) < 3:
        return []
    ts.sort()
    deltas = sorted(b - a for a, b in zip(ts, ts[1:]))
    typical = deltas[len(deltas) // 2] or 0.0
    if typical <= 0:
        return []
    bad = []
    for a, b in zip(ts, ts[1:]):
        d = b - a
        if d > typical * PTS_GAP_FRAMES:
            bad.append({"at": round(a, 3), "gap": round(d, 3)})
    # Report the worst few. A thousand identical findings is not more
    # information than ten, and it hides everything else in the verdict.
    bad.sort(key=lambda r: -r["gap"])
    return bad[:limit]


def freezes(path: Path, noise_db: int | None = None,
            min_sec: float | None = None) -> list:
    """freezedetect over the WHOLE file.

    The old motion check ran this too, but only ever on a file whose video
    stream it had not measured - so on the truncated render it scanned 255s,
    found nothing, and reported the film clean. Pair this with
    `verify()`: a freeze report is only meaningful once the stream is known to
    be the right length.
    """
    noise_db = config.FREEZE_NOISE_DB if noise_db is None else noise_db
    min_sec = 0.25 if min_sec is None else min_sec
    cmd = [config.ffmpeg(), "-hide_banner", "-nostats", "-i", str(path),
           "-vf", f"freezedetect=n={noise_db}dB:d={min_sec}",
           "-map", "0:v:0", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = []
    start = None
    for ln in (r.stderr or "").splitlines():
        if "freeze_start" in ln:
            try:
                start = float(ln.rsplit(":", 1)[1].strip())
            except (ValueError, IndexError):
                start = None
        elif "freeze_duration" in ln and start is not None:
            try:
                dur = float(ln.rsplit(":", 1)[1].strip())
            except (ValueError, IndexError):
                continue
            out.append({"start": start, "end": start + dur, "dur": dur})
            start = None
    return out


def verify(path: Path, expect_dur: float | None = None,
           tol: float | None = None) -> list:
    """Independent verdict on a finished file. Returns a list of problems.

    This is the check the truncated render needed and did not have. It knows
    nothing about the draft, the timeline or the clip list; `expect_dur` is the
    only number it is told, and it is checked rather than trusted.
    """
    probs = []
    if not Path(path).exists():
        return [{"what": "missing", "msg": f"{path} does not exist"}]
    st = streams(Path(path))
    v, a = st.get("video"), st.get("audio")
    if v is None:
        probs.append({"what": "no-video", "msg": "the file has no video "
                                                 "stream at all"})
        return probs
    if a is None:
        probs.append({"what": "no-audio", "msg": "the file has no audio "
                                                 "stream at all"})

    # 1. the two streams must be the same length
    if a is not None:
        d = a["duration"] - v["duration"]
        if abs(d) > AV_SYNC_MAX_SEC:
            worse = ("the PICTURE ENDS EARLY and every player will hold the "
                     "last frame for the rest of the film"
                     if d > 0 else "the SOUND ends early")
            probs.append({
                "what": "stream-length-mismatch",
                "msg": (f"video is {v['duration']:.2f}s but audio is "
                        f"{a['duration']:.2f}s (delta {d:+.2f}s) - {worse}"),
                "video": v["duration"], "audio": a["duration"]})

    # 2. the frame count must match the video duration
    pk = packet_count(Path(path), "v")
    if pk and v["fps"] > 0:
        implied = pk / v["fps"]
        if abs(implied - v["duration"]) > max(1.0, v["duration"] * 0.02):
            probs.append({
                "what": "frame-count-mismatch",
                "msg": (f"{pk} video packets at {v['fps']:.3f}fps implies "
                        f"{implied:.2f}s but the stream claims "
                        f"{v['duration']:.2f}s")})

    # 3. both streams must be as long as the render promised
    if expect_dur and expect_dur > 0:
        tol = max(1.0, expect_dur * 0.01) if tol is None else tol
        if abs(v["duration"] - float(expect_dur)) > tol:
            probs.append({
                "what": "short-video",
                "msg": (f"the render said {float(expect_dur):.2f}s but the "
                        f"VIDEO stream is {v['duration']:.2f}s "
                        f"({v['duration'] - float(expect_dur):+.2f}s)")})
        if a is not None and abs(a["duration"] - float(expect_dur)) > tol:
            probs.append({
                "what": "short-audio",
                "msg": (f"the render said {float(expect_dur):.2f}s but the "
                        f"AUDIO stream is {a['duration']:.2f}s "
                        f"({a['duration'] - float(expect_dur):+.2f}s)")})

    # 4. the picture must advance continuously
    for g in pts_gaps(Path(path), "v"):
        probs.append({
            "what": "pts-gap",
            "msg": (f"the picture does not advance for {g['gap']:.3f}s at "
                    f"{g['at']:.3f}s")})
    return probs


def describe(path: Path) -> str:
    st = streams(Path(path))
    v, a = st.get("video"), st.get("audio")
    bits = []
    if v:
        bits.append(f"video {v['duration']:.2f}s {v['nb_frames']}f "
                    f"@{v['fps']:.2f}fps {v['codec']}")
    if a:
        bits.append(f"audio {a['duration']:.2f}s {a['codec']}")
    return " | ".join(bits) if bits else "no streams"
