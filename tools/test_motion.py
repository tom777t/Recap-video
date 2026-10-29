"""Frozen / slow / repeated footage regression tests.

THE DEFECTS, all visible in the Tokyo Drift render and all permitted:
  * a bound shot could be stretched to 1.40x (setpts frame duplication, so it
    reads as judder, not slow motion)
  * `tpad=stop_mode=clone` had stop_duration set to the whole clip length, i.e.
    no ceiling - a short window under a long line became a still image
  * nothing stopped two lines binding overlapping footage

Cases
-----
  SLOWDOWN-CAPPED      BINDING_SLOWDOWN_MAX is 1.15 and schemas reads it from
                       config, so the ceiling is tunable in one place
  FREEZE-CAPPED        no tpad in render.py can clone for longer than
                       config.MAX_FREEZE_SEC. Asserted against the SOURCE, so a
                       new uncapped tpad fails here rather than in a render.
  FREEZE-DETECTED      a real frozen video is found by freezedetect with the
                       right duration; a moving one is not flagged. Built with
                       ffmpeg, not mocked.
  FREEZE-FATAL         the threshold relationship holds: anything over
                       FREEZE_FAIL_SEC fails, and the detector's own minimum is
                       below that so near-misses are still visible
  REUSE-DETECTED       two lines on overlapping footage are caught; abutting
                       windows and a line's own sub-windows are not
  REUSE-USES-SHOWN     the check prefers what the render actually showed over
                       the declared windows - a hold plays PAST its window, so
                       judging declared windows misses the overlap it creates
  HOLD-WINDOW-HONEST   _build_silence_clip ignores its `end` argument, so the
                       footage a hold shows is [start, start+clip_len). The
                       render must record that, not the declared window.
  MULTI-SHOT-EXTENSION fit_narration may extend a window across a cut into the
                       following shots, bounded by the next bound line, a
                       reveal landing and the source duration.

Run:  python tools/test_motion.py
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402

TMP = Path(ROOT) / "_mtest"


def _ff(*args) -> None:
    r = subprocess.run([config.ffmpeg(), "-y", "-hide_banner",
                        "-loglevel", "error", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg: {(r.stderr or '')[-300:]}")


def test_slowdown_capped() -> tuple[bool, str]:
    from pipeline.schemas import BINDING_SLOWDOWN_MAX
    want = 1.15
    if abs(float(config.BINDING_SLOWDOWN_MAX) - want) > 1e-9:
        return False, (f"config.BINDING_SLOWDOWN_MAX is "
                       f"{config.BINDING_SLOWDOWN_MAX}, expected {want}")
    if abs(float(BINDING_SLOWDOWN_MAX) - float(config.BINDING_SLOWDOWN_MAX)) > 1e-9:
        return False, ("schemas.BINDING_SLOWDOWN_MAX does not track the config "
                       "value - the ceiling exists in two places")
    return True, (f"slow-motion ceiling is {want}x and schemas reads it from "
                  f"config")


def test_freeze_capped() -> tuple[bool, str]:
    """No tpad may clone for longer than MAX_FREEZE_SEC."""
    # EVERY module that builds a tpad, not just render.py. The four frozen
    # stretches in the finished Tokyo Drift intro were all built by intro.py,
    # whose tpad this test never looked at because it only read render.py -
    # so the cap was enforced in the one file that already had it.
    bad = []
    spots = []
    for mod in ("render.py", "intro.py"):
        src = io.open(os.path.join(ROOT, "pipeline", mod),
                      encoding="utf-8").read()
        # Look at a WINDOW after each occurrence, not to the end of the line:
        # the cap is often on the following physical line because these are
        # wrapped f-strings, and a line-bounded regex reported every capped
        # tpad as bare.
        here = [m.start() for m in
                re.finditer(r"tpad=stop_mode=clone:stop_duration=", src)]
        spots += [(mod, i) for i in here]
        for i in here:
            window = src[i:i + 160]
            if "MAX_FREEZE_SEC" not in window and "_freeze_cap" not in window:
                line_no = src[:i].count("\n") + 1
                bad.append(f"{mod}:{line_no}")
    if not spots:
        return False, "found no tpad clone filters to check at all"
    if bad:
        return False, (f"{len(bad)} tpad(s) clone without the "
                       f"MAX_FREEZE_SEC cap at {bad}")
    if float(config.MAX_FREEZE_SEC) > 0.5:
        return False, (f"MAX_FREEZE_SEC is {config.MAX_FREEZE_SEC}, which is "
                       f"not below the {config.FREEZE_FAIL_SEC}s failure "
                       f"threshold")
    return True, (f"all {len(spots)} tpad clone(s) are capped at "
                  f"MAX_FREEZE_SEC ({config.MAX_FREEZE_SEC}s)")


def test_freeze_detected() -> tuple[bool, str]:
    """A really frozen video is found; a moving one is not."""
    from pipeline import motion_check as mc
    ff = config.ffmpeg()
    TMP.mkdir(parents=True, exist_ok=True)
    try:
        # 1s moving, 2s frozen, 1s moving
        moving = TMP / "mv.mp4"
        _ff("-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=4",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(moving))
        frozen = TMP / "fz.mp4"
        # hold a single frame for 2s in the middle using a still + concat
        still = TMP / "still.mp4"
        _ff("-f", "lavfi", "-i", "color=c=navy:size=320x180:rate=30:duration=2",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(still))
        lst = TMP / "l.txt"
        lst.write_text(f"file '{moving.as_posix()}'\n"
                       f"file '{still.as_posix()}'\n"
                       f"file '{moving.as_posix()}'\n", encoding="utf-8")
        _ff("-f", "concat", "-safe", "0", "-i", str(lst),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(frozen))

        fz = mc.freezes(ff, frozen)
        if not fz:
            return False, "a 2s frozen stretch was not detected"
        longest = max(f["dur"] for f in fz)
        if longest < 1.0:
            return False, (f"the 2s freeze was detected as only "
                           f"{longest:.2f}s - the duration is being misread")
        clean = mc.freezes(ff, moving)
        if clean:
            return False, (f"moving footage was reported as frozen: {clean}")
        return True, (f"a 2s freeze is detected ({longest:.2f}s found at "
                      f"{fz[0]['start']:.2f}s); moving footage is not flagged")
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


def test_freeze_fatal() -> tuple[bool, str]:
    """The thresholds must be ordered so near-misses are visible."""
    if float(config.MAX_FREEZE_SEC) >= float(config.FREEZE_FAIL_SEC):
        return False, (f"MAX_FREEZE_SEC ({config.MAX_FREEZE_SEC}) is not below "
                       f"FREEZE_FAIL_SEC ({config.FREEZE_FAIL_SEC}) - the build "
                       f"rule permits what the check fails")
    # the detector's own minimum must be under the failure threshold, or a
    # near-miss is invisible and the report can only ever say "fail"
    if float(config.FREEZE_FAIL_SEC) / 2.0 >= float(config.FREEZE_FAIL_SEC):
        return False, "detector minimum is not below the failure threshold"
    return True, (f"clone cap {config.MAX_FREEZE_SEC}s < fail threshold "
                  f"{config.FREEZE_FAIL_SEC}s, and the detector reports from "
                  f"{config.FREEZE_FAIL_SEC/2:.2f}s so near-misses show")


def test_reuse_detected() -> tuple[bool, str]:
    from pipeline import motion_check as mc
    ov = float(config.FOOTAGE_REUSE_MIN_OVERLAP_SEC)
    # clear overlap
    draft = {"lines": [
        {"id": 1, "clip_start": "00:00:10.000", "clip_end": "00:00:20.000"},
        {"id": 2, "clip_start": "00:00:15.000", "clip_end": "00:00:25.000"},
    ]}
    hits = mc.reuse(draft)
    if len(hits) != 1 or abs(hits[0]["overlap"] - 5.0) > 0.01:
        return False, f"a 5s overlap was not reported correctly: {hits}"
    # abutting windows are NOT reuse
    abut = {"lines": [
        {"id": 1, "clip_start": "00:00:10.000", "clip_end": "00:00:20.000"},
        {"id": 2, "clip_start": "00:00:20.000", "clip_end": "00:00:30.000"},
    ]}
    if mc.reuse(abut):
        return False, "abutting windows were reported as reuse"
    # a frame or two of touch is not reuse either
    touch = {"lines": [
        {"id": 1, "clip_start": "00:00:10.000", "clip_end": "00:00:20.000"},
        {"id": 2, "clip_start": f"00:00:{20 - ov/2:.3f}",
         "clip_end": "00:00:30.000"},
    ]}
    if mc.reuse(touch):
        return False, (f"a {ov/2:.2f}s touch (under the {ov:.2f}s threshold) "
                       f"was reported as reuse")
    # a line's own montage sub-windows are not reuse with itself
    own = {"lines": [
        {"id": 1, "clip_start": "00:00:10.000", "clip_end": "00:00:20.000",
         "montage": [{"clip_start": "00:00:10.000", "clip_end": "00:00:15.000"},
                     {"clip_start": "00:00:15.000", "clip_end": "00:00:20.000"}]},
    ]}
    if mc.reuse(own):
        return False, "a line's own sub-windows were reported as reuse"
    return True, ("a 5s overlap is caught; abutting windows, sub-threshold "
                  "touches and a line's own sub-windows are not")


def test_reuse_uses_shown() -> tuple[bool, str]:
    """What the render SHOWED beats what the draft declared.

    A hold ignores its declared window end and keeps playing, so two lines can
    overlap on screen while their declared windows do not.
    """
    from pipeline import motion_check as mc
    # declared windows do NOT overlap...
    draft = {"lines": [
        {"id": 1, "clip_start": "00:00:10.000", "clip_end": "00:00:12.000",
         "narration": "", "narration_silence_seconds": 8.0},
        {"id": 2, "clip_start": "00:00:14.000", "clip_end": "00:00:20.000"},
    ]}
    if mc.reuse(draft):
        return False, "declared windows do not overlap but were flagged"
    # ...but the hold actually played 10.0 -> 18.0, which does overlap line 2
    shown = [{"line_id": 1, "a": 10.0, "b": 18.0, "source": "hold"},
             {"line_id": 2, "a": 14.0, "b": 20.0, "source": "clip"}]
    hits = mc.reuse(draft, shown=shown)
    if not hits:
        return False, ("the overlap the hold actually created on screen was "
                       "missed - the check is reading declared windows")
    return True, (f"the hold's real {shown[0]['b']-shown[0]['a']:.0f}s of "
                  f"footage overlaps line 2 by {hits[0]['overlap']:.0f}s and "
                  f"is caught, though the declared windows do not overlap")


def test_hold_window_honest() -> tuple[bool, str]:
    """render must record a hold's REAL footage span, not its declared one."""
    src = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                  encoding="utf-8").read()
    if "_hold_end" not in src:
        return False, ("render.py records a hold's declared window; "
                       "_build_silence_clip ignores `end` and plays clip_len "
                       "seconds from `start`, so footage past the window is "
                       "unchecked by the censor audit and the reuse check")
    # and the builder genuinely does ignore `end`
    i = src.find("def _build_silence_clip")
    j = src.find("\ndef ", i + 10)
    body = src[i:j]
    if '"-t", f"{clip_len' not in body:
        return False, ("_build_silence_clip no longer reads clip_len seconds - "
                       "re-check what a hold actually shows")
    return True, ("a hold's recorded footage span is "
                  "[start, start+clip_len), which is what it really shows")


