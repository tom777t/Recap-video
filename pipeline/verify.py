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


# --------------------------------------------------------------------------- #
# Orthography canonicalisation - deliberately NARROW.
#
# Whisper writes "25-year-old" where the draft writes "twenty-five-year-old",
# and "license" where the draft writes "licence". Both scored as mismatches
# (0.31 and 0.62) on renders that were word-perfect, which trains you to ignore
# this gate - the expensive failure mode for a gate whose whole job is to be
# believed.
#
# The safety property is that every rule below is a ONE-TO-ONE token rewrite
# applied IDENTICALLY to both sides. Nothing is deleted, nothing is fuzzy-
# matched, and no rule can bring two different words together. A line playing
# the wrong audio still scores ~0.1, because canonicalising spelling does not
# make one sentence resemble another.
#
# Names are deliberately NOT normalised. "TTS mangling a name badly enough to
# change it" is a failure this gate exists to catch, so Fogell/Fogel must stay
# visible as a difference.
# --------------------------------------------------------------------------- #
# Numerals canonicalise to WORDS, not to digits, and the direction matters.
# Folding "twenty five" -> "25" shortens the only part of the string that
# differs when a number is WRONG, so difflib scores the error as more similar:
# measured, "twenty-five years old" vs "forty-seven years old" went 0.78 -> 0.89
# and slid past the suspect floor. Expanding "25" -> "twenty five" keeps the
# differing region full length, so a wrong number stays as visible as it was
# (and 25-vs-47 in digits actually gets easier to catch, 0.89 -> 0.78).
_ONES_W = ["zero", "one", "two", "three", "four", "five", "six", "seven",
           "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
           "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS_W = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty",
           7: "seventy", 8: "eighty", 9: "ninety"}


def _num_to_words(n: int):
    """0-99 only. Bigger numbers are left as digits: years ('1954' is spoken
    'nineteen fifty-four', not 'one thousand...') and any long figure would need
    guesswork about how it was read aloud, and guesswork is how a normaliser
    starts excusing things."""
    if 0 <= n < 20:
        return [_ONES_W[n]]
    if 20 <= n < 100:
        t, u = divmod(n, 10)
        return [_TENS_W[t]] + ([_ONES_W[u]] if u else [])
    return None

# British -> American, exact tokens only. No -our/-ise wildcards: a blanket
# suffix rule would rewrite words it was never shown and could collide.
_SPELLING = {
    "licence": "license", "defence": "defense", "offence": "offense",
    "practise": "practice", "pretence": "pretense",
    "colour": "color", "honour": "honor", "favour": "favor",
    "neighbour": "neighbor", "behaviour": "behavior", "rumour": "rumor",
    "realise": "realize", "realised": "realized", "recognise": "recognize",
    "recognised": "recognized", "apologise": "apologize",
    "organise": "organize", "organised": "organized",
    "travelling": "traveling", "travelled": "traveled",
    "cancelled": "canceled", "grey": "gray",
    "theatre": "theater", "centre": "center", "metre": "meter",
    "litre": "liter", "storey": "story", "plough": "plow",
    "aeroplane": "airplane", "moustache": "mustache", "kerb": "curb",
}


def _canon_tokens(tokens: list) -> list:
    """Digits 0-99 -> number words, British -> American. Token-for-token.

    Number words already written as words are left alone: stripping the hyphen
    in "twenty-five-year-old" is done by _norm, so both sides meet at the same
    word sequence without either being compressed.
    """
    out = []
    for t in tokens:
        if t.isdigit() and len(t) <= 2:
            words = _num_to_words(int(t))
            out.extend(words if words else [t])
        else:
            out.append(_SPELLING.get(t, t))
    return out


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return " ".join(_canon_tokens(s.split()))


def _extract_audio(mp4: Path) -> Path:
    wav = mp4.with_name("_verify16k.wav")
    cmd = [config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(mp4), "-vn", "-ac", "1", "-ar", "16000", str(wav)]
    subprocess.run(cmd, check=True)
    return wav


