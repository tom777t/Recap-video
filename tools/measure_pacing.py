"""Measure the PACING CONTOUR of the reference recap channels.

THE QUESTION
------------
The Tokyo Drift draft reads as rushed outside two or three scenes. Measured on
it: 56 of ~80 beats get exactly ONE line, and every 10 film-minutes gets
1.0-1.6 narration-minutes - a flat contour. The scenes viewers singled out
(Han on the footbridge, the Neela beats) are precisely the ones given 3-4
lines.

So: do the reference channels have a flat contour, or do they DWELL? This tool
measures it rather than assuming, because "dwell more on the good bits" is
untestable until there is a number on it.

WHAT A "SCENE" IS IN A TRANSCRIPT, AND WHY THIS IS A PROXY
-----------------------------------------------------------
Our drafts bind every line to a shot window, so a scene is a given. A
reference is just narration over a film we do not have, so scene boundaries
have to be inferred. Two signals, both visible in the text:

  * a TRANSITION cue opening a sentence ("meanwhile", "the next morning",
    "back at the house", "later that night", "at the station") - recap
    narration signals scene changes far more explicitly than screenwriting
    does, because the viewer has no establishing shot to rely on;
  * a PAUSE in the delivery longer than the channel's own typical
    between-sentence gap, which is where the picture usually cuts.

This UNDER-segments: a recap that cuts without signalling reads as one long
scene. Under-segmentation inflates lines-per-scene and shortens the one-line
run, so the two bars derived from it are set with that direction of error in
mind - and the one metric that is robust to it, the share of runtime in the
top 20% of scenes, is the one the main gate leans on.

LANGUAGE
--------
Reported per channel and per language, never pooled. TARGET_WPM was once set
from a Vietnamese channel and applied to English narration, and it was wrong
by 25 WPM. Pacing is more structural than tempo, but the same caution applies:
the bars come from the ENGLISH channels because the output is English, with
the Vietnamese channel reported beside them as a cross-check.

Run:  python tools/measure_pacing.py [--write]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

REF_DIR = os.path.join(ROOT, "references", "voice")

# Sentence-initial transition cues. English and Vietnamese kept apart so a
# Vietnamese transcript is not scored with English cues (which would find none
# and report the whole film as one scene).
CUES_EN = [
    r"meanwhile", r"back (?:at|in|to|home)", r"later(?: that)?",
    r"the (?:next|following) (?:day|morning|night|evening|week)",
    r"that (?:night|evening|morning|afternoon)", r"elsewhere",
    r"soon(?:er)?", r"after(?:wards)?", r"the day (?:after|before)",
    r"at the \w+", r"in the \w+", r"outside", r"inside", r"hours later",
    r"minutes later", r"days later", r"weeks later", r"years later",
    r"on the way", r"when (?:he|she|they) (?:arrives|arrive|gets|get)",
    r"cut to", r"we (?:then )?(?:see|cut)", r"next(?: up)?",
]
CUES_VI = [
    r"trong khi (?:đó|do)", r"lúc này", r"lúc đó", r"sau đó", r"ngay sau",
    r"hôm sau", r"sáng hôm sau", r"tối hôm", r"đêm đó", r"về nhà",
    r"tại \w+", r"ở \w+", r"bên ngoài", r"bên trong", r"ít lâu sau",
    r"một lúc sau", r"nhiều năm sau", r"cùng lúc", r"rồi thì", r"kế tiếp",
    r"quay lại", r"trở lại", r"cuối cùng",
]


def _words_with_times(cues: list) -> list:
    """[(t, word)] - a deduped word stream with a time for every word.

    The rollup dedupe is reused from measure_voice: auto-captions repeat the
    tail of each cue at the head of the next, and naive joining roughly
    doubles the word count.
    """
    out: list = []
    have: list = []
    for s, e, text in cues:
        w = text.split()
        if not w:
            continue
        if not have:
            take = w
        else:
            # longest suffix of `have` that is a prefix of `w`
            k = min(len(have), len(w))
            overlap = 0
            while k > 0:
                if [x.lower() for x in have[-k:]] == [x.lower() for x in w[:k]]:
                    overlap = k
                    break
                k -= 1
            take = w[overlap:]
        if not take:
            continue
        span = max(0.05, float(e) - float(s))
        step = span / len(take)
        for i, word in enumerate(take):
            out.append((float(s) + i * step, word))
        have.extend(take)
        if len(have) > 40:
            have = have[-40:]
    return out


def _sentences(stream: list) -> list:
    """[(start, end, text)] split on sentence-final punctuation."""
    sents: list = []
    cur: list = []
    for t, w in stream:
        cur.append((t, w))
        if re.search(r"[.!?]$", w):
            txt = " ".join(x[1] for x in cur).strip()
            if len(txt.split()) >= 2:
                sents.append((cur[0][0], cur[-1][0], txt))
            cur = []
    if cur:
        txt = " ".join(x[1] for x in cur).strip()
        if len(txt.split()) >= 2:
            sents.append((cur[0][0], cur[-1][0], txt))
    return sents


def _scene_breaks(sents: list, lang: str) -> list:
    """Indices where a new scene starts (0 is always a start)."""
    cues = CUES_VI if lang.startswith("vi") else CUES_EN
    pat = re.compile(r"^\W*(?:" + "|".join(cues) + r")\b", re.I)
    gaps = [sents[i + 1][0] - sents[i][1] for i in range(len(sents) - 1)]
    # a pause is "long" relative to this channel's own rhythm
    big = (statistics.median(gaps) + 2.0 * statistics.pstdev(gaps)
           if len(gaps) > 4 else 1.5)
    breaks = [0]
    for i in range(1, len(sents)):
        by_cue = bool(pat.match(sents[i][2]))
        by_gap = (sents[i][0] - sents[i - 1][1]) >= max(0.8, big)
        if by_cue or by_gap:
            breaks.append(i)
    return breaks, round(big, 2)


def measure_file(path: str) -> dict:
    from measure_voice import parse_vtt
    name = os.path.basename(path)
    lang = "vi" if ".vi-" in name else "en"
    cues = parse_vtt(path)
    stream = _words_with_times(cues)
    sents = _sentences(stream)
    if len(sents) < 20:
        return {"file": name, "lang": lang, "error": "too few sentences"}
    breaks, big_gap = _scene_breaks(sents, lang)
    scenes = []
    for bi, b in enumerate(breaks):
        nxt = breaks[bi + 1] if bi + 1 < len(breaks) else len(sents)
        grp = sents[b:nxt]
        if not grp:
            continue
        scenes.append({"lines": len(grp), "start": grp[0][0],
                       "end": grp[-1][1],
                       "dur": max(0.1, grp[-1][1] - grp[0][0]),
                       "words": sum(len(g[2].split()) for g in grp)})
    if len(scenes) < 8:
        return {"file": name, "lang": lang, "error": "too few scenes"}

    total_dur = sum(s["dur"] for s in scenes)
    counts = sorted(s["lines"] for s in scenes)
    # share of runtime in the TOP 20% of scenes, ranked by their own duration
    by_dur = sorted(scenes, key=lambda s: -s["dur"])
    k = max(1, round(len(scenes) * 0.20))
    top_share = sum(s["dur"] for s in by_dur[:k]) / total_dur
    # ...and by line count, which is the shape the draft gate can control
    by_lines = sorted(scenes, key=lambda s: -s["lines"])
    top_line_share = (sum(s["lines"] for s in by_lines[:k])
                      / sum(s["lines"] for s in scenes))
    # longest run of consecutive ONE-line scenes
    run = best = 0
    for s in scenes:
        if s["lines"] <= 1:
            run += 1
            best = max(best, run)
        else:
            run = 0
    one_share = sum(1 for s in scenes if s["lines"] <= 1) / len(scenes)
    return {
        "file": name, "lang": lang,
        "runtime_min": round(total_dur / 60.0, 2),
        "sentences": len(sents),
        "scenes": len(scenes),
        "lines_per_scene_mean": round(statistics.mean(counts), 2),
        "lines_per_scene_median": counts[len(counts) // 2],
        "lines_per_scene_p90": counts[int(len(counts) * 0.9)],
        "lines_per_scene_max": counts[-1],
        "one_line_scene_share": round(one_share, 3),
        "longest_one_line_run": best,
        "top20_runtime_share": round(top_share, 3),
        "top20_line_share": round(top_line_share, 3),
        "long_gap_sec": big_gap,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(ROOT, "tools"))

    files = [os.path.join(REF_DIR, f) for f in sorted(os.listdir(REF_DIR))
             if f.endswith(".vtt")]
    rows = [measure_file(f) for f in files]
    ok = [r for r in rows if "error" not in r]
    for r in rows:
        if "error" in r:
            print(f"  {r['file']:<40} SKIPPED ({r['error']})")
            continue
        print(f"  {r['file']:<40} {r['lang']}  "
              f"{r['runtime_min']:5.1f}min  {r['scenes']:3d} scenes  "
              f"lines/scene mean {r['lines_per_scene_mean']:4.2f} "
              f"med {r['lines_per_scene_median']} "
              f"p90 {r['lines_per_scene_p90']} "
              f"max {r['lines_per_scene_max']:2d} | "
              f"1-line {r['one_line_scene_share']:.0%} "
              f"run {r['longest_one_line_run']:2d} | "
              f"top20 runtime {r['top20_runtime_share']:.0%} "
              f"lines {r['top20_line_share']:.0%}")

    def agg(rs, key):
        v = [r[key] for r in rs]
        return (min(v), statistics.median(v), max(v)) if v else (0, 0, 0)

    print()
    out = {"files": rows, "by_lang": {}}
    for lang in ("en", "vi"):
        rs = [r for r in ok if r["lang"] == lang]
        if not rs:
            continue
        g = {
            "n_files": len(rs),
            "lines_per_scene_mean": agg(rs, "lines_per_scene_mean"),
            "one_line_scene_share": agg(rs, "one_line_scene_share"),
            "longest_one_line_run": agg(rs, "longest_one_line_run"),
            "top20_runtime_share": agg(rs, "top20_runtime_share"),
            "top20_line_share": agg(rs, "top20_line_share"),
        }
        out["by_lang"][lang] = g
        print(f"{lang.upper()} ({len(rs)} file(s))  min / median / max")
        for k in ("lines_per_scene_mean", "one_line_scene_share",
                  "longest_one_line_run", "top20_runtime_share",
                  "top20_line_share"):
            lo, md, hi = g[k]
            print(f"   {k:24s} {lo:7.3f} / {md:7.3f} / {hi:7.3f}")
    if a.write:
        p = os.path.join(ROOT, "config", "pacing_control.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)
        print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