def test_multi_shot_extension() -> tuple[bool, str]:
    """A window may extend across a cut, bounded by the next bound line."""
    src = io.open(os.path.join(ROOT, "tools", "fit_narration.py"),
                  encoding="utf-8").read()
    if "MULTI-SHOT EXTENSION" not in src:
        return False, ("tools/fit_narration.py does not document the "
                       "multi-shot extension - it may still be clamping to "
                       "the host shot, whose only alternative is slow-motion")
    # the limit must come from the next bound line, not the host shot end
    if "limit = max(he, max(m[\"b\"] for m in members))" not in src:
        return False, "the extension limit is not derived as expected"
    for guard in ("lands", "src_dur"):
        if guard not in src:
            return False, f"the extension is not bounded by {guard}"
    return True, ("a window extends across cuts to the next bound line, "
                  "bounded by reveal landings and the source duration")


def test_static_source_excused() -> tuple[bool, str]:
    """A shot the FILM holds still must not be reported as a render freeze.

    freezedetect on the finished file cannot tell the two apart:
      * the render froze the picture        - a defect
      * the film is holding a static shot   - a shot
    Locked-off establishing shots, held close-ups and title cards are all
    legitimate, and flagging them produced findings with nothing to fix. A
    freeze counts only where the SOURCE moved over the same span.
    """
    from pipeline import motion_check as mc
    ff = config.ffmpeg()
    TMP.mkdir(parents=True, exist_ok=True)
    try:
        # A genuinely STATIC source: a single colour, 4s. Nothing moves.
        static = TMP / "static_src.mp4"
        _ff("-f", "lavfi", "-i", "color=c=navy:size=320x180:rate=30:duration=4",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(static))
        # A MOVING source of the same length.
        moving = TMP / "moving_src.mp4"
        _ff("-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=4",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(moving))

        if mc.source_has_motion(ff, static, 0.5, 3.5) is not False:
            return False, ("a single-colour source was reported as moving, so "
                           "a held shot would still be flagged")
        if mc.source_has_motion(ff, moving, 0.5, 3.5) is not True:
            return False, "a testsrc source was not reported as moving"
        if mc.source_has_motion(ff, TMP / "nope.mp4", 0.0, 1.0) is not None:
            return False, ("an unreadable source returned a verdict instead "
                           "of None - an unknown answer must not read as "
                           "'static', which would suppress real freezes")

        # ---- end to end: the same freeze, excused or not by its source ----
        # A finished file that is frozen for 2s in the middle.
        frozen_final = TMP / "final.mp4"
        lst = TMP / "l.txt"
        lst.write_text(f"file '{moving.as_posix()}'\n"
                       f"file '{static.as_posix()}'\n"
                       f"file '{moving.as_posix()}'\n", encoding="utf-8")
        _ff("-f", "concat", "-safe", "0", "-i", str(lst),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(frozen_final))
        # the frozen stretch sits at 4-8s in the finished file, and came from
        # 0-4s of whichever source we claim
        shown = [{"a": 0.0, "b": 4.0, "out_a": 4.0, "out_b": 8.0,
                  "source": "clip", "line_id": 1, "blurred": False}]
        draft = {"lines": [{"id": 1, "clip_start": "00:00:00.000",
                            "clip_end": "00:00:04.000"}]}

        ok_static, bad_static = mc.check(ff, frozen_final, draft, shown=shown,
                                         source=static)
        if not ok_static:
            return False, (f"the freeze was reported even though its SOURCE "
                           f"span is static: {bad_static}")
        ok_moving, bad_moving = mc.check(ff, frozen_final, draft, shown=shown,
                                        source=moving)
        if ok_moving:
            return False, ("a freeze whose source MOVES was not reported - the "
                           "check now excuses everything")
        if not any("SOURCE moves" in b for b in bad_moving):
            return False, f"the finding does not explain itself: {bad_moving}"
        return True, ("a static source excuses the freeze; a moving source "
                      "still fails it; an unreadable source is reported, not "
                      "excused")
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


