"""Calibrate the judgment CEILING from the English references.

THE DEFECT. PERSONA_JUDGMENT_SHARE_MIN gave the narrator a floor and no
ceiling, so the fix for a draft with 10% judgment produced one with 52%: the
narrator talks over the film, every beat arrives pre-digested, and the peak
moments land on commentary instead of on the moment. A floor with no ceiling
is half a bar.

BASIS, because it is the thing that breaks this measurement. A reference is a
VTT with no line structure - its only natural unit is the SENTENCE. Our draft's
unit is the LINE, and a line holds 1-4 sentences, so a line is judgment if ANY
of its sentences is. Those two shares are not comparable and must not be
compared: the same draft measures differently on each. So this tool measures
the references by sentence, measures OUR draft by sentence AND by line, and
reports the conversion factor between the two bases measured on our own text -
the same method docs/stage2/PACING_CALIBRATION.md used for the contour bars.

The classifier is pipeline.pacing_gates.classify_judgment, the SAME instrument
the gate uses. Calibrating with one instrument and judging with another is how
the first frame-only cap came out wrong.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from pipeline.pacing_gates import classify_judgment   # noqa: E402

REF_DIR = os.path.join(ROOT, "references", "voice")
OUT = os.path.join(ROOT, "config", "judgment_control.json")


def _split_sentences(text: str) -> list:
    """Sentence split for draft prose, matching the reference splitter.

    measure_pacing._sentences splits a word STREAM on sentence-final
    punctuation; draft prose is already text, so split on the same
    punctuation and keep the >=2-word filter so both sides drop the same
    fragments.
    """
    parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    return [p for p in parts if len(p.split()) >= 2]


def _runs(flags: list) -> int:
    """Longest run of consecutive True."""
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def measure_reference(path: str) -> dict:
    from measure_voice import parse_vtt
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from measure_pacing import _words_with_times, _sentences

    cues = parse_vtt(path)
    sents = _sentences(_words_with_times(cues))
    flags = [bool(classify_judgment(t)[0]) for _, _, t in sents]
    n = len(flags)
    return {
        "file": os.path.basename(path),
        "sentences": n,
        "judgment_sentences": sum(flags),
        "judgment_share_sent": round(sum(flags) / n, 3) if n else None,
        "longest_judgment_run_sent": _runs(flags),
    }


def measure_draft(draft_path: str) -> dict:
    with open(draft_path, encoding="utf-8-sig") as fh:
        d = json.load(fh)
    lines = [l for l in d.get("lines") or []
             if str(l.get("narration") or "").strip()]
    sent_flags: list = []
    line_flags: list = []
    for l in lines:
        ss = _split_sentences(l["narration"])
        fs = [bool(classify_judgment(s)[0]) for s in ss]
        sent_flags.extend(fs)
        line_flags.append(any(fs))
    ns, nl = len(sent_flags), len(line_flags)
    return {
        "file": os.path.basename(draft_path),
        "lines": nl,
        "sentences": ns,
        "judgment_share_sent": round(sum(sent_flags) / ns, 3) if ns else None,
        "judgment_share_line": round(sum(line_flags) / nl, 3) if nl else None,
        "longest_judgment_run_sent": _runs(sent_flags),
        "longest_judgment_run_line": _runs(line_flags),
    }


def main() -> int:
    refs = []
    for f in sorted(os.listdir(REF_DIR)) if os.path.isdir(REF_DIR) else []:
        if f.endswith(".vtt") and ".en" in f:
            try:
                refs.append(measure_reference(os.path.join(REF_DIR, f)))
            except Exception as e:                       # pragma: no cover
                refs.append({"file": f, "error": str(e)})
    ok = [r for r in refs if r.get("judgment_share_sent") is not None]
    shares = sorted(r["judgment_share_sent"] for r in ok)
    runs = sorted(r["longest_judgment_run_sent"] for r in ok)

    drafts = []
    for name in ("draft_overcorrected.json", "draft_prerewrite.json"):
        p = os.path.join(ROOT, "projects", "tokyodrift2006", name)
        if os.path.exists(p):
            drafts.append(measure_draft(p))

    # Basis conversion, measured on our own text: line-basis share divided by
    # sentence-basis share. A line is judgment if ANY sentence in it is, so the
    # line share is always the HIGHER of the two and the factor is >= 1.
    conv = None
    base = [d for d in drafts if d.get("judgment_share_sent")]
    if base:
        fs = [d["judgment_share_line"] / d["judgment_share_sent"]
              for d in base if d["judgment_share_sent"]]
        conv = round(sum(fs) / len(fs), 3) if fs else None

    out = {
        "instrument": "pipeline.pacing_gates.classify_judgment",
        "basis_note": ("references measured by SENTENCE (a VTT has no lines); "
                       "our draft measured by SENTENCE and by LINE; the "
                       "line/sentence conversion is measured on our own "
                       "drafts, never assumed"),
        "references": refs,
        "reference_share_sent": {
            "n": len(ok), "values": shares,
            "min": shares[0] if shares else None,
            "median": shares[len(shares) // 2] if shares else None,
            "max": shares[-1] if shares else None,
        },
        "reference_run_sent": {
            "values": runs,
            "max": runs[-1] if runs else None,
            "median": runs[len(runs) // 2] if runs else None,
        },
        "drafts": drafts,
        "line_per_sentence_conversion": conv,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    print(f"English references: {len(ok)}")
    for r in ok:
        print(f"  {r['file'][:34]:34} {r['sentences']:4d} sent  "
              f"judgment {r['judgment_share_sent']:.3f}  "
              f"longest run {r['longest_judgment_run_sent']}")
    if shares:
        print(f"\n  share by sentence: min {shares[0]:.3f}  median "
              f"{shares[len(shares)//2]:.3f}  max {shares[-1]:.3f}")
        print(f"  longest run by sentence: {runs}")
    print()
    for d in drafts:
        print(f"  {d['file'][:34]:34} {d['lines']:3d} lines / "
              f"{d['sentences']:4d} sent  sent {d['judgment_share_sent']}  "
              f"line {d['judgment_share_line']}  run(line) "
              f"{d['longest_judgment_run_line']}")
    print(f"\n  line/sentence conversion (measured on our drafts): {conv}")
    print(f"  written: {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
