

"""
Produce per-line narration audio.

--voice tts  : Edge-TTS neural voice (free, needs internet) -> narration/line_XXX.mp3
--voice mine : you record your own audio; we just locate your files.

Returns an ordered list of (line_id, audio_path, duration_seconds).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from rich.console import Console

import config

# The multi-provider abstraction lives in pipeline/tts_providers.py and is
# re-exported here so `from pipeline import tts` reaches it. It is a separate
# module rather than 700 more lines in this file because this file is the
# SHIPPING path the render depends on; the import is cheap (stdlib + config).
from pipeline.tts_providers import (  # noqa: F401
    TAGS,
    ProviderUnavailable,
    SynthesisFailed,
    UnknownTag,
    all_providers,
    synthesize_cached,
)

console = Console()

# The production narrator. Inworld "Warren" (mature announcer voice), steered
# per tag and calibrated to ~185 WPM on this draft - see tts_providers._inworld.
# Edge is the OFFLINE FALLBACK only: it cannot act, it only shifts rate/pitch,
# so a render that falls back to it is a degraded render and the pipeline says
# so out loud rather than shipping the downgrade silently.
DEFAULT_PROVIDER = "inworld"
FALLBACK_PROVIDER = "edge"


def _audio_duration(path: Path) -> float:
    fp = config.ffprobe()
    out = subprocess.run(
        [fp, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


# --------------------------------------------------------------------------- #
# Edge-TTS with per-line delivery (rate / pitch / volume)
# --------------------------------------------------------------------------- #
async def _edge_one(text: str, out: Path, voice: str,
                    rate: str, pitch: str, volume: str,
                    attempts: int = 4):
    """Synthesize one line, retrying transient Edge-TTS drops.

    The public Edge-TTS endpoint intermittently returns "No audio was
    received" for a valid request. A single drop must NOT abort a long
    render, so retry with backoff and verify a non-empty file was written.
    """
    import asyncio as _asyncio
    import edge_tts
    last_err = None
    for i in range(attempts):
        try:
            communicate = edge_tts.Communicate(
                text, voice=voice, rate=rate, pitch=pitch, volume=volume)
            await communicate.save(str(out))
            if out.exists() and out.stat().st_size > 0:
                return
            last_err = RuntimeError("empty audio file written")
        except Exception as e:  # noqa: BLE001 - transient network/service errors
            last_err = e
        # clean any zero-byte partial before retrying
        try:
            if out.exists() and out.stat().st_size == 0:
                out.unlink()
        except OSError:
            pass
        if i < attempts - 1:
            await _asyncio.sleep(2.0 * (i + 1))  # 2s, 4s, 6s backoff
    raise last_err if last_err else RuntimeError("TTS failed")


class UnknownDelivery(Exception):
    """A draft asked for a delivery tag that has no preset."""


def _delivery_for(ln: dict, base_rate: str) -> dict:
    """
    Resolve the per-line delivery. Priority:
      explicit rate/pitch/volume on the line  >  named 'delivery' preset  >
      default preset (with base_rate substituted for the global default).

    An UNKNOWN tag raises. It used to fall back to "normal", and that fallback
    is why every <reveal> line in tokyodrift2006 (ten of them) and the <action>
    line in badgenius2017 were read at exactly the pace of an ordinary
    sentence: the preset simply did not exist, the writer's mark was silently
    discarded, and nothing anywhere said so. A silent fallback on the one field
    whose entire purpose is to make lines sound different is worse than a
    crash - the render completes and looks finished.
    """
    raw = ln.get("delivery", config.DEFAULT_DELIVERY)
    # A missing or null tag is "normal" - that is an absent choice, not a wrong
    # one. Only a NAMED tag with no preset is an error.
    preset_name = str(raw).strip() if raw not in (None, "") else config.DEFAULT_DELIVERY
    if preset_name not in config.TTS_DELIVERY:
        raise UnknownDelivery(
            f"line {ln.get('id')} asks for delivery '{preset_name}', which has "
            f"no preset in config.TTS_DELIVERY. Known tags: "
            f"{', '.join(sorted(config.TTS_DELIVERY))}. Either add a preset "
            f"with a deliberate rate/pitch, or change the line's tag - do not "
            f"let it read as a normal line, which is what used to happen.")
    preset = dict(config.TTS_DELIVERY[preset_name])
    # "normal" carries no rate of its own - the CLI/base rate is the rate.
    if "rate" not in preset:
        preset["rate"] = base_rate
    # explicit per-line overrides win
    for k in ("rate", "pitch", "volume"):
        if k in ln:
            preset[k] = ln[k]
    return preset


def _select_provider():
    """Inworld 'Warren' by default; Edge as the offline fallback, loudly.

    Returns (provider, is_fallback). The default is Inworld because it can
    ACT - steer per tag, land ~185 WPM. Edge only shifts rate/pitch, so a
    render on Edge is a DOWNGRADE, and the pipeline prints that it happened
    rather than shipping it silently. Falls back when INWORLD_API_KEY is
    missing or the provider is otherwise unavailable.
    """
    provs = all_providers()
    primary = provs.get(DEFAULT_PROVIDER)
    if primary is not None:
        ok, why = primary.available()
        if ok:
            return primary, False
        console.print(
            f"[yellow]Voice fallback:[/] {primary.name} ({primary.voice_label}) "
            f"is unavailable - {why}. Falling back to {FALLBACK_PROVIDER} "
            f"(offline, rate/pitch only - no acting). Set INWORLD_API_KEY for "
            f"the production voice.")
    return provs[FALLBACK_PROVIDER], True


def generate_tts(project: str, draft: dict,
                 voice: str = config.DEFAULT_TTS_VOICE,
                 rate: str = config.DEFAULT_TTS_RATE) -> list[tuple[int, Path, float]]:
    pdir = config.ensure_project(project)
    ndir = pdir / "narration"
    ndir.mkdir(exist_ok=True)

    provider, is_fallback = _select_provider()

    # ---- pre-flight: every delivery tag must resolve BEFORE we synthesize ----
    # Fail on line 1, not on line 97 of 219 after eight minutes of network
    # calls. Resolve each tag against the CHOSEN provider's mapping so an
    # unmappable tag is caught up front, naming every bad tag in one pass.
    _bad_tags: dict = {}
    for ln in draft["lines"]:
        if (ln.get("narration_silence_seconds") is not None
                or ln.get("film_speaks_seconds") is not None):
            continue
        if not str(ln.get("narration", "")).strip():
            continue
        try:
            provider.controls_for(str(ln.get("delivery") or "normal"))
        except UnknownTag:
            _bad_tags.setdefault(str(ln.get("delivery")), []).append(ln.get("id"))
    if _bad_tags:
        console.print(f"[red][DELIVERY-UNKNOWN][/] the draft uses delivery tags "
                      f"with no mapping for provider '{provider.name}':")
        for _t, _ids in sorted(_bad_tags.items()):
            console.print(f"    '{_t}' on {len(_ids)} line(s): "
                          f"{_ids[:12]}{' ...' if len(_ids) > 12 else ''}")
        console.print(
            f"[red]  Known tags: {', '.join(sorted(TAGS))}.[/]\n"
            f"  A tag with no mapping used to fall back to 'normal' in silence, "
            f"which is how ten <reveal> lines were read at ordinary pace while "
            f"every gate stayed green. Add a mapping or retag the lines.")
        sys.exit(1)

    results: list[tuple[int, Path, float]] = []
    _tag = "[yellow]FALLBACK[/] " if is_fallback else ""
    console.print(f"[cyan]Generating voiceover[/] {_tag}with "
                  f"{provider.name} '{provider.voice_label}' (per-line delivery)")

    for ln in draft["lines"]:
        # Gap 3 / S9 silence line: no narration -> no TTS. The render builds a
        # silent held clip for it (matched by clip_start/clip_end, not by_id).
        if (ln.get("narration_silence_seconds") is not None
                or ln.get("film_speaks_seconds") is not None
                or not ln.get("narration", "").strip()):
            sec = ln.get("narration_silence_seconds")
            fsp = ln.get("film_speaks_seconds")
            if fsp:
                console.print(f"  line {ln['id']:>3}: [dim]film speaks "
                              f"({float(fsp):.0f}s, no narration)[/]")
            elif sec:
                console.print(f"  line {ln['id']:>3}: [dim]silence ({float(sec):.0f}s)[/]")
            else:
                console.print(f"  line {ln['id']:>3}: [dim]skipped (empty)[/]")
            continue

        out = ndir / f"line_{ln['id']:03d}.mp3"
        tag = str(ln.get("delivery") or "normal")
        # synthesize_cached owns its own manifest (text + voice + tag + model +
        # resolved controls), so retuning a tag's controls busts the cache for
        # just the affected lines - which a plain text+voice+tag key would miss.
        try:
            was_cached, dur = synthesize_cached(
                provider, str(ln["narration"]), tag, out, ndir)
        except (ProviderUnavailable, SynthesisFailed) as e:
            # The primary went down mid-run (e.g. a network blip). Fall back to
            # Edge for the rest rather than abort a 109-line render, and say so.
            if provider.name != FALLBACK_PROVIDER:
                console.print(f"[yellow]  line {ln['id']}: {provider.name} "
                              f"failed ({e}); switching to {FALLBACK_PROVIDER} "
                              f"for the remainder.[/]")
                provider, is_fallback = all_providers()[FALLBACK_PROVIDER], True
                was_cached, dur = synthesize_cached(
                    provider, str(ln["narration"]), tag, out, ndir)
            else:
                console.print(f"[red]TTS failed on line {ln['id']}:[/] {e}")
                sys.exit(1)

        results.append((ln["id"], out, dur))
        flag = "cached" if was_cached else "[yellow]new[/]"
        console.print(f"  line {ln['id']:>3}: {dur:5.2f}s  ({tag:<7}) {flag}")

    if is_fallback:
        console.print(
            "[yellow]  NOTE: this narration was rendered on the Edge fallback "
            "(rate/pitch only). It is not the production Warren voice.[/]")
    return results


# --------------------------------------------------------------------------- #
# Your own recordings
# --------------------------------------------------------------------------- #
def collect_mine(project: str, draft: dict) -> list[tuple[int, Path, float]]:
    """
    Expect one audio file per line in narration/, named line_001.* (mp3/wav/m4a).
    Tells you exactly which files are missing.
    """
    pdir = config.ensure_project(project)
    ndir = pdir / "narration"
    ndir.mkdir(exist_ok=True)

    results: list[tuple[int, Path, float]] = []
    missing: list[int] = []
    for ln in draft["lines"]:
        hits = sorted(ndir.glob(f"line_{ln['id']:03d}.*"))
        hits = [h for h in hits if h.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac", ".flac")]
        if not hits:
            missing.append(ln["id"])
            continue
        dur = _audio_duration(hits[0])
        results.append((ln["id"], hits[0], dur))

    if missing:
        console.print("[red]Missing your recordings for these lines:[/]")
        for mid in missing:
            console.print(f"  - drop a file named line_{mid:03d}.wav (or .mp3) in:")
        console.print(f"      {ndir}")
        console.print("\nSee script.txt for the text of each line. Then re-run render.")
        sys.exit(1)

    console.print(f"[green]Found all {len(results)} recordings.[/]")
    return results