def test_bump_never_compounds() -> tuple[bool, str]:
    """A rate_bump is ABSOLUTE. Re-fitting must not multiply onto the old one.

    fit_narration used to write `cur * mult`, so two passes took 1.08 to 1.188
    and three took line 86 to 1.283 - all outside the +-10% voice band that
    every delivery tag respects. Every individual decision looked right; it
    was the ACCUMULATION that broke the one-narrator contract, which is why
    this is an invariant and not a code review.
    """
    src = io.open(os.path.join(ROOT, "tools", "fit_narration.py"),
                  encoding="utf-8").read()
    # Search CODE only. The comment above the fix quotes the old expression
    # verbatim so the bug is documented where it happened, and a naive
    # substring search flagged that comment as the bug itself.
    code = "\n".join(l for l in src.splitlines()
                     if not l.lstrip().startswith("#"))
    for bad in ("cur * mult", "cur * a.max_bump"):
        if bad in code:
            return False, (f"fit_narration still compounds bumps ({bad!r}) - "
                           f"a re-fit will push lines outside the voice band")
    if "old_bumps" not in src:
        return False, ("fit_narration does not reset previous bumps before "
                       "re-fitting, so it cannot be starting from the base rate")
    if "bump_in_band" not in src:
        return False, ("fit_narration does not assert the band invariant after "
                       "planning - an accumulation would go unnoticed again")
    # the un-scaling of a previous bump must exist, or resetting throws away
    # the measurement instead of correcting it
    if "UN-SCALE" not in src:
        return False, ("a reset discards the measured audio instead of "
                       "dividing the old bump back out of it")
    # and the shipped draft must satisfy the band
    from pipeline import voice_check as vc
    p = Path(config.project_dir("tokyodrift2006")) / "draft.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        out = [(l["id"], float(l["rate_bump"])) for l in d["lines"]
               if l.get("rate_bump") and not vc.bump_in_band(l["rate_bump"])]
        if out:
            return False, f"the shipped draft has out-of-band bumps: {out}"
    return True, (f"bumps are absolute, previous ones are reset and un-scaled, "
                  f"and the band invariant is asserted; the shipped draft is "
                  f"inside +-{config.VOICE_RATE_BAND:.0%}")


