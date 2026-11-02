# -*- coding: utf-8 -*-
"""The intro montage's EDIT STYLE: how it is cut, and which footage it uses.

WHY
---
The montage always cut on every music onset, chronologically spread footage,
hard cuts. That is right for an energetic track and wrong for a ballad, a
thriller or a comedy. A style is now a set of parameters:

  shots       (min, max) shot length in seconds
  transition  cut | dissolve | dip (to black), and its length
  align       onset (every onset) | bar (bars / phrases) | strong (only the
              strongest hits)
  pacing      steady | build (shots shorten from max to min into the drop -
              the cut rate RISES across the intro)
  select      a shot-selection PROFILE: what footage it prefers and in what
              order (see PROFILES)

and eight presets ship below. `energetic` is today's montage, byte for byte:
it takes the legacy code path for cuts AND footage (see the note at
PROFILES['energetic'] for the one switch, config.INTRO_ENERGETIC_PROFILE).

CHOOSING (choose()): an explicit `intro_style` in draft.json wins. Otherwise
the intro music's measured features give AROUSAL (onset density, tempo,
loudness) and VALENCE (major/minor); the tone words of angle.md pick the
genre among the presets that fit that arousal. Every decision is returned as
a list of reasons and printed.

THRESHOLDS (calibrated - tools/test_intro_style.py; HIGH_* / LOW_* below):
  high arousal  onset density >= 1.3 /s AND brightness >= 1500 Hz
  low arousal   onset density < 1.0 /s OR brightness < 1000 Hz
  else          mid (mode decides: major -> energetic, minor -> suspense)
  Measured on the synthetic fixtures (tools/intro_music_fixtures.py):
    140-BPM drums  1.55 /s, 2533 Hz -> high -> energetic
    110-BPM drums  1.38 /s, 2532 Hz -> high
    66-BPM ballad  0.93 /s,  282 Hz -> low  -> emotional
    80-BPM ballad  0.83 /s,  282 Hz -> low
  The onset detector spaces onsets >= MIN_CUT_SEC (0.55s) apart, so density
  tops out near 1.8 /s - a bar near that is unreachable. TEMPO is measured
  and logged but NOT used: on sustained, non-percussive music the
  autocorrelation reads harmonics (the ballads measured 143-184 BPM).
  tokyodrift2006/intro_music.mp3 must classify high -> energetic; that case
  runs where the file exists (the owner's laptop) and prints NOT RUN here.

NOTHING FILM-SPECIFIC LIVES HERE: the lexicons are general English.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import config

# --------------------------------------------------------------------------- #
# presets
# --------------------------------------------------------------------------- #
PRESETS = {
    "energetic": {"shots": (0.55, None), "transition": "cut", "trans_sec": 0.0,
                  "align": "onset", "pacing": "steady", "legacy": True},
    "emotional": {"shots": (2.0, 4.5), "transition": "dissolve",
                  "trans_sec": 0.5, "align": "bar", "pacing": "steady"},
    "suspense":  {"shots": (1.6, 3.5), "transition": "dip", "trans_sec": 0.25,
                  "align": "strong", "pacing": "build"},
    "mystery":   {"shots": (1.4, 3.0), "transition": "dissolve",
                  "trans_sec": 0.35, "align": "strong", "pacing": "steady"},
    "horror":    {"shots": (1.2, 4.0), "transition": "dip", "trans_sec": 0.3,
                  "align": "strong", "pacing": "build"},
    "comedy":    {"shots": (0.8, 2.2), "transition": "cut", "trans_sec": 0.0,
                  "align": "bar", "pacing": "steady"},
    "epic":      {"shots": (0.7, 3.5), "transition": "cut", "trans_sec": 0.0,
                  "align": "bar", "pacing": "build"},
    "romance":   {"shots": (2.0, 4.0), "transition": "dissolve",
                  "trans_sec": 0.6, "align": "bar", "pacing": "steady"},
}

XFADE = {"dissolve": "fade", "dip": "fadeblack"}

# --------------------------------------------------------------------------- #
# music features
# --------------------------------------------------------------------------- #
_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def music_features(path: Path, max_sec: float = 60.0) -> dict:
    """{density, tempo, loudness_db, brightness_hz, mode, mode_strength}."""
    import numpy as np
    from pipeline import intro as I
    x = I._decode_mono(path)[: int(max_sec * I.SR)]
    dur = max(1e-6, len(x) / I.SR)
    onsets = I.detect_beats(path, max_sec)
    rms = float(np.sqrt(np.mean(x ** 2) + 1e-12))
    loud = 20.0 * np.log10(rms + 1e-12)
    # tempo from the autocorrelation of the onset envelope, 60-180 BPM
    env = I._flux(x)
    tempo = 0.0
    if env.size > 64 and env.std() > 0:
        e = (env - env.mean()) / (env.std() + 1e-9)
        ac = np.correlate(e, e, mode="full")[e.size - 1:]
        fps = I.SR / I.HOP
        lo, hi = int(fps * 60 / 180), int(fps * 60 / 60)
        if hi < ac.size:
            lag = lo + int(np.argmax(ac[lo:hi]))
            # octave check: a beat at 140 BPM also correlates at 70 BPM. If
            # half the lag is nearly as strong, the faster reading is the beat.
            half = lag // 2
            if half >= lo and ac[half] >= 0.6 * ac[lag]:
                lag = half
            tempo = 60.0 * fps / max(1, lag)
    # brightness + chroma from a few long frames
    n = 4096
    cents, chroma = [], np.zeros(12)
    freqs = np.fft.rfftfreq(n, 1.0 / I.SR)
    valid = freqs > 30
    pcs = (np.round(12 * np.log2(freqs[valid] / 440.0)) + 9) % 12
    for i in range(0, max(1, len(x) - n), n):
        mag = np.abs(np.fft.rfft(x[i:i + n] * np.hanning(n)))
        if mag.sum() <= 0:
            continue
        cents.append(float((freqs * mag).sum() / mag.sum()))
        m = mag[valid]
        for pc in range(12):
            chroma[pc] += m[pcs == pc].sum()
    mode, strength = "unknown", 0.0
    if chroma.sum() > 0:
        best = (-2.0, "unknown")
        for k in range(12):
            for name, prof in (("major", _MAJOR), ("minor", _MINOR)):
                r = float(np.corrcoef(chroma, np.roll(prof, k))[0, 1])
                best = max(best, (r, name))
        strength, mode = best
    return {"density": round(len(onsets) / dur, 3), "tempo": round(tempo, 1),
            "loudness_db": round(loud, 1),
            "brightness_hz": round(float(np.mean(cents)) if cents else 0.0, 1),
            "mode": mode, "mode_strength": round(strength, 3),
            "onsets": len(onsets), "seconds": round(dur, 2)}


# Thresholds - see the module docstring for the measurements behind them.
HIGH_DENSITY = 1.3        # onsets/s (the detector caps at 1/MIN_CUT_SEC ~1.8)
HIGH_BRIGHT_HZ = 1500.0   # mean spectral centroid
LOW_DENSITY = 1.0
LOW_BRIGHT_HZ = 1000.0


def arousal(f: dict) -> tuple:
    d, br = f["density"], f["brightness_hz"]
    if d >= HIGH_DENSITY and br >= HIGH_BRIGHT_HZ:
        return "high", (f"onset density {d}/s >= {HIGH_DENSITY} and "
                        f"brightness {br} Hz >= {HIGH_BRIGHT_HZ:.0f}")
    if d < LOW_DENSITY or br < LOW_BRIGHT_HZ:
        return "low", (f"onset density {d}/s < {LOW_DENSITY} or brightness "
                       f"{br} Hz < {LOW_BRIGHT_HZ:.0f}")
    return "mid", f"onset density {d}/s, brightness {br} Hz (between the bars)"


# --------------------------------------------------------------------------- #
# tone from angle.md
# --------------------------------------------------------------------------- #
TONE_WORDS = {
    "comedy": ("comedy", "comic", "funny", "laugh", "laughs", "joke", "jokes",
               "absurd", "slapstick", "farce", "hilarious"),
    "horror": ("horror", "terror", "dread", "haunted", "haunting", "monster",
               "scream", "nightmare", "gore"),
    "mystery": ("mystery", "secret", "secrets", "whodunit", "clue", "clues",
                "puzzle", "who killed", "conspiracy"),
    "romance": ("romance", "romantic", "love story", "falls in love",
                "lovers", "courtship", "heartbreak"),
    "epic": ("epic", "war", "wars", "battle", "battles", "empire", "kingdom",
             "saga", "army", "legend", "legendary"),
    "suspense": ("suspense", "thriller", "tension", "hunted", "stalked",
                 "stalking", "manhunt", "ticking"),
}


def angle_tone(pdir: Path) -> tuple:
    """(genre or None, counts) from angle.md's ANGLE, ATTITUDE and persona."""
    p = Path(pdir) / "angle.md"
    if not p.exists():
        return None, {}
    txt = p.read_text(encoding="utf-8-sig").lower()
    keep = []
    for head in ("ANGLE", "ATTITUDE TO CHARACTERS", "NARRATOR PERSONA"):
        m = re.search(rf"^##\s+{head.lower()}\s*$(.*?)(?=^##\s|\Z)", txt,
                      re.M | re.S)
        if m:
            keep.append(m.group(1))
    body = "\n".join(keep) or txt
    # WHOLE words: a prefix match counted "war" in "toward" and "warm"
    counts = {g: sum(len(re.findall(rf"\b{re.escape(w)}\b", body)) for w in ws)
              for g, ws in TONE_WORDS.items()}
    g = max(counts, key=lambda k: counts[k])
    return (g if counts[g] >= 2 else None), counts


