"""
Join finished clips into one timeline WITHOUT re-encoding the picture.

THE OLD SHAPE, AND WHY IT WAS SLOW
`_xfade_chain` fed every clip through an `xfade` filtergraph in batches of 12,
then fed the batch results through another `xfade` pass, then the result went
through the music mix - which re-encoded the video a third and fourth time.
Measured on tokyodrift2006: 115 min for a first render, and 56 min to
re-render after editing three lines even though 104 of 107 clips came straight
from cache. The clips were never the cost. The cost was that every frame was
re-compressed four times on the way out, every time, no matter how little had
changed.

THE NEW SHAPE
A crossfade only touches 0.28 seconds either side of a junction. Everything
else is already the exact picture we want to ship. So:

    clip i:   [=== body ===][tail]
    clip i+1:                [head][=== body ===]
    output:   [=== body ===][XF][=== body ===]

Only the [XF] pieces are encoded - 0.28s each, 110 of them on this draft, so
about 31 seconds of video instead of 16 minutes, four times over. The bodies
are cut out with `-c copy` and the whole thing is joined with the concat
demuxer, also `-c copy`. The picture that lands in final.mp4 is byte-identical
to what the clip builder produced.

WHY THE CUTS ARE EXACT
A stream copy can only cut on a keyframe. So the clip builder is told to put
one exactly where the body starts and ends (`encoder.video_args(...,
keyframes_at=[...])`). That is the whole trick, and it is also the thing most
likely to go wrong silently, so every extracted piece is re-measured and a
drift over one frame is a hard failure rather than a shrug.

AUDIO IS A SEPARATE PASS
Audio still crossfades through a filtergraph, because `acrossfade` genuinely
has to resample both sides - but audio-only passes are cheap, and crucially
they no longer drag the video through an encoder with them. The per-input
`apad`/`atrim`/`asetpts` pinning is kept verbatim from the old code: it is
there because AAC priming leaked 12-18 ms per junction, and that bug does not
care which module it lives in.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rich.console import Console

import config
from pipeline import encoder as enc

console = Console()

FPS = float(config.OUTPUT_FPS)
XF_FRAMES = int(config.XFADE_FRAMES)
XFADE = XF_FRAMES / FPS
# One frame at the output rate. The tolerance for every duration assertion
# below: anything inside a frame is rounding, anything outside is a defect.
FRAME = 1.0 / FPS


def _frames(p: Path) -> int:
    """Exact frame count, by counting packets rather than trusting duration."""
    r = subprocess.run(
        [config.ffprobe(), "-v", "error", "-select_streams", "v:0",
         "-count_packets", "-show_entries", "stream=nb_read_packets",
         "-of", "default=nw=1:nk=1", str(p)],
        capture_output=True, text=True)
    try:
        return int((r.stdout or "0").strip())
    except ValueError:
        return 0


class AssemblyError(Exception):
    pass


def _run(cmd: list[str], what: str) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        console.print(f"[red]{what} failed[/]")
        console.print((r.stderr or "")[-700:])
        raise AssemblyError(what)


def _dur(p: Path, stream: str = "v:0") -> float:
    r = subprocess.run(
        [config.ffprobe(), "-v", "error", "-select_streams", stream,
         "-show_entries", "stream=duration", "-of", "default=nw=1:nk=1",
         str(p)], capture_output=True, text=True)
    try:
        return float((r.stdout or "").strip().splitlines()[0])
    except Exception:
        r2 = subprocess.run(
            [config.ffprobe(), "-v", "error", "-show_entries",
             "format=duration", "-of", "default=nw=1:nk=1", str(p)],
            capture_output=True, text=True)
        try:
            return float((r2.stdout or "").strip())
        except ValueError:
            return 0.0


def keyframe_indices(p: Path) -> set[int]:
    """Frame indices that are keyframes - by POSITION, not by timestamp.

    This reads the key_frame flag of every frame and enumerates. The obvious
    implementation - `-skip_frame nokey` and convert each pts_time to an index
    with round(t*fps) - is wrong, and wrong in a way that wasted a long
    detour: a clip written with `-ss <t> -i source` can carry a non-zero start
    PTS, so its first frame reports 0.033s rather than 0. Every index then
    comes out one too high, the keyframe at frame 8 reads as frame 9, and the
    assembler rejects a clip that was in fact built correctly. It made
    libx264 and QSV both look broken when only one of them was.

    Positions are immune to that. A clip is a few hundred frames, so reading
    every flag costs nothing.
    """
    r = subprocess.run(
        [config.ffprobe(), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "frame=key_frame", "-of", "csv=p=0", str(p)],
        capture_output=True, text=True)
    out: set[int] = set()
    for i, line in enumerate(
            l for l in (r.stdout or "").splitlines() if l.strip()):
        if line.strip().rstrip(",") == "1":
            out.add(i)
    return out


def body_window(i: int, n: int, dur: float) -> tuple[float, float]:
    """Which part of clip i survives as a stream-copied body.

    The first clip keeps its head (nothing fades into it) and the last keeps
    its tail (nothing fades out of it). Everything else loses XFADE at both
    ends to the two crossfades it takes part in.
    """
    start = 0.0 if i == 0 else XFADE
    end = dur if i == n - 1 else dur - XFADE
    return start, end


def keyframes_for(i: int, n: int, dur: float) -> list[float]:
    """Where clip i must carry forced keyframes for an exact copy-cut."""
    start, end = body_window(i, n, dur)
    ks = []
    if start > 0.0:
        ks.append(round(start, 3))
    if end < dur - 1e-6:
        ks.append(round(end, 3))
    return ks


# --------------------------------------------------------------------------- #
# Video: copy the bodies, encode only the crossfades
# --------------------------------------------------------------------------- #
def _extract_body(ff: str, src: Path, start_frame: int, n_frames: int,
                  out: Path) -> int:
    """Copy exactly `n_frames` frames starting at `start_frame`.

    COUNTED IN FRAMES, NOT SECONDS, and that is the whole point. The first
    attempt used `-t <seconds>` with `-c copy` and asked for 2.720s; it
    produced 2.800s, because a stream copy emits whole packets and `-t` keeps
    any packet that starts before the limit. 0.080s of slop per piece is
    nearly nine seconds across 110 junctions, all of it desync against an
    audio track built from the planned numbers.

    `-frames:v N` is exact under `-c copy`: it emits N packets and stops.
    Combined with a forced keyframe at `start_frame`, the cut is correct at
    both ends with no arithmetic left to round.
    """
    # -ss BEFORE -i is an input seek; with -c copy it lands on the nearest
    # preceding keyframe, which is exact only because the clip was encoded
    # with a forced keyframe at this frame.
    _run([ff, "-y", "-hide_banner", "-loglevel", "error",
          "-ss", f"{start_frame / FPS:.6f}", "-i", str(src),
          "-frames:v", str(n_frames),
          "-an", "-c:v", "copy", "-avoid_negative_ts", "make_zero",
          str(out)], f"body copy of {src.name}")
    return _frames(out)


def _build_transition(ff: str, a: Path, a_dur: float, b: Path,
                      out: Path) -> float:
    """Encode just the 0.28s dissolve from the tail of a into the head of b."""
    a_from = max(0.0, a_dur - XFADE)
    graph = (f"[0:v]trim=start={a_from:.3f}:duration={XFADE:.3f},"
             f"setpts=PTS-STARTPTS[xa];"
             f"[1:v]trim=duration={XFADE:.3f},setpts=PTS-STARTPTS[xb];"
             f"[xa][xb]xfade=transition=fade:duration={XFADE:.3f}:offset=0[v]")
    _run([ff, "-y", "-hide_banner", "-loglevel", "error",
          "-i", str(a), "-i", str(b),
          "-filter_complex", graph, "-map", "[v]", "-an",
          # EXACTLY XF_FRAMES frames, counted - not `-t XFADE` seconds.
          # `-t 0.267` produced NINE frames, because xfade emits the frame at
          # the closing endpoint as well. One extra frame per junction is
          # invisible in a single transition and became 106 frames - 3.5
          # seconds of picture against sound - across the film. It survived
          # because the check below allowed +/-1 frame; a tolerance wide
          # enough to absorb a systematic error will absorb it every time.
          "-frames:v", str(XF_FRAMES),
          # No forced keyframes: a transition is never copy-cut, it is used
          # whole, and forcing an IDR inside 8 frames only costs bitrate.
          *enc.video_args("transition"),
          str(out)], f"transition {a.name}->{b.name}")
    return _dur(out)


def build_video(ff: str, clips: list[tuple[Path, float]], work: Path,
                out: Path) -> float:
    """Stream-copy the bodies, encode the junctions, concat the lot."""
    n = len(clips)
    if n == 0:
        raise AssemblyError("no clips to assemble")
    pieces_dir = work / "_asm"
    pieces_dir.mkdir(parents=True, exist_ok=True)

    order: list[Path] = []
    planned_frames = 0
    n_short = 0

    for i, (p, d) in enumerate(clips):
        # Everything below is in FRAMES, taken from the clip's actual packet
        # count rather than its nominal duration, so nothing has to be rounded
        # twice.
        total_f = _frames(p)
        head_f = 0 if i == 0 else XF_FRAMES
        tail_f = 0 if i == n - 1 else XF_FRAMES
        body_f = total_f - head_f - tail_f
        if body_f <= 0:
            # A clip shorter than its two crossfades has no body at all. It
            # would vanish, so say so rather than silently dropping a line.
            n_short += 1
            console.print(f"[yellow]  clip {p.name} is {total_f} frames, "
                          f"shorter than the {head_f+tail_f} its crossfades "
                          f"need - it contributes no body.[/]")
        else:
            # PRECONDITION, checked before copying rather than inferred after.
            # `-frames:v N` guarantees the COUNT, not the START: with no
            # keyframe at head_f the input seek silently lands on frame 0 and
            # copies N frames from the wrong place. The count check passes and
            # the picture is wrong. Found by this module's own negative
            # control, which is the only reason it is checked at all.
            if head_f > 0:
                kfs = keyframe_indices(p)
                if head_f not in kfs:
                    near = sorted(kfs)[:6]
                    raise AssemblyError(
                        f"{p.name} has no keyframe at frame {head_f} "
                        f"({head_f/FPS:.3f}s), so a stream copy cannot start "
                        f"there - it would silently begin at the previous "
                        f"keyframe and the picture would be offset. "
                        f"Keyframes present: {near}... "
                        f"The clip must be encoded with "
                        f"-force_key_frames at that point "
                        f"(render._body_keyframes).")
            bp = pieces_dir / f"body_{i:04d}.mp4"
            got_f = _extract_body(ff, p, head_f, body_f, bp)
            if got_f != body_f:
                raise AssemblyError(
                    f"body copy of {p.name} asked for {body_f} frames and got "
                    f"{got_f}, so the copy-cut is not exact.")
            order.append(bp)
            planned_frames += body_f

        if i < n - 1:
            tp = pieces_dir / f"xf_{i:04d}.mp4"
            _build_transition(ff, p, d, clips[i + 1][0], tp)
            got_f = _frames(tp)
            # EXACT. No tolerance: a transition is produced by `-frames:v`,
            # so it either has the frames asked for or something is wrong.
            if got_f != XF_FRAMES:
                raise AssemblyError(
                    f"transition {i} is {got_f} frames, expected exactly "
                    f"{XF_FRAMES}. Every junction shares this error, so it "
                    f"multiplies by the number of clips.")
            order.append(tp)
            planned_frames += got_f

    console.print(f"  [dim]{len(order)} pieces: "
                  f"{sum(1 for p in order if p.name.startswith('body'))} "
                  f"stream-copied bodies + "
                  f"{sum(1 for p in order if p.name.startswith('xf'))} "
                  f"encoded crossfades "
                  f"({XFADE*(n-1):.1f}s of video encoded, not "
                  f"{planned_frames/FPS/60:.1f} min)[/]")
    if n_short:
        console.print(f"[yellow]  {n_short} clip(s) had no body.[/]")

    lst = pieces_dir / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in order),
                   encoding="utf-8")
    _run([ff, "-y", "-hide_banner", "-loglevel", "error",
          "-f", "concat", "-safe", "0", "-i", str(lst),
          "-c", "copy", "-fflags", "+genpts", str(out)],
         "video concat (stream copy)")

    # Frame-exact check first: the concat must contain exactly the frames we
    # handed it. A duration comparison can hide a lost frame inside rounding.
    got_f = _frames(out)
    if got_f != planned_frames:
        raise AssemblyError(
            f"assembled video has {got_f} frames but {planned_frames} were "
            f"written into the concat list (off by {got_f-planned_frames}). "
            f"The demuxer dropped or duplicated pieces.")
    got = _dur(out)
    console.print(f"  [dim]{got_f} frames = {got_f/FPS:.3f}s at {FPS:.0f}fps, "
                  f"container reports {got:.3f}s[/]")
    return got_f / FPS


# --------------------------------------------------------------------------- #
# Audio: its own pass, crossfaded, no video anywhere near it
# --------------------------------------------------------------------------- #
def _audio_batch(ff: str, clips: list[tuple[Path, float]], out: Path) -> float:
    ins: list[str] = []
    for p, _ in clips:
        ins += ["-i", str(p)]
    pre = []
    for i, (_, d) in enumerate(clips):
        # Verbatim from the old _xfade_single: pin every input to its measured
        # length before it is faded, because AAC decode priming leaked 12-18ms
        # per junction and compounded across the film.
        pre.append(f"[{i}:a]apad=whole_dur={d:.3f},atrim=0:{d:.3f},"
                   f"asetpts=PTS-STARTPTS[at{i}]")
    chain = []
    prev = "at0"
    for i in range(1, len(clips)):
        lab = f"ax{i}"
        chain.append(f"[{prev}][at{i}]acrossfade=d={XFADE:.3f}[{lab}]")
        prev = lab
    graph = ";".join(pre + chain) if chain else ";".join(pre)
    _run([ff, "-y", "-hide_banner", "-loglevel", "error", *ins,
          "-filter_complex", graph, "-map", f"[{prev}]", "-vn",
          # PCM: this is an intermediate and the final mix re-encodes once.
          # Another AAC generation here would be free loss.
          "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(out)],
         "audio crossfade pass")
    return _dur(out, "a:0")


def build_audio(ff: str, clips: list[tuple[Path, float]], work: Path,
                out: Path) -> float:
    """One crossfaded audio track for the whole timeline.

    Batched at 12 like the old code - not for encode cost, which is trivial
    now, but because a 111-input filtergraph is a memory and command-line
    risk that nobody needs to take.
    """
    BATCH = 12
    if len(clips) <= BATCH:
        return _audio_batch(ff, clips, out)
    tmp = work / "_asm"
    tmp.mkdir(parents=True, exist_ok=True)
    parts: list[tuple[Path, float]] = []
    for bi in range(0, len(clips), BATCH):
        chunk = clips[bi:bi + BATCH]
        bp = tmp / f"aud_{bi//BATCH:03d}.wav"
        d = _audio_batch(ff, chunk, bp)
        parts.append((bp, d))
    return _audio_batch(ff, parts, out)


# --------------------------------------------------------------------------- #
# Both, muxed
# --------------------------------------------------------------------------- #
def build(ff: str, clips: list[tuple[Path, float]], work: Path,
          out: Path) -> float:
    """Produce `out` with a stream-copied picture and a crossfaded soundtrack.

    Returns the measured video duration, which is what the rest of render.py
    treats as the timeline length.
    """
    console.print(f"[cyan]Assembling {len(clips)} clips[/] "
                  f"[dim](bodies stream-copied, only the "
                  f"{XFADE:.2f}s crossfades encoded)[/]")

    # ONE SOURCE OF TRUTH FOR EACH CLIP'S LENGTH.
    # The caller's durations are the clip builder's intended `clip_len`. The
    # encoder does not always produce exactly that many frames - `-t 3.000` at
    # 30fps can yield 91 frames, not 90. The video assembly works in measured
    # frames, so when the audio pass worked from the caller's nominal numbers
    # instead, the two drifted by about one frame per junction: on this draft
    # the picture came out 900.067s against 896.423s of sound, a 3.644s split
    # that grew with every clip. Caught by the agreement check below, which is
    # the only reason it was not shipped.
    #
    # So the frame count is measured ONCE here and both routes are handed the
    # same numbers. They now agree by construction rather than by coincidence.
    exact: list[tuple[Path, float]] = []
    for p, _nominal in clips:
        exact.append((p, _frames(p) / FPS))

    vid = work / "_asm_video.mp4"
    aud = work / "_asm_audio.wav"
    v_dur = build_video(ff, exact, work, vid)
    a_dur = build_audio(ff, exact, work, aud)

    if abs(v_dur - a_dur) > 0.25:
        raise AssemblyError(
            f"picture is {v_dur:.3f}s but sound is {a_dur:.3f}s "
            f"(off by {a_dur-v_dur:+.3f}s). These are built by two different "
            f"routes now, so they are checked against each other rather than "
            f"assumed to agree.")

    # THE PICTURE IS AUTHORITATIVE. It is frame-exact by construction - every
    # piece was counted, not timed - whereas the audio length is whatever
    # acrossfade arithmetic produced from the clips' audio streams, which can
    # differ from their video streams by a frame or two each.
    #
    # `-shortest` was wrong here and the self-test caught it: audio came out
    # 0.067s short, so -shortest threw away 3 frames of finished picture. On
    # 107 clips that error is free to accumulate. Padding the audio and
    # cutting at the video's own duration means the sound follows the picture
    # instead of truncating it.
    _run([ff, "-y", "-hide_banner", "-loglevel", "error",
          "-i", str(vid), "-i", str(aud),
          "-map", "0:v:0", "-map", "1:a:0",
          "-af", "apad", "-t", f"{v_dur:.6f}",
          "-c:v", "copy", *enc.audio_args(), str(out)],
         "mux assembled video + audio")
    final_dur = _dur(out)
    got_f = _frames(out)
    want_f = int(round(v_dur * FPS))
    if abs(got_f - want_f) > 1:
        raise AssemblyError(
            f"the mux changed the frame count: {want_f} in, {got_f} out "
            f"(off by {got_f-want_f}). A stream copy must not lose frames.")
    console.print(f"  [dim]picture {v_dur:.3f}s ({want_f}f) / sound "
                  f"{a_dur:.3f}s padded to match / muxed {final_dur:.3f}s "
                  f"({got_f}f)[/]")
    return v_dur


# --------------------------------------------------------------------------- #
# Self-test
# --------------------------------------------------------------------------- #
def selftest() -> int:
    """Build real clips, assemble them, and check the result by measurement.

    Runs against actual ffmpeg rather than mocks, because every failure this
    is guarding against - a missing forced keyframe, an inexact copy-cut, a
    concat that silently drops a piece - only exists at the bitstream level.
    """
    import tempfile
    fails: list[str] = []

    def chk(name, cond, detail=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {name}"
              + (f"   {detail}" if detail and not cond else ""))
        if not cond:
            fails.append(name)

    ff = config.ffmpeg()
    print(f"\nassemble selftest - {enc.describe()}")
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        durs = [3.0, 2.0, 4.0]
        clips: list[tuple[Path, float]] = []
        for i, d in enumerate(durs):
            p = work / f"c{i}.mp4"
            # Frame-number forcing, exactly as the real clip builder does it.
            # See encoder.video_args for why a timestamp does not work.
            expr = "+".join("eq(n,%d)" % int(x) for x in [XF_FRAMES])
            _run([ff, "-y", "-hide_banner", "-loglevel", "error",
                  "-f", "lavfi", "-i",
                  f"testsrc2=s=640x360:r={config.OUTPUT_FPS}:d={d}",
                  "-f", "lavfi", "-i",
                  f"sine=frequency={220*(i+1)}:r=48000:d={d}",
                  "-t", f"{d:.3f}",
                  "-force_key_frames", f"expr:{expr}",
                  "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                  "-pix_fmt", "yuv420p",
                  "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                  str(p)], f"test clip {i}")
            clips.append((p, _dur(p)))

        print("\n[1] the xfade identity holds")
        expect = sum(d for _, d in clips) - XFADE * (len(clips) - 1)
        out = work / "asm.mp4"
        got = build(ff, clips, work, out)
        # Tolerance is 2 frames, not 0: `-t 3.0` at 30fps does not always
        # yield exactly 90 frames, so the nominal durations this expectation
        # is built from are themselves approximate. The assembler works off
        # MEASURED frame counts, which is why its own internal check is exact
        # and this one is not.
        chk(f"assembled length {got:.3f}s == expected {expect:.3f}s",
            abs(got - expect) <= 2 * FRAME + 1e-6,
            f"drift {got-expect:+.3f}s, over {2*FRAME:.3f}s")

        print("\n[2] no frame is lost between assembly and the muxed file")
        # build() now asserts this internally, so reaching here at all means
        # the copy preserved every frame. Re-check independently rather than
        # trusting the thing under test.
        frames = _frames(out)
        want_frames = int(round(got * FPS))
        chk(f"muxed file has {frames} frames, expected {want_frames}",
            abs(frames - want_frames) <= 1, f"off by {frames-want_frames}")

        print("\n[3] picture and sound agree")
        v = _dur(out, "v:0")
        a = _dur(out, "a:0")
        chk(f"video {v:.3f}s vs audio {a:.3f}s within 0.25s",
            abs(v - a) < 0.25, f"off by {a-v:+.3f}s")

        print("\n[4] a missing forced keyframe is CAUGHT, not absorbed")
        # Negative control: encode a clip with NO forced keyframes and a long
        # GOP, so the copy-cut cannot land where the assembler needs it. The
        # body extraction must notice.
        bad = work / "bad.mp4"
        _run([ff, "-y", "-hide_banner", "-loglevel", "error",
              "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=6",
              "-f", "lavfi", "-i", "sine=frequency=330:r=48000:d=6",
              "-t", "6.0", "-g", "300", "-keyint_min", "300",
              "-sc_threshold", "0",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
              "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
              str(bad)], "bad clip")
        # Two clips, so `bad` is the FIRST and keeps its head - the cut that
        # needs a keyframe is at its TAIL. Put it second instead, where the
        # body starts at frame 8 and there is no keyframe within 300 frames.
        raised = False
        try:
            build_video(ff, [(clips[0][0], clips[0][1]), (bad, 6.0)],
                        work / "nc", work / "nc.mp4")
        except AssemblyError as e:
            raised = "no keyframe at frame" in str(e)
        except Exception:
            raised = False
        chk("a clip with no forced keyframe is REJECTED, not absorbed",
            raised)

        print("\n[5] the positive half: a properly built clip HAS the keyframe")
        kf = keyframe_indices(clips[1][0])
        chk(f"forced keyframe at frame {XF_FRAMES} is present {sorted(kf)[:5]}",
            XF_FRAMES in kf)

    print("\n" + "=" * 56)
    if fails:
        print(f"RESULT: {len(fails)} FAILURE(S)")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("RESULT: ALL SELF-TESTS PASS")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(selftest())