def test_multi_shot_before_trim() -> tuple[bool, str]:
    """Free adjacent footage must be taken BEFORE rate bumps and trims.

    The widener only ever grew a window inside its HOST SHOT, because the reach
    limit was `max(host_end, ...)` and then only ever reduced - so it could
    never exceed the host shot's end. Everything it could not fix went straight
    to a rate bump or the trim worklist while 71 minutes of unused footage sat
    in 75 gaps across the film.
    """
    src = io.open(os.path.join(ROOT, "tools", "fit_narration.py"),
                  encoding="utf-8").read()
    if "def plan_extend" not in src:
        return False, "there is no multi-shot extension stage"
    # the reach limit must be able to GROW to the next bound line
    if "limit = max(limit, r[\"a\"])" not in src:
        return False, ("the reach limit cannot exceed the host shot - it is "
                       "being min()-ed downward only, which is the original bug")
    # order: extension must be planned before the rate bump / trim loop
    i_ext = src.find("plan_extend(draft")
    i_rate = src.find("bounded rate bump")
    i_merge = src.find("plan_merge_short(draft")
    i_trim = src.find("the text is the problem")
    for nm, idx in (("plan_extend", i_ext), ("rate bump", i_rate),
                    ("plan_merge_short", i_merge), ("trim", i_trim)):
        if idx < 0:
            return False, f"could not locate the {nm} stage"
    if not (i_ext < i_merge < i_rate or i_ext < i_rate):
        return False, ("multi-shot extension is not planned before the rate "
                       "bump")
    if not i_ext < i_trim:
        return False, "multi-shot extension is not planned before the trim"
    # extension must refuse to overlap another line's footage
    j = src.find("def plan_extend")
    body = src[j:j + 5200]
    for probe, why in (("real_b", "a hold's real footprint"),
                       ("lands", "reveal landings"),
                       ("src_dur", "the source duration"),
                       ("AssertionError", "an overlap invariant")):
        if probe not in body:
            return False, f"plan_extend does not respect {why}"
    return True, ("multi-shot extension exists, can reach past the host shot "
                  "to the next bound line, runs before the rate bump and the "
                  "trim, and asserts it never overlaps another line")