# which presets each arousal level allows, and the default for each mode
FITS = {
    "high": {"default": "energetic",
             "genres": ("epic", "comedy", "horror", "suspense")},
    "mid":  {"default": {"major": "energetic", "minor": "suspense",
                         "unknown": "energetic"},
             "genres": ("comedy", "epic", "romance", "mystery", "suspense",
                        "horror")},
    # a slow, soft track is emotional unless the angle names a darker genre;
    # mode is NOT used here: the measured major/minor reading is not reliable
    # enough on sustained chords (C-Am-F-G read as A minor)
    "low":  {"default": {"major": "emotional", "minor": "emotional",
                         "unknown": "emotional"},
             "genres": ("romance", "mystery", "horror", "suspense")},
}


def choose(project: str, music: Path | None) -> tuple:
    """(preset name, [reasons]). Never raises: an unreadable input becomes
    a stated reason and the legacy energetic montage."""
    pdir = config.project_dir(project)
    why = []
    try:
        d = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
        ov = d.get("intro_style")
    except (OSError, ValueError):
        ov = None
    if ov:
        if ov in PRESETS:
            return ov, [f"draft.json sets intro_style = {ov!r} (explicit "
                        f"override wins)"]
        why.append(f"draft.json intro_style {ov!r} is not a preset "
                   f"({', '.join(PRESETS)}) - ignored")
    if music is None:
        return "energetic", why + ["no intro music to measure - legacy style"]
    try:
        f = music_features(music)
    except Exception as e:
        return "energetic", why + [f"music features could not be measured "
                                   f"({type(e).__name__}: {e}) - legacy style"]
    ar, awhy = arousal(f)
    why.append(f"music: {awhy}; mode {f['mode']} "
               f"(r={f['mode_strength']}), brightness {f['brightness_hz']} Hz")
    tone, counts = angle_tone(pdir)
    fit = FITS[ar]
    if tone and tone in fit["genres"]:
        why.append(f"angle.md tone: {tone} ({counts[tone]} tone word(s)) "
                   f"fits {ar} arousal")
        return tone, why
    if tone:
        why.append(f"angle.md tone {tone} does not fit {ar} arousal - "
                   f"music decides")
    dflt = fit["default"]
    pick = dflt if isinstance(dflt, str) else dflt.get(f["mode"], "energetic")
    why.append(f"{ar} arousal, {f['mode']} -> {pick}")
    return pick, why


