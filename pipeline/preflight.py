"""Pre-flight: check EVERY line's real audio against its window before rendering.

WHY THIS EXISTS
---------------
The first Warren render died like this:

    BindingViolation, line 11: narration 13.8s > shot capacity 13.4s
                               (window 9.6s x 1.4)

- after all 109 lines had been synthesized, and after 10 clips had been built.
The capacity contract was checked INSIDE the clip loop, one line at a time, so
the first offender aborted the render and the other 18 stayed invisible. You
fixed one line, re-ran, and met the next one. Nineteen times.

The draft-time gate ([BINDING-VIOLATION], schemas.binding_capacity_check) cannot
replace this, because at draft time there is no audio: it estimates length from
word count at a single configured words-per-minute. Warren does not have a
single rate - measured across these 109 lines he runs 151 WPM on `sad` and 261
WPM on `tense`, a 1.7x spread - so the estimate was wrong in both directions.
It over-estimated capacity on the slow tags (every big overrun here is `sad` or
`reveal`) and wasted footage on the fast ones.

Once narration exists the guesswork is over: this module measures the actual
audio and answers the capacity question exactly, for all lines at once, BEFORE
a single clip is built.

It mirrors render.py's formula deliberately and exactly:

    need = _lead_for(narr_dur, shot_dur) + narr_dur + GAP
    cap  = shot_dur * BINDING_SLOWDOWN_MAX
    overrun when shot_dur > 0 and need > cap

If those two ever drift apart, the pre-flight would pass a render that then
crashes - so tools/test_preflight.py asserts they agree by driving the real
render on a deliberately overrun fixture.
"""
from __future__ import annotations

from pathlib import Path

from rich.console import Console

console = Console()


def _audio_dur(ffprobe: str, p: Path) -> float:
    import subprocess
    r = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
        capture_output=True, text=True)
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