def test_intro_extends_not_pads() -> tuple[bool, str]:
    """The intro montage reaches for more footage instead of freezing.

    THE DEFECT: four frozen stretches of 0.93-1.83s, all inside the intro
    block (19.17-20.17, 20.17-22.00, 42.60-43.53, 47.90-48.90s with
    intro_offset at 53.43s). The slot loop read
        _read = min(me - ms, dur + 0.4)
    so when a chosen moment was SHORTER than its beat-cut slot, the shortfall
    was handed to an uncapped `tpad=stop_mode=clone` - a still frame in the
    first minute of the video. The main render's answer to "the window is too
    short" is more footage, and the intro now has to answer the same way.
    """
    src = io.open(os.path.join(ROOT, "pipeline", "intro.py"),
                  encoding="utf-8").read()
    if "min(me - ms, dur + 0.4)" in src:
        return False, ("the slot loop still clamps its read to the moment's "
                       "own end, so a short moment is padded with a frozen "
                       "frame instead of extended")
    i = src.find("def build_intro")
    body = src[i:] if i >= 0 else src
    for probe, why in (("extend_limit(", "it never asks how far it may read"),
                       ("_slot_durs", "it cannot shorten a slot that really "
                                      "has no footage left"),
                       ("vid_total", "the audio would still be cut to the "
                                     "beat-cut length, not the real one")):
        if probe not in body:
            return False, f"intro montage: {why}"
    from pipeline import intro as _intro
    if not hasattr(_intro, "extend_limit"):
        return False, "intro.extend_limit() does not exist"
    return True, ("the intro montage extends into adjacent footage, shortens "
                  "a slot rather than freezing when footage runs out, and "
                  "trims its audio to the real length")