# --------------------------------------------------------------------------- #
# cut planning
# --------------------------------------------------------------------------- #
def legacy_slots(beats: list, total: float) -> list:
    """Today's montage: a cut on every onset. Kept verbatim for energetic."""
    cuts = [0.0] + [b for b in beats if 0.2 < b < total - 0.3] + [total]
    return [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)
            if cuts[i + 1] - cuts[i] >= 0.25]


def plan_slots(onsets: list, total: float, drop: float, style: dict) -> list:
    """[(a, b)] slots for a non-legacy style. `onsets` = [(t, strength)]."""
    import statistics
    lo, hi = style["shots"]
    hi = hi or max(lo * 4, 2.0)
    times = [t for t, _s in onsets]
    if style["align"] == "strong" and onsets:
        qs = sorted(s for _t, s in onsets)
        bar = qs[int(0.7 * (len(qs) - 1))]
        times = [t for t, s in onsets if s >= bar]
    period = 0.5
    if len(times) >= 3:
        period = min(1.2, max(0.3, statistics.median(
            b - a for a, b in zip(times, times[1:]))))
    barlen = 4 * period
    span = max(drop, total * 0.6, 1.0)

    def target(t):
        if style["pacing"] == "build":
            k = min(1.0, t / span)
            return hi - (hi - lo) * k
        if style["align"] == "bar":
            n = max(1, round(lo / barlen + 0.49))
            return min(hi, max(lo, n * barlen))
        return lo

    cuts, t = [0.0], 0.0
    while total - t > lo * 0.75 + 0.3:
        want = target(t)
        cand = [c for c in times if c - t >= want - 0.05 and c - t <= hi
                and c < total - 0.3]
        nxt = cand[0] if cand else min(t + want, total)
        if total - nxt < lo * 0.6:
            break
        cuts.append(round(nxt, 3))
        t = nxt
    cuts.append(total)
    return [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)
            if cuts[i + 1] - cuts[i] >= 0.25]