def stale_audio(draft: dict, pdir: Path) -> list[int]:
    """Line ids whose narration/*.mp3 does NOT match the current text.

    Measuring a capacity overrun against audio of a DIFFERENT text is worse
    than not measuring: after a trim pass the files on disk still hold the old,
    longer reading, so the pre-flight would report overruns that the next
    render has already fixed - and would miss ones it has not. The TTS cache
    manifest already records the signature of exactly what was synthesized, so
    ask it rather than guessing from timestamps.

    Returns [] when the manifest or the provider cannot be consulted: an
    unknown answer must not masquerade as "all fresh".
    """
    import json
    try:
        from pipeline.tts import DEFAULT_PROVIDER
        from pipeline.tts_providers import all_providers
        prov = all_providers().get(DEFAULT_PROVIDER)
        if prov is None:
            return []
        man = json.loads((pdir / "narration" / "_cache.json")
                         .read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for ln in draft.get("lines", []):
        text = str(ln.get("narration") or "").strip()
        if not text:
            continue
        key = f"line_{ln['id']:03d}.mp3"
        if key not in man:
            continue
        try:
            sig = prov.cache_signature(
                text, str(ln.get("delivery") or "normal"),
                float(ln.get("rate_bump") or 1.0))
        except Exception:
            continue
        if man[key] != sig:
            out.append(ln["id"])
    return sorted(out)


def available_window(draft: dict, line_id, src_dur: float = 0.0) -> float:
    """Seconds of footage a line could have - its own window PLUS the free
    footage either side that no other line uses.

    This is the number the WRITER needs, and it is not the shot's duration.
    tokyodrift2006 has 71 minutes of unused footage in 75 gaps, so a line whose
    shot is 3 seconds long may have 30 seconds available to it; budgeting from
    the shot alone under-counts it badly. Conversely a line whose neighbour
    abuts immediately really does have only its own window, and budgeting from
    a generous shot over-counts it.

    Bounded by the neighbours' REAL footprints (a hold plays past its declared
    end) and by the source duration. Reveal landings are deliberately NOT
    applied here: this is a budget, and the fitter applies the landing rule
    when it actually moves a boundary.
    """
    from pipeline.draft import parse_ts
    from pipeline.render import intro_owned
    rows = []
    for ln in draft.get("lines") or []:
        if intro_owned(ln) or ln.get("pool") or ln.get("montage"):
            continue
        cs, ce = ln.get("clip_start"), ln.get("clip_end")
        if not cs or not ce:
            continue
        try:
            a, b = parse_ts(cs), parse_ts(ce)
        except Exception:
            continue
        hold = (ln.get("narration_silence_seconds")
                or ln.get("film_speaks_seconds"))
        rows.append({"id": ln.get("id"), "a": a, "b": b,
                     "real_b": max(b, a + float(hold)) if hold else b})
    rows.sort(key=lambda r: r["a"])
    for i, r in enumerate(rows):
        if r["id"] != line_id:
            continue
        lo = rows[i - 1]["real_b"] if i else 0.0
        hi = rows[i + 1]["a"] if i + 1 < len(rows) else (
            float(src_dur) if src_dur else r["b"])
        return max(0.0, min(hi, float(src_dur) if src_dur else hi) - lo)
    return 0.0


def budget_words(window_sec: float, tag: str | None = None) -> int:
    """The writer's word budget for `window_sec` of footage.

    THE SAME CONTRACT THE RENDER ENFORCES, in one place:
        window x BINDING_SLOWDOWN_MAX          the capacity the render allows
        - GAP                                   the inter-line gap it adds
        - max(CAPACITY_MARGIN_MIN_SEC, 3%)      the headroom the fitter demands
        / the MEASURED rate for this tag        what the voice actually does

    Every one of those four was wrong somewhere at some point, which is how a
    draft arrived with 42 overruns: the rate was 185 WPM against a measured
    140.6, the margin existed only in the fitter, and the window was the shot's
    own length rather than the footage available.
    """
    import config
    from pipeline.calibration import production_profile
    from pipeline.schemas import BINDING_SLOWDOWN_MAX
    cap = max(0.0, float(window_sec)) * float(BINDING_SLOWDOWN_MAX)
    return production_profile().max_words_for_capacity(cap, tag)


def capacity_findings(draft: dict, narration: list,
                      ffprobe: str | None = None,
                      skip_ids: set | None = None) -> list[dict]:
    """Every line whose REAL narration overruns its window capacity.

    `narration` is the [(line_id, path, duration)] list the TTS pass returns -
    the same object render() receives, so this measures exactly what will be
    rendered. Durations already in that list are trusted; a missing one is
    probed with ffprobe.

    Returns a list of dicts sorted worst-first:
        line_id, words, tag, narr_dur, shot_dur, need, capacity, over, ratio

    Only lines bound to ONE explicit window are checked, which is exactly the
    set render.py enforces the contract on:
      * `pool` lines resolve their window at render time from broll.json
      * `montage` lines scale their segments to the narration by construction
      * hold / film_speaks lines carry no narration
    Mirroring that scope matters: checking more than render enforces would
    block renders that work.
    """
    import config
    from pipeline.draft import parse_ts
    from pipeline.render import _lead_for, GAP, intro_owned
    from pipeline.schemas import BINDING_SLOWDOWN_MAX

    ffprobe = ffprobe or config.ffprobe()
    dur_by_id: dict = {}
    for item in narration or []:
        try:
            lid, path = item[0], Path(item[1])
            d = float(item[2]) if len(item) > 2 and item[2] else 0.0
        except (TypeError, ValueError, IndexError):
            continue
        if d <= 0 and path.exists():
            d = _audio_dur(ffprobe, path)
        dur_by_id[lid] = d

    skip_ids = set(skip_ids or ())
    out = []
    for ln in draft.get("lines", []):
        lid = ln.get("id")
        if lid in skip_ids:
            continue
        if intro_owned(ln):
            continue
        if ln.get("pool") or ln.get("montage"):
            continue
        if (ln.get("narration_silence_seconds") is not None
                or ln.get("film_speaks_seconds") is not None):
            continue
        cs, ce = ln.get("clip_start"), ln.get("clip_end")
        if not cs or not ce:
            continue
        narr_dur = float(dur_by_id.get(lid) or 0.0)
        if narr_dur <= 0:
            continue                      # no audio measured; nothing to judge
        try:
            shot_dur = max(0.0, parse_ts(ce) - parse_ts(cs))
        except Exception:
            continue
        if shot_dur <= 0:
            continue
        need = _lead_for(narr_dur, shot_dur) + narr_dur + GAP
        cap = shot_dur * BINDING_SLOWDOWN_MAX
        if need <= cap:
            continue
        out.append({
            "line_id": lid,
            "words": len(str(ln.get("narration") or "").split()),
            "tag": str(ln.get("delivery") or "normal"),
            "narr_dur": round(narr_dur, 2),
            "shot_dur": round(shot_dur, 2),
            "need": round(need, 2),
            "capacity": round(cap, 2),
            "over": round(need - cap, 2),
            "ratio": round(need / cap, 3) if cap else 0.0,
            "clip_start": cs,
            "clip_end": ce,
        })
    out.sort(key=lambda r: -r["over"])
    return out


def report(findings: list[dict], project: str = "") -> bool:
    """Print every overrun in ONE list. Returns True if the render may proceed.

    The point of the list is that it is a LIST. The render loop reported one
    line per run, which turned a 19-line problem into nineteen render attempts.
    """
    if not findings:
        return True
    from pipeline.schemas import BINDING_SLOWDOWN_MAX
    console.print(
        f"[red][CAPACITY-PREFLIGHT][/] {len(findings)} line(s) have narration "
        f"that cannot fit their window, measured on the REAL audio "
        f"(contract: narration <= window x {BINDING_SLOWDOWN_MAX:.1f}):")
    console.print(f"[red]  {'line':>5} {'tag':<7} {'words':>5} {'narr':>7} "
                  f"{'window':>7} {'need':>7} {'cap':>7} {'over':>7}[/]")
    for f in findings:
        console.print(
            f"[red]  {f['line_id']:>5} {f['tag']:<7} {f['words']:>5} "
            f"{f['narr_dur']:>7.2f} {f['shot_dur']:>7.2f} {f['need']:>7.2f} "
            f"{f['capacity']:>7.2f} {f['over']:>7.2f}[/]")
    worst = findings[0]
    console.print(
        f"[red]  worst: line {worst['line_id']} needs "
        f"{worst['ratio']:.2f}x its capacity.[/]")
    console.print(
        f"[yellow]  Resolve them in one pass:  python tools/fit_narration.py "
        f"--project {project or '<project>'} --apply[/]")
    console.print(
        "[yellow]  It widens a window into adjacent footage of the same shot "
        "where that is free, else applies a small per-line rate bump, else "
        "writes a trim worklist for the lines that need the text shortened.[/]")
    return False