def test_intro_traceable() -> tuple[bool, str]:
    """A freeze inside the intro can be mapped back to its source footage.

    THE DEFECT: render.py recorded the intro's spans ONLY when some shot was
    censor-flagged, because the censor audit was the only consumer. With no
    flagged shots nothing was recorded, so every freeze in the intro block was
    untraceable - and `motion_check` reports an untraceable freeze rather than
    excusing it. All four reported freezes were in that blind spot.

    Also checks the coordinate space. The intro sits at 0..intro_offset in the
    FINISHED file while every story clip is positioned before the offset is
    added, so a record has to say which space its out_a/out_b are in. Without
    that the intro's spans were searched at negative timestamps.
    """
    rsrc = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                   encoding="utf-8").read()
    i = rsrc.find("_intro.used_footage()")
    if i < 0:
        return False, "render.py never records the intro's footage"
    if "if _flagged" in rsrc[max(0, i - 400):i]:
        return False, ("the intro's footage is still recorded only when a "
                       "shot is censor-flagged, so with no flags every intro "
                       "freeze is untraceable")
    if "out_abs" not in rsrc[i:i + 400]:
        return False, ("the intro's spans are recorded without out_abs, so "
                       "they are shifted by intro_offset and match nothing")

    # behaviour, not just shape: a freeze at 20s of the finished file must
    # resolve to the source span the intro showed there.
    from pipeline.censor import UsedFootage
    from pipeline import motion_check as mc
    uf = UsedFootage()
    uf.add(1200.0, 1203.0, "intro montage slot 3", blurred=False,
           out_a=19.0, out_b=22.0, out_abs=True)
    uf.add(400.0, 410.0, "clip", blurred=False, line_id=7,
           out_a=0.0, out_b=10.0)
    got = mc._to_source({"start": 19.17, "end": 20.17, "dur": 1.0}, uf.items, 53.43)
    if not got:
        return False, ("a freeze at 19.17-20.17s of the finished file still "
                       "maps to no source span, so it is reported as "
                       "untraceable")
    if not (1199.0 <= float(got[0]) <= 1204.0):
        return False, (f"the freeze mapped to {got}, not the intro span that "
                       f"was on screen at 19.17s")
    # and a story freeze must still have the offset subtracted
    story = mc._to_source({"start": 55.0, "end": 56.0, "dur": 1.0}, uf.items, 53.43)
    if not story or not (399.0 <= float(story[0]) <= 411.0):
        return False, (f"a story freeze mapped to {story}; the intro_offset "
                       f"is no longer being applied to story clips")
    return True, ("intro spans are always recorded, carry final-file "
                  "coordinates, and a freeze in the intro resolves to the "
                  "footage that was on screen")