# --------------------------------------------------------------------------- #
# shot selection profiles
# --------------------------------------------------------------------------- #
LEX = {
    "vehicle": ("car", "cars", "race", "racing", "drift", "engine", "tyre",
                "tire", "motorcycle", "truck", "chase", "speed", "wheel"),
    "fight": ("fight", "punch", "kick", "brawl", "shoot", "gun", "attack",
              "struggle", "hits", "swing"),
    "blast": ("explosion", "explode", "fire", "flame", "crash", "smash",
              "burning", "detonat"),
    "face": ("face", "close-up", "close up", "closeup", "eyes", "expression",
             "tears", "cries", "smiles"),
    "embrace": ("hug", "embrace", "holds her", "holds him", "kiss", "hand in"),
    "family": ("mother", "father", "mum", "mom", "dad", "son", "daughter",
               "family", "brother", "sister", "grand"),
    "quiet": ("quiet", "silent", "silence", "still", "sits", "waits", "alone"),
    "dark": ("dark", "shadow", "night", "dim", "black"),
    "object": ("door", "key", "phone", "letter", "photo", "knife", "window",
               "eyes", "envelope"),
    "lone": ("alone", "lone", "by himself", "by herself", "solitary", "single"),
    "empty": ("empty", "deserted", "corridor", "hallway", "abandoned"),
    "fear": ("fear", "scream", "terror", "horrified", "panic", "flinch",
             "startled", "recoils", "afraid"),
    "reaction": ("reacts", "reaction", "stares", "grins", "laughs", "shocked",
                 "rolls his eyes", "double-take", "gapes", "smirks"),
    "absurd": ("absurd", "ridiculous", "awkward", "clumsy", "falls", "slips",
               "embarrass", "pratfall"),
    "wide": ("wide", "aerial", "skyline", "city", "crowd", "landscape",
             "panorama", "stadium", "rooftop"),
    "hero": ("stands", "raises", "triumph", "victory", "wins", "cheers",
             "salute", "strides"),
    "couple": ("each other", "eyes meet", "smiles at", "together", "dance",
               "kiss", "leans in"),
    "warm": ("laugh", "smile", "warm", "sunset", "gentle", "tender"),
}

# weights per feature; "order": how the picked shots are sequenced
PROFILES = {
    # NOTE: energetic is the LEGACY spread selection by default, so today's
    # montage stays byte-identical. Set config.INTRO_ENERGETIC_PROFILE = True
    # to use this profile instead.
    "energetic": {"w": {"motion": 3, "vehicle": 2, "fight": 2, "blast": 3,
                        "d:action": 2, "k:action": 1, "quiet": -1},
                  "order": "rising"},
    "emotional": {"w": {"main_cast": 2, "face": 2, "embrace": 3, "family": 2,
                        "quiet": 2, "still": 2, "d:emotion": 2,
                        "k:emotion": 2, "a:emotional": 3, "motion": -1,
                        "fight": -2, "blast": -2},
                  "order": "chrono"},
    "suspense": {"w": {"dark": 2, "darkness": 2, "object": 2, "lone": 2,
                       "still": 1, "d:setup": 1, "blast": -2, "warm": -1},
                 "order": "chrono"},
    "mystery": {"w": {"object": 2, "dark": 1, "darkness": 1, "lone": 1,
                      "face": 1, "d:setup": 1, "d:establishing": 1},
                "order": "chrono", "exclude_reveal_chars": True},
    "horror": {"w": {"empty": 3, "dark": 2, "darkness": 2, "fear": 3,
                     "lone": 1, "warm": -2},
               "order": "chrono"},
    "comedy": {"w": {"reaction": 3, "absurd": 3, "face": 1,
                     "d:reaction": 2, "fear": -1, "blast": -1},
               "order": "chrono"},
    "epic": {"w": {"wide": 3, "hero": 2, "crowd": 2, "motion": 1,
                   "d:establishing": 1, "blast": 1},
             "order": "small_to_big"},
    "romance": {"w": {"couple": 3, "warm": 2, "face": 1, "embrace": 2,
                      "d:emotion": 1, "fight": -2, "blast": -2},
                "order": "chrono"},
}