def _load_model(model_size: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        console.print("[red]faster-whisper not installed.[/] pip install -r requirements.txt")
        return None
    return WhisperModel(model_size, device="cpu", compute_type="int8")


def _transcribe_words(wmodel, path: Path) -> list:
    # WORD timestamps, not segment timestamps. A Whisper segment runs 10-15s and
    # routinely straddles two of our lines; pulling in whole overlapping segments
    # made every window inherit the previous line's sentence, which looked exactly
    # like a systematic render fault and was not one.
    segs, _info = wmodel.transcribe(str(path), beam_size=1, vad_filter=False,
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


def _transcribe(wav: Path, model_size: str):
    wmodel = _load_model(model_size)
    if wmodel is None:
        return None
    console.print(f"Transcribing the rendered audio with '{model_size}'...")
    return _transcribe_words(wmodel, wav)


EDGE_SLACK = 0.25

# A line is UNMEASURED when too little of it reached the comparison to support
# any verdict. Two independent ways that happens:
#   - the ASR supplied words for only part of the window (timing/window loss)
#   - the ASR supplied words across the window but far too few of them, which is
#     what a music bed does to a quiet or fast line
MIN_AUDIO_COVERAGE = 0.75    # fraction of the window ASR gave words for
MIN_WORD_RATIO = 0.60        # heard words / drafted words

# Audio coverage is only meaningful once the window is long enough for speech
# to dominate it. A 4-word line ("So he hits him.") gets a 1.78s window, most of
# which is the TTS file's trailing silence, so coverage reads 0.36 however
# perfectly the line was transcribed - measured: that line scores similarity
# 1.00 and would still have been branded UNMEASURED. Short windows are judged on
# word ratio alone, which is the signal that actually degrades when a line is
# lost. A short line that produced NO words never reaches here - an empty window
# is a MISMATCH, not an unmeasured one.
MIN_WINDOW_FOR_COVERAGE = 3.0   # seconds


def _window_words(words, a: float, b: float) -> list:
    """Words whose midpoint falls inside [a, b].

    Midpoint, not overlap: a word (or a fallback segment) belongs to exactly one
    window, so a line cannot inherit its neighbour's sentence. Small slack at the
    edges because the timeline is accurate to about a tenth of a second, measured.
    """
    return [w for w in words
            if a - EDGE_SLACK <= (w["start"] + w["end"]) / 2.0 <= b + EDGE_SLACK]


def _text_in_window(words, a: float, b: float) -> str:
    return " ".join(w["text"] for w in _window_words(words, a, b))


def _audio_coverage(inside: list, a: float, b: float) -> float:
    """How much of the window [a, b] the ASR actually supplied words for.

    This is the measurement the module previously did not have. Without it,
    verify compares whatever text happened to land in the window and returns a
    verdict on it - so a line where only a third arrived scored as a mismatch,
    indistinguishable from a line that genuinely said the wrong thing. Those are
    different states and only one of them is a finding.
    """
    span = b - a
    if span <= 0 or not inside:
        return 0.0
    lo = max(a, min(w["start"] for w in inside))
    hi = min(b, max(w["end"] for w in inside))
    return max(0.0, min(1.0, (hi - lo) / span))


def _classify(want: str, heard: str, cov: float, window_dur: float) -> tuple:
    """(verdict, similarity, coverage, word_ratio). Shared by both passes so the
    escalated read is judged by exactly the same rules as the first one."""
    want_n, heard_n = _norm(want), _norm(heard)
    if not heard_n.strip():
        return "MISMATCH", 0.0, cov, 0.0
    word_ratio = len(heard_n.split()) / max(1, len(want_n.split()))
    ratio = SequenceMatcher(None, want_n, heard_n).ratio()
    # Measurability is decided BEFORE similarity, so a low score can never be
    # laundered into "unmeasured" and a high score can never hide the fact that
    # most of the line never arrived.
    if ((window_dur >= MIN_WINDOW_FOR_COVERAGE and cov < MIN_AUDIO_COVERAGE)
            or word_ratio < MIN_WORD_RATIO):
        return "UNMEASURED", ratio, cov, word_ratio
    if ratio < MATCH_FLOOR:
        return "MISMATCH", ratio, cov, word_ratio
    if ratio < SUSPECT_FLOOR:
        return "SUSPECT", ratio, cov, word_ratio
    return "OK", ratio, cov, word_ratio


def _reread_window(wmodel, final: Path, a: float, b: float):
    """Transcribe ONE line's window on its own. Returns (heard, coverage).

    The whole-film pass assembles a line's text out of a single long-form
    transcription, which degrades it two ways: the ASR mis-hears across segment
    joins, and consecutive windows overlap (the next line starts GAP-XFADE =
    0.10s before this one's window ends, plus EDGE_SLACK either side), so a line
    inherits its neighbour's opening words. Measured on two finished films, that
    cost up to 0.5 similarity on lines that were rendered perfectly.

    Reading the window alone removes both. It is 2.4-3.7x the runtime applied to
    every line, which is why it is applied only to lines already flagged.
    """
    cut = final.with_name("_verify_slot.wav")
    try:
        subprocess.run([config.ffmpeg(), "-v", "error", "-y",
                        "-ss", f"{a:.3f}", "-i", str(final),
                        "-t", f"{max(0.05, b - a):.3f}",
                        "-vn", "-ac", "1", "-ar", "16000", str(cut)], check=True)
        ws = _transcribe_words(wmodel, cut)
    except Exception:
        return None
    finally:
        try:
            cut.unlink()
        except Exception:
            pass
    heard = " ".join(w["text"] for w in ws)
    cov = _audio_coverage(ws, 0.0, b - a) if ws else 0.0
    return heard, cov


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
            return {"error": f"missing {p.name}", "failed": 0,
                    "unmeasured": 0, "checked": 0, "total": 0}

    timeline = json.load(io.open(tl_path, encoding="utf-8-sig"))["lines"]
    lines = json.load(io.open(draft_path, encoding="utf-8-sig"))["lines"]
    by_id = {str(l.get("id")): (l.get("narration") or "") for l in lines}

    wmodel = _load_model(model_size)
    if wmodel is None:
        return {"error": "transcription unavailable", "failed": 0,
                "unmeasured": 0, "checked": 0, "total": 0}
    console.print(f"Transcribing the rendered audio with '{model_size}'...")
    wav = _extract_audio(final)
    try:
        words = _transcribe_words(wmodel, wav)
    finally:
        try:
            wav.unlink()
        except Exception:
            pass

    # ---- pass 1: whole-film transcription, assembled per window --------------
    recs = []
    for t in timeline:
        lid = str(t.get("id"))
        want = by_id.get(lid)
        if not want:
            continue
        a, b = float(t["out_start"]), float(t["out_end"])
        inside = _window_words(words, a, b)
        heard = " ".join(w["text"] for w in inside)
        cov = _audio_coverage(inside, a, b)
        verdict, ratio, cov, wr = _classify(want, heard, cov, b - a)
        recs.append({"id": lid, "a": a, "b": b, "want": want, "heard": heard,
                     "verdict": verdict, "sim": ratio, "cov": cov, "wr": wr,
                     "escalated": False, "was": None})

    # ---- pass 2: ONE re-read for anything not already clean ------------------
    # Ceiling is deliberate and hard: a line is re-read at most once. If the
    # second read still lands below the floor, that verdict is final - it is not
    # re-escalated, not averaged with the first read, and not softened. The
    # cheapest way for a gate to start excusing things is to let it retry until
    # it likes the answer.
    flagged = [r for r in recs if r["verdict"] != "OK"]
    escalations = []
    if flagged:
        console.print(f"[cyan]Escalating {len(flagged)} flagged line(s) to a "
                      f"single-window re-read...[/]")
    for r in flagged:
        got = _reread_window(wmodel, final, r["a"], r["b"])
        if got is None:
            r["reread_failed"] = True
            continue
        heard2, cov2 = got
        v2, sim2, cov2, wr2 = _classify(r["want"], heard2, cov2, r["b"] - r["a"])
        cleared = (v2 == "OK")
        escalations.append({
            "id": r["id"], "at": r["a"],
            "from": r["verdict"], "to": v2, "cleared": cleared,
            "sim_from": r["sim"], "sim_to": sim2,
            "cov_from": r["cov"], "cov_to": cov2,
        })
        r["escalated"] = True
        if cleared:
            r.update({"was": {"verdict": r["verdict"], "sim": r["sim"],
                              "heard": r["heard"]},
                      "verdict": "OK", "sim": sim2, "cov": cov2, "wr": wr2,
                      "heard": heard2})
        else:
            # The re-read may ONLY clear a line. It may not reclassify one
            # finding as a different, milder one. Tested: a re-read that came
            # back with the wrong words returned only 28% of the expected word
            # count, which tripped the word-ratio rule and turned a MISMATCH
            # into UNMEASURED - dropping the failure count from 1 to 0 and the
            # exit code from 1 to 2. A gate that can talk itself out of its own
            # findings on the second look is worse than one that never looks
            # twice. The first-pass verdict stands; the re-read is reported.
            r["reread"] = {"verdict": v2, "sim": sim2, "heard": heard2}

    bad = [(r["id"], r["a"], r["sim"], r["want"], r["heard"] or "(silence)", r["cov"])
           for r in recs if r["verdict"] == "MISMATCH"]
    suspect = [(r["id"], r["a"], r["sim"], r["want"], r["heard"], r["cov"])
               for r in recs if r["verdict"] == "SUSPECT"]
    unmeasured = [(r["id"], r["a"], r["sim"], r["want"], r["heard"], r["cov"], r["wr"])
                  for r in recs if r["verdict"] == "UNMEASURED"]
    checked = sum(1 for r in recs if r["verdict"] != "UNMEASURED")

    def ms(s):
        return f"{int(s)//60:02d}:{int(s)%60:02d}"

    total = checked + len(unmeasured)
    console.print()
    console.print(f"[bold][RENDER-VERIFY][/] {checked} line(s) compared, "
                  f"{len(unmeasured)} unmeasured, of {total} with narration")

    # ---- escalation ledger --------------------------------------------------
    # Every re-read is reported, cleared or not. A gate that quietly upgrades its
    # own findings is a gate that can start excusing real defects with nobody
    # able to see it happening, so there is no silent path through here.
    if escalations:
        console.print(f"[cyan]  [ESCALATED] {len(escalations)} line(s) re-read on "
                      f"their own window (one re-read each, then the verdict "
                      f"stands):[/]")
        for e in escalations:
            if e["cleared"]:
                console.print(f"    [green]line {e['id']} at {ms(e['at'])}: "
                              f"{e['from']} {e['sim_from']:.2f} -> re-read "
                              f"{e['sim_to']:.2f}, cleared[/]")
            else:
                console.print(f"    [red]line {e['id']} at {ms(e['at'])}: "
                              f"{e['from']} {e['sim_from']:.2f} -> re-read "
                              f"{e['sim_to']:.2f} ({e['to']}), did NOT clear - "
                              f"verdict stands as {e['from']}[/]")
    _rrf = [r for r in recs if r.get("reread_failed")]
    if _rrf:
        console.print(f"[yellow]  {len(_rrf)} line(s) could not be re-read "
                      f"(audio cut failed); their first-pass verdict stands: "
                      f"{', '.join(r['id'] for r in _rrf)}[/]")

    for lid, at, ratio, want, heard, cov in bad:
        console.print(f"[red]  MISMATCH line {lid} at {ms(at)} "
                      f"(similarity {ratio:.2f}, read {cov*100:.0f}% of the line)[/]")
        console.print(f"      draft says : {want[:100]}")
        console.print(f"      audio says : {heard.strip()[:100]}")
    for lid, at, ratio, want, heard, cov in suspect:
        console.print(f"[yellow]  worth a look: line {lid} at {ms(at)} "
                      f"(similarity {ratio:.2f}, read {cov*100:.0f}%)[/]")
        console.print(f"      draft says : {want[:90]}")
        console.print(f"      audio says : {heard.strip()[:90]}")

    # UNMEASURED is not a pass and not a failure. Printing it as either is the
    # bug this section exists to prevent.
    for lid, at, ratio, want, heard, cov, wr in unmeasured:
        console.print(f"[magenta]  UNMEASURED line {lid} at {ms(at)} "
                      f"- read {cov*100:.0f}% of the window, "
                      f"{wr*100:.0f}% of the expected words[/]")
        console.print(f"      draft says : {want[:90]}")
        console.print(f"      audio says : {heard.strip()[:90]}")

    if bad or suspect or unmeasured:
        console.print()
    if unmeasured:
        console.print(f"[magenta]  {len(unmeasured)} line(s) could not be checked "
                      f"either way - too little of them reached the comparison. "
                      f"This is not a pass.[/]")
        console.print("[dim]    ASR under a music bed is the usual cause. To settle "
                      "one, listen to the slot in final.mp4 - timeline.json gives "
                      "the timestamp.[/]")
    if not bad and not suspect and not unmeasured:
        console.print("[green]  every line is saying what the draft says it should.[/]")
    elif not bad and not suspect:
        console.print(f"[green]  all {checked} measurable line(s) match the draft.[/]")

    console.print("[dim]  This checks the WORDS only. Whether the picture matches "
                  "them is drift - still needs your eyes (RULES.md Part F).[/]")
    return {"failed": len(bad), "suspect": len(suspect),
            "unmeasured": len(unmeasured), "checked": checked, "total": total,
            "escalated": len(escalations),
            "escalations": escalations,
            "verdicts": {r["id"]: r["verdict"] for r in recs}}
