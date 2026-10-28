# -*- coding: utf-8 -*-
"""
Music: one BED under the whole recap, with mood CUES layered on top.

Replaces the per-unit mood-bed switching (2c). The design, in one place:

  BED    projects/<name>/music/bed.mp3 - a single track looped seamlessly
         (crossfade at the loop point) under the ENTIRE recap, ducked ~-22 dB
         under narration and RAISED in holds.
  CUES   projects/<name>/music/cues/<mood>*.mp3 for tense/sad/action/mystery,
         1-3 files per mood, ROTATED so the same cue never repeats back to
         back. A cue is layered ON TOP of the bed and fires ONLY on a run of
         >=MUSIC_CUE_MIN_RUN consecutive lines of that mood, or a hold after a
         sad/reveal line - never on a single line. Fades in/out ~1.75s. While a
         cue plays the bed dips ~-6 dB; the cue itself ducks under narration
         like the bed (8-12 dB in action runs).
  REVEAL music/cues/reveal*.mp3 - bed and cues dip to near-silence 1-2s before
         a reveal line, one short sting lands on the reveal, then the bed
         returns.
  DENSITY about 1 cue / 90s on average at most, and >=20s between cues.

FALLBACKS, each printed:
  no cues          -> bed only
  no bed           -> music.mp3 (the legacy single track)
  neither          -> no music

This module PLANS (plan_music) and BUILDS ONE track file (build_music_track).
render.py then mixes that single pre-built track under the voice exactly as it
already mixes a bed, so the final filter graph stays one expression.
"""
from __future__ import annotations

import random
import subprocess
from pathlib import Path

from rich.console import Console

import config

console = Console()

_AUDIO_EXTS = (".mp3", ".m4a", ".wav", ".ogg")


def _db(x: float) -> float:
    return 10.0 ** (float(x) / 20.0)