def _has(text: str, words) -> int:
    return sum(1 for w in words if w in text)


def shot_features(s: dict, main_cast: set, beat_kind: str = "",
                  anchor_kind: str = "", motion=None, luma=None) -> dict:
    """Features of one catalogued shot, all from data the project has."""
    act = " " + str(s.get("action") or "").lower() + " "
    chars = [str(c) for c in s.get("chars") or []]
    f = {k: min(2, _has(act, ws)) for k, ws in LEX.items()}
    f["main_cast"] = min(2, sum(1 for c in chars if c in main_cast))
    f["crowd"] = 1 if len(chars) >= 4 or "crowd" in act else 0
    for d in s.get("depicts") or []:
        f[f"d:{d}"] = 1
    if beat_kind:
        f[f"k:{beat_kind}"] = 1
    if "emotional" in anchor_kind:
        f["a:emotional"] = 1
    if motion is not None:
        # frame difference in luma levels: ~0-2 still, 6+ busy
        f["motion"] = round(min(3.0, motion / 3.0), 2)
        f["still"] = 1 if motion < 2.0 else 0
    if luma is not None:
        f["darkness"] = round(max(0.0, (60.0 - luma) / 30.0), 2)
    return f


def score(f: dict, profile: str) -> tuple:
    """(score, top contributions) - the reason a shot was picked."""
    w = PROFILES[profile]["w"]
    parts = [(k, f.get(k, 0) * wt) for k, wt in w.items() if f.get(k)]
    return round(sum(v for _k, v in parts), 2), sorted(
        parts, key=lambda kv: -abs(kv[1]))[:3]


def select(cands: list, n: int, profile: str, exclude: set | None = None,
           log=None) -> list:
    """Pick `n` shots for a profile from pre-filtered candidates.

    `cands` = [{"a", "b", "shot", "f"}] - already free of reveal, flagged and
    story-bound footage (intro.usable_moments). `exclude` = lowercased names
    that must never appear (mystery: the reveal-critical characters).
    Returns [(a, b)] in the profile's order."""
    prof = PROFILES[profile]
    pool = []
    for c in cands:
        if prof.get("exclude_reveal_chars") and exclude:
            blob = (" ".join(c["shot"].get("chars") or []) + " "
                    + str(c["shot"].get("action") or "")).lower()
            if any(x in blob for x in exclude):
                continue
            if set(c["shot"].get("depicts") or []) & {"reveal", "discovery"}:
                continue
        sc, why = score(c["f"], profile)
        pool.append((sc, c, why))
    pool.sort(key=lambda t: (-t[0], t[1]["a"]))
    picked = pool[:n]
    if prof["order"] == "rising":
        picked.sort(key=lambda t: (t[0], t[1]["a"]))
    elif prof["order"] == "small_to_big":
        picked.sort(key=lambda t: (t[1]["f"].get("wide", 0)
                                   + t[1]["f"].get("crowd", 0), t[0],
                                   t[1]["a"]))
    else:
        picked.sort(key=lambda t: t[1]["a"])
    if log:
        for sc, c, why in picked:
            log(f"    {c['a']:8.1f}s  score {sc:5.1f}  "
                + ", ".join(f"{k} {v:+g}" for k, v in why)
                + f"  | {str(c['shot'].get('action') or '')[:70]}")
    return [(c["a"], c["b"]) for _sc, c, _w in picked]