def test_footprint_is_real_span() -> tuple[bool, str]:
    """A line's footprint is what the render READS, not what it declares.

    THE DEFECT: lines 100 and 101 shared 0.48s of footage. Their declared
    windows abut exactly and do not overlap - but 101 is a 6.0s hold in a
    5.52s window, and `_build_silence_clip` reads its authored length straight
    from the source with no `-t`, so it really reached 0.48s into line 100.

    The distinction that makes this subtle, and that a first version of the
    shared helper got wrong in the generous direction: a NARRATED clip that
    overruns is SLOWED to fit, and `_build_clip` passes `-t shot_dur` exactly
    when the slowdown engages - so for a narrated line the window IS the
    ceiling. Only an unslowed read (every wordless unit) can exceed it.
    """
    from pipeline import footprint as fp
    hold = {"id": 1, "clip_start": "00:00:10.000", "clip_end": "00:00:15.520",
            "narration_silence_seconds": 6.0}
    got = fp.footprint(hold, 0.0)
    if not got or abs(got[1] - 16.0) > 0.01:
        return False, (f"a 6.0s hold in a 5.52s window reports {got}, not a "
                       f"real end of 16.0s - the overrun is invisible again")
    narr = {"id": 2, "clip_start": "00:00:10.000", "clip_end": "00:00:13.000",
            "narration": "a line far too long for three seconds of footage"}
    got2 = fp.footprint(narr, 9.0)
    if not got2 or abs(got2[1] - 13.0) > 0.01:
        return False, (f"a slowed narrated clip reports {got2}; the render "
                       f"caps its read with -t, so its footprint must stop at "
                       f"the window or the fitter reserves footage nothing "
                       f"shows")
    draft = {"lines": [hold, {"id": 3, "clip_start": "00:00:15.520",
                              "clip_end": "00:00:26.680",
                              "narration": "the next line"}]}
    ov = fp.overlaps(draft, {})
    if not ov:
        return False, ("the abutting pair that really overlaps by 0.48s is "
                       "reported as clean")
    if abs(ov[0]["overlap"] - 0.48) > 0.02:
        return False, f"overlap measured as {ov[0]['overlap']:.3f}s, not 0.48s"
    return True, ("a footprint is [start, start+clip_len) for an unslowed "
                  "read and the declared window for a slowed one, and the "
                  "100/101 overlap is detected")