def _dur(ff: str, p: Path) -> float:
    r = subprocess.run(
        [config.ffprobe(), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
def bed_file(pdir: Path) -> Path | None:
    for ext in _AUDIO_EXTS:
        p = pdir / "music" / f"bed{ext}"
        if p.exists():
            return p
    return None


def legacy_music(pdir: Path) -> Path | None:
    for ext in _AUDIO_EXTS:
        p = pdir / f"music{ext}"
        if p.exists():
            return p
    return None


def cue_files(pdir: Path) -> dict[str, list[Path]]:
    """{mood: [files]} for every mood that has at least one cue, plus 'reveal'.

    Matched by filename PREFIX: tense*.mp3, sad*.mp3, action*.mp3, mystery*.mp3,
    reveal*.mp3 under music/cues/. Sorted so rotation is deterministic.
    """
    cdir = pdir / "music" / "cues"
    out: dict[str, list[Path]] = {}
    if not cdir.is_dir():
        return out
    moods = set(config.MUSIC_CUE_MOOD_FOR_TAG.values()) | {"reveal"}
    for mood in sorted(moods):
        hits = sorted(p for p in cdir.iterdir()
                      if p.suffix.lower() in _AUDIO_EXTS
                      and p.stem.lower().startswith(mood))
        if hits:
            out[mood] = hits
    return out


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #
def _mood_of(tag: str) -> str | None:
    return config.MUSIC_CUE_MOOD_FOR_TAG.get(str(tag or "").strip())


def plan_cues(draft: dict, timeline: list, cues: dict,
              reveal_positions: list | None = None,
              hold_windows: list | None = None) -> list[dict]:
    """Decide WHERE cues play. Returns a list of
        {"mood", "file", "start", "end", "why"}
    ordered in time, honouring the min-run, rotation, and density rules.

    A cue is proposed by:
      - a RUN of >= MUSIC_CUE_MIN_RUN consecutive narrated lines sharing one cue
        mood (the cue spans the run), or
      - a HOLD that comes right after a sad or reveal line (the cue fills it).
    Then the density caps drop proposals that are too close together, and
    rotation picks which file so the same cue never repeats back to back.
    """
    reveal_positions = sorted(reveal_positions or [])
    hold_windows = hold_windows or []

    # line_id -> delivery tag, and id -> timeline slot
    tag_by_id = {l.get("id"): str(l.get("delivery") or "normal")
                 for l in draft.get("lines", [])}
    slot_by_id = {t.get("id"): t for t in timeline if t.get("id") is not None}
    # narrated lines in time order (those present in the timeline)
    ordered = [t for t in sorted(timeline, key=lambda t: t.get("start", 0.0))
               if t.get("id") in tag_by_id]

    proposals: list[dict] = []

    # 1. mood runs
    i = 0
    n = len(ordered)
    while i < n:
        mood = _mood_of(tag_by_id[ordered[i]["id"]])
        if mood is None or mood not in cues:
            i += 1
            continue
        j = i
        while j < n and _mood_of(tag_by_id[ordered[j]["id"]]) == mood:
            j += 1
        run = ordered[i:j]
        if len(run) >= config.MUSIC_CUE_MIN_RUN:
            proposals.append({
                "mood": mood,
                "start": float(run[0]["start"]),
                "end": float(run[-1]["end"]),
                "why": f"run of {len(run)} {mood} lines "
                       f"(L{run[0]['id']}-L{run[-1]['id']})",
            })
        i = j

    # 2. holds after a sad/reveal line -> a cue fills the hold
    for (hs, he) in hold_windows:
        # which narrated line ends just before this hold?
        prev = [t for t in ordered if t.get("end", 0.0) <= hs + 0.5]
        if not prev:
            continue
        ptag = tag_by_id[prev[-1]["id"]]
        if ptag == "sad" and "sad" in cues:
            proposals.append({"mood": "sad", "start": float(hs),
                              "end": float(he),
                              "why": f"hold after a sad line (L{prev[-1]['id']})"})
        elif ptag == "reveal" and "sad" in cues:
            # after a reveal, a sad/soft cue lets it settle
            proposals.append({"mood": "sad", "start": float(hs),
                              "end": float(he),
                              "why": f"hold after a reveal (L{prev[-1]['id']})"})

    proposals.sort(key=lambda p: p["start"])

    # 3. density caps: >= MIN_GAP between cues, and <= 1 per AVG_SPACING on
    # average across the film.
    total = ordered[-1]["end"] if ordered else 0.0
    cap_by_avg = int(total / config.MUSIC_CUE_AVG_SPACING_SEC) + 1
    kept: list[dict] = []
    last_end = -1e9
    for p in proposals:
        if p["start"] < last_end + config.MUSIC_CUE_MIN_GAP_SEC:
            continue
        kept.append(p)
        last_end = p["end"]
    if len(kept) > cap_by_avg:
        # keep the LONGEST runs (most earned), preserving time order after
        kept = sorted(sorted(kept, key=lambda p: p["end"] - p["start"],
                             reverse=True)[:cap_by_avg],
                      key=lambda p: p["start"])

    # 4. rotation: never the same file back to back WITHIN a mood
    rot: dict[str, int] = {}
    last_file_for_mood: dict[str, Path] = {}
    for p in kept:
        files = cues[p["mood"]]
        idx = rot.get(p["mood"], 0) % len(files)
        f = files[idx]
        if len(files) > 1 and last_file_for_mood.get(p["mood"]) == f:
            idx = (idx + 1) % len(files)
            f = files[idx]
        rot[p["mood"]] = idx + 1
        last_file_for_mood[p["mood"]] = f
        p["file"] = f
    return kept


# --------------------------------------------------------------------------- #
# Building the one track
# --------------------------------------------------------------------------- #
def build_music_track(ff: str, pdir: Path, out: Path, total_dur: float,
                      bed: Path, cue_plan: list[dict],
                      reveal_positions: list | None = None,
                      hold_windows: list | None = None) -> bool:
    """Render the bed (looped, crossfaded at the loop point) with the cues
    layered on top and the reveal dips, to one wav of length total_dur.

    This bed+cues track still has NO narration in it and is NOT ducked -
    render.py sidechains it under the voice afterwards, exactly as it does a
    mood bed. What IS baked here is every RELATIONSHIP that must survive that
    single global duck: the per-cue bed dip, the reveal near-silence dip, and
    each cue's level relative to the bed (see the cue loop below - this is what
    makes a cue audible rather than another layer of bed).
    """
    reveal_positions = sorted(reveal_positions or [])
    hold_windows = hold_windows or []
    fade = config.MUSIC_CUE_FADE_SEC
    dip = config.MUSIC_PRE_REVEAL_DROP_SEC
    near = config.MUSIC_PRE_REVEAL_LEVEL
    bed_dip = _db(config.MUSIC_CUE_BED_DIP_DB)

    inputs = ["-stream_loop", "-1", "-t", f"{total_dur:.3f}", "-i", str(bed)]

    # bed volume expression: 1.0 normally, dip to bed_dip while a cue plays,
    # dip to `near` for `dip` seconds before each reveal.
    bed_terms = []
    for p in cue_plan:
        bed_terms.append(f"between(t,{p['start']:.3f},{p['end']:.3f})*{bed_dip:.4f}")
    bed_vol = "1"
    if bed_terms:
        # max of (1 outside cues) and the dip inside cues: use a product form
        # - simplest correct: start at 1, multiply by bed_dip inside each cue.
        inside = "+".join(f"between(t,{p['start']:.3f},{p['end']:.3f})"
                          for p in cue_plan)
        bed_vol = f"if(gt({inside},0),{bed_dip:.4f},1)"
    # reveal near-silence wins over everything
    for rp in reveal_positions:
        lo = max(0.0, rp - dip)
        bed_vol = f"if(between(t,{lo:.3f},{rp:.3f}),{near:.4f},{bed_vol})"

    parts = [f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,"
             f"volume='{bed_vol}':eval=frame[bed]"]
    labels = ["[bed]"]
    idx = 1

    # each cue: an input trimmed to its length, faded, placed at its start
    #
    # THE CUE LEVEL, and why it has to be baked in here.
    # render.py mixes this finished track under the voice with ONE duck
    # (MUSIC_DUCK_DB, -22 dB) applied to the whole thing. So a cue inside this
    # track was ducked to exactly the same depth as the bed - the event sat at
    # the level of the furniture it was supposed to rise above. That is why the
    # cues could not be heard, and MUSIC_CUE_DUCK_DB / _ACTION_DB were DEAD
    # CONFIG: nothing anywhere read them.
    #
    # The mix architecture does not need changing to fix it. Give each cue a
    # RELATIVE gain of (cue duck - bed duck) here, and the single global duck
    # then lands the bed at MUSIC_DUCK_DB and the cue at MUSIC_CUE_DUCK_DB:
    #     bed  -22 dB          cue  -22 + 10 = -12 dB
    #     action cue           -22 + 14 =  -8 dB
    # It falls out correctly in holds too: the silence swell raises the whole
    # track to SILENCE_MUSIC_VOLUME (about -10 dB), which puts a cue at roughly
    # -0.5 dB - near full level, which is what a hold is for.
    _bed_duck = float(getattr(config, "MUSIC_DUCK_DB", -22.0))
    _cue_duck = float(getattr(config, "MUSIC_CUE_DUCK_DB", -12.0))
    _cue_duck_action = float(getattr(config, "MUSIC_CUE_DUCK_ACTION_DB", -8.0))
    for k, p in enumerate(cue_plan):
        cue_len = p["end"] - p["start"]
        if cue_len < 1.0:
            continue
        inputs += ["-i", str(p["file"])]
        delay_ms = int(max(0.0, p["start"]) * 1000)
        lbl = f"cue{k}"
        _target = (_cue_duck_action if str(p.get("mood")) == "action"
                   else _cue_duck)
        _rel = _target - _bed_duck          # dB, positive = louder than bed
        # fade in/out within the cue, lift to its level, delay to its start,
        # pad to full length
        parts.append(
            f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
            f"atrim=duration={cue_len:.3f},"
            f"afade=t=in:st=0:d={min(fade, cue_len/2):.2f},"
            f"afade=t=out:st={max(0.0, cue_len-fade):.2f}:d={min(fade, cue_len/2):.2f},"
            f"volume={_rel:+.2f}dB,"
            f"adelay={delay_ms}|{delay_ms},apad=whole_dur={total_dur:.3f}[{lbl}]")
        labels.append(f"[{lbl}]")
        idx += 1

    if len(labels) == 1:
        # bed only (no cues placed) - still render the bed track so the caller
        # has a single file with the reveal dips baked in.
        graph = parts[0].replace("[bed]", "[mixout]")
    else:
        graph = ";".join(parts) + ";" + "".join(labels) + \
            f"amix=inputs={len(labels)}:duration=first:normalize=0," \
            f"alimiter=limit=0.95[mixout]"

    cmd = [ff, "-y", *inputs, "-filter_complex", graph,
           "-map", "[mixout]", "-t", f"{total_dur:.3f}",
           "-c:a", "pcm_s16le", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        console.print("[yellow]Music:[/] bed+cues build failed; "
                      "falling back to the plain bed.")
        console.print((r.stderr or "")[-400:])
        return False
    return True


# --------------------------------------------------------------------------- #
# Top-level: decide what track render.py should mix
# --------------------------------------------------------------------------- #
def resolve_music(ff: str, pdir: Path, work: Path, draft: dict, timeline: list,
                  total_dur: float, reveal_positions: list | None = None,
                  hold_windows: list | None = None,
                  legacy: Path | None = None):
    """Return (track_path, is_prebuilt, note) for render.py to mix, applying the
    fallback ladder and PRINTING which design is active and which files it found.

      bed + cues  -> prebuilt bed+cues track           (is_prebuilt True)
      bed only    -> the bed, looped by render.py      (is_prebuilt False)
      music.mp3   -> the legacy single track           (is_prebuilt False)
      neither     -> (None, ...) : render with no music

    PRECEDENCE: projects/<name>/music/ always wins over the legacy single track
    that recap.py auto-discovers (or --music downloads) and passes as `legacy`.
    If music/bed.* is absent but CUES exist, the legacy track is promoted to BE
    the bed so the cues still layer - dropping to "legacy single track" there
    silently threw away a populated music/cues/ directory.
    """
    bed = bed_file(pdir)
    cues = cue_files(pdir)
    # reveal stings live under 'reveal'; mood cues are the rest
    mood_cues = {m: f for m, f in cues.items() if m != "reveal"}
    if legacy is None:
        legacy = legacy_music(pdir)

    # ---- say what was FOUND, before saying what will be used ---------------
    _found = []
    _found.append(f"music/bed{bed.suffix}" if bed else "no music/bed.*")
    if cues:
        _found.append("music/cues: " + ", ".join(
            f"{m} x{len(f)}" for m, f in sorted(cues.items())))
    else:
        _found.append("no music/cues/*")
    _found.append(f"legacy {legacy.name}" if legacy else "no legacy music.*")
    console.print(f"[dim]Music files: {' | '.join(_found)}[/]")

    bed_is_legacy = False
    if bed is None:
        if legacy is not None and mood_cues:
            # promote the legacy track to bed so the cues are not thrown away
            bed, bed_is_legacy = legacy, True
            console.print(
                f"[cyan]Music design: BED + CUES[/] - no music/bed.*, so "
                f"{legacy.name} is used AS the bed, with the "
                f"music/cues/ files layered on top.")
        elif legacy is not None:
            console.print(
                f"[yellow]Music design: LEGACY SINGLE TRACK[/] - {legacy.name}, "
                f"no music/bed.* and no music/cues/*. Add music/bed.mp3 + "
                f"music/cues/<mood>*.mp3 for the bed+cues design.")
            return legacy, False, "legacy single track"
        else:
            console.print("[yellow]Music design: NONE[/] - no music/bed.*, no "
                          "music/cues/* and no music.* - rendering with NO music.")
            return None, False, "no music"

    if not mood_cues:
        console.print(
            "[cyan]Music design: BED ONLY[/] (no music/cues/<mood>*.* found). "
            "The bed runs under the whole recap, ducked under the voice and "
            "raised in holds. Add cue files for layered mood.")
        return bed, False, "bed only"

    plan = plan_cues(draft, timeline, cues, reveal_positions, hold_windows)
    if not plan:
        console.print(
            "[cyan]Music:[/] bed only - cues are present but nothing earned one "
            "(need a run of >= "
            f"{config.MUSIC_CUE_MIN_RUN} same-mood lines or a hold after a "
            "sad/reveal line).")
        return bed, False, "bed only (no cue earned)"

    out = work / "music_track.wav"
    ok = build_music_track(ff, pdir, out, total_dur, bed, plan,
                           reveal_positions, hold_windows)
    if not ok:
        return bed, False, "bed only (cue build failed)"

    _by_mood: dict[str, int] = {}
    for p in plan:
        _by_mood[p["mood"]] = _by_mood.get(p["mood"], 0) + 1
    console.print(
        f"[cyan]Music design: BED + CUES[/] - bed {bed.name}"
        + (" (legacy track promoted)" if bed_is_legacy else "") + " + "
        + ", ".join(f"{v} {k} cue(s)" for k, v in sorted(_by_mood.items()))
        + f" over {total_dur/60:.1f} min "
        f"(>= {config.MUSIC_CUE_MIN_GAP_SEC:.0f}s apart, bed dips "
        f"{config.MUSIC_CUE_BED_DIP_DB:.0f} dB under each cue).")
    for p in plan:
        console.print(f"[dim]    cue {p['start']:.0f}-{p['end']:.0f}s "
                      f"{p['mood']} ({p['file'].name}) - {p['why']}[/]")
    return out, True, "bed + cues"
