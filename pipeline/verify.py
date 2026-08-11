"""Verify what the RENDER actually says, not what the draft says it should.

Every gate in this pipeline validates draft.json. None of them look at the file
that gets published. That gap is not theoretical: two lines sharing an id shared
one TTS file, so both played the same voiceover - a line from 02:04:00 of the
film ran under footage from 07:20, and it implied the twist 36 seconds into the
video. REVEAL-TIMING was green and was not wrong; it reads the order of the
WORDS in draft.json, where that line sat correctly at minute 8. The corruption
happened after the gate ran.

So: transcribe final.mp4's own audio, line the transcript up against
timeline.json, and compare each line to what draft.json says it should be.

What this catches: a line playing the wrong audio, a line missing entirely,
lines rendered out of order, TTS mangling a name badly enough to change it.

What this does NOT catch: whether the picture matches the words. That is drift,
it needs vision, and RULES.md Part F checkpoint 2 still stands.

Similarity uses difflib on normalised text - stdlib, no new dependency. TTS is
not expected to reproduce the script exactly (numbers, punctuation, elisions),
so the threshold is deliberately loose; the failure this is built for looks like
0.1, not 0.8.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

from rich.console import Console

import config

console = Console()

MATCH_FLOOR = 0.55      # below this, the audio is a different sentence
SUSPECT_FLOOR = 0.75    # between the two, worth a look


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _extract_audio(mp4: Path) -> Path:
    wav = mp4.with_name("_verify16k.wav")
    cmd = [config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(mp4), "-vn", "-ac", "1", "-ar", "16000", str(wav)]
    subprocess.run(cmd, check=True)
    return wav


def _transcribe(wav: Path, model_size: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        console.print("[red]faster-whisper not installed.[/] pip install -r requirements.txt")
        return None
    console.print(f"Transcribing the rendered audio with '{model_size}'...")
    wmodel = WhisperModel(model_size, device="cpu", compute_type="int8")
    # WORD timestamps, not segment timestamps. A Whisper segment runs 10-15s and
    # routinely straddles two of our lines; pulling in whole overlapping segments
    # made every window inherit the previous line's sentence, which looked exactly
    # like a systematic render fault and was not one.
    segs, _info = wmodel.transcribe(str(wav), beam_size=1, vad_filter=False,
                                    word_timestamps=True)
    words = []
    for s in segs:
        for w in (getattr(s, "words", None) or []):
            words.append({"start": float(w.start), "end": float(w.end),
                          "text": w.word})
        if not getattr(s, "words", None):
            # model build without word timings - fall back to the segment,
            # placed at its midpoint so it lands in exactly one window
            mid = (float(s.start) + float(s.end)) / 2.0
            words.append({"start": mid, "end": mid, "text": s.text})
    return words


def _text_in_window(words, a: float, b: float) -> str:
    """Words whose midpoint falls inside [a, b].

    Midpoint, not overlap: a word (or a fallback segment) belongs to exactly one
    window, so a line cannot inherit its neighbour's sentence. Small slack at the
    edges because the timeline is accurate to about a tenth of a second, measured.
    """
    out = []
    for w in words:
        mid = (w["start"] + w["end"]) / 2.0
        if a - 0.25 <= mid <= b + 0.25:
            out.append(w["text"])
    return " ".join(out)


def verify(project: str, model_size: str = "small") -> int:
    """Returns the number of lines that failed. 0 = the render says what the
    draft says."""
    pdir = config.project_dir(project)
    final = pdir / "final.mp4"
    tl_path = pdir / "timeline.json"
    draft_path = pdir / "draft.json"

    for p, what in ((final, "final.mp4 - render first"),
                    (tl_path, "timeline.json - re-render to produce it"),
                    (draft_path, "draft.json")):
        if not p.exists():
            console.print(f"[red]missing {p.name}[/] ({what})")
            return -1

    timeline = json.load(io.open(tl_path, encoding="utf-8-sig"))["lines"]
    lines = json.load(io.open(draft_path, encoding="utf-8-sig"))["lines"]
    by_id = {str(l.get("id")): (l.get("narration") or "") for l in lines}

    wav = _extract_audio(final)
    words = _transcribe(wav, model_size)
    try:
        wav.unlink()
    except Exception:
        pass
    if words is None:
        return -1

    bad, suspect, checked = [], [], 0
    for t in timeline:
        lid = str(t.get("id"))
        want = by_id.get(lid)
        if not want:
            continue
        heard = _text_in_window(words, t["out_start"], t["out_end"])
        if not heard.strip():
            bad.append((lid, t["out_start"], 0.0, want, "(silence)"))
            continue
        checked += 1
        ratio = SequenceMatcher(None, _norm(want), _norm(heard)).ratio()
        if ratio < MATCH_FLOOR:
            bad.append((lid, t["out_start"], ratio, want, heard))
        elif ratio < SUSPECT_FLOOR:
            suspect.append((lid, t["out_start"], ratio, want, heard))

    def ms(s):
        return f"{int(s)//60:02d}:{int(s)%60:02d}"

    console.print()
    console.print(f"[bold][RENDER-VERIFY][/] compared {checked} line(s) of "
                  f"rendered audio against draft.json")

    for lid, at, ratio, want, heard in bad:
        console.print(f"[red]  MISMATCH line {lid} at {ms(at)} "
                      f"(similarity {ratio:.2f})[/]")
        console.print(f"      draft says : {want[:100]}")
        console.print(f"      audio says : {heard.strip()[:100]}")
    for lid, at, ratio, want, heard in suspect:
        console.print(f"[yellow]  worth a look: line {lid} at {ms(at)} "
                      f"(similarity {ratio:.2f})[/]")
        console.print(f"      draft says : {want[:90]}")
        console.print(f"      audio says : {heard.strip()[:90]}")

    if not bad and not suspect:
        console.print("[green]  every line is saying what the draft says it should.[/]")
    console.print("[dim]  This checks the WORDS only. Whether the picture matches "
                  "them is drift - still needs your eyes (RULES.md Part F).[/]")
    return len(bad)