def test_hold_capacity_checked() -> tuple[bool, str]:
    """A hold longer than its window is a capacity overrun.

    `capacity_findings` skipped every wordless unit on the grounds that it
    "carries no narration". True - but it carries a LENGTH, read at real speed
    with no slowdown available to absorb it, so the window has to hold it. That
    exemption is why nothing flagged line 101 before the render.

    Also: the fix must not be a rate bump. A hold has no words to read faster,
    and stamping a rate_bump on a wordless line would mark its audio stale
    forever, so the lever is the hold's own length.
    """
    from pipeline import preflight as pf
    draft = {"lines": [{"id": 101, "clip_start": "00:00:10.000",
                        "clip_end": "00:00:15.520", "tag": "normal",
                        "narration_silence_seconds": 6.0}]}
    f = pf.capacity_findings(draft, [])
    if not f:
        return False, ("a 6.0s hold in a 5.52s window is reported as fitting; "
                       "wordless units are exempt from the capacity check "
                       "again")
    if not f[0].get("wordless"):
        return False, "the finding is not marked wordless"
    if abs(f[0]["over"] - 0.48) > 0.02:
        return False, f"overrun measured as {f[0]['over']:.3f}s, not 0.48s"
    if f[0]["capacity"] > f[0]["shot_dur"] + 1e-6:
        return False, ("the hold's capacity was multiplied by "
                       "BINDING_SLOWDOWN_MAX; nothing slows a hold, so its "
                       "capacity is the bare window")
    src = io.open(os.path.join(ROOT, "tools", "fit_narration.py"),
                  encoding="utf-8").read()
    i = src.find("bounded rate bump")
    if i < 0 or 'f.get("wordless")' not in src[i:i + 1800]:
        return False, ("the rate-bump stage does not skip wordless units, so "
                       "a hold can still be handed a meaningless rate_bump")
    if "c-hold" not in src:
        return False, ("there is no hold-shortening resolution, so a hold that "
                       "cannot be given enough footage has no honest fix")
    return True, ("a hold that exceeds its window is a capacity overrun, its "
                  "capacity is the bare window, and it is resolved by "
                  "shortening the hold rather than by a rate bump")


def test_footprint_shared() -> tuple[bool, str]:
    """One definition of the footprint, used by every consumer.

    Five callers each had their own version: plan_widen used declared windows
    (and moved the boundaries that overlapped), plan_extend handled holds,
    needed_spans handled holds, available_window handled holds, the censor
    audit handled holds. The one that got it wrong is the one that decided
    where windows go.
    """
    missing = []
    for mod, fn in (("tools/fit_narration.py", "plan_widen/plan_extend"),
                    ("pipeline/preflight.py", "available_window"),
                    ("pipeline/stems.py", "needed_spans")):
        src = io.open(os.path.join(ROOT, *mod.split("/")),
                      encoding="utf-8").read()
        if "footprint" not in src:
            missing.append(f"{fn} ({mod})")
    if missing:
        return False, ("these still compute the footprint themselves: "
                       + "; ".join(missing))
    return True, ("the fitter, the pre-flight and the stems pass all share "
                  "pipeline/footprint.py")


TESTS = {
    "SLOWDOWN-CAPPED":      test_slowdown_capped,
    "INTRO-EXTENDS-NOT-PADS": test_intro_extends_not_pads,
    "INTRO-TRACEABLE":      test_intro_traceable,
    "FOOTPRINT-REAL-SPAN":  test_footprint_is_real_span,
    "FOOTPRINT-SHARED":     test_footprint_shared,
    "HOLD-CAPACITY-CHECKED": test_hold_capacity_checked,
    "STATIC-SOURCE-EXCUSED": test_static_source_excused,
    "BUMP-NEVER-COMPOUNDS":  test_bump_never_compounds,
    "MULTI-SHOT-BEFORE-TRIM": test_multi_shot_before_trim,
    "FREEZE-CAPPED":        test_freeze_capped,
    "FREEZE-DETECTED":      test_freeze_detected,
    "FREEZE-FATAL":         test_freeze_fatal,
    "REUSE-DETECTED":       test_reuse_detected,
    "REUSE-USES-SHOWN":     test_reuse_uses_shown,
    "HOLD-WINDOW-HONEST":   test_hold_window_honest,
    "MULTI-SHOT-EXTENSION": test_multi_shot_extension,
}

if __name__ == "__main__":
    want = sys.argv[1:] or list(TESTS)
    bad = 0
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
        print(f'{"PASS" if ok else "FAIL"}  {name:<22} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_motion: all pass" if not bad else
          f"test_motion: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
