"""Re-derive the frame-only cap after the detector was widened.

THE REASON THIS EXISTS. config.PERSONA_FRAME_ONLY_SHARE_MAX = 0.13 was
derived from five English references measured at 5.9 / 7.0 / 8.4 / 11.5 /
11.5%. Those numbers appear ONLY in a config comment - no tool produced them,
so they could not be re-taken when the instrument changed. The instrument has
now changed: the frame-only detector was a positive match on a closed list of
visual verbs, which could not see a bare noun list (the emptier line of the
two), so a shot-list sentence was added to it.

A bar calibrated with a different instrument is not a calibration - that rule
is written in this very constant's own comment about the 0.15 it replaced. So
the references are re-measured with BOTH detectors here, and the measurement
is a tool from now on rather than a number in a comment.

BASIS. A reference VTT has no lines, so its only unit is the SENTENCE; our
draft's unit is the LINE, and a line is frame-only if ANY of its sentences is.
The old comparison put a reference SENTENCE share next to our LINE share
without saying so. Both bases are measured here, on our own drafts, and the
conversion is reported rather than assumed.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.stdout.reconfigure(encoding="utf-8")

from pipeline import pacing_gates as pg                      # noqa: E402
from pipeline import shotlist_gates as sg                    # noqa: E402

REF_DIR = os.path.join(ROOT, "references", "voice")
OUT = os.path.join(ROOT, "config", "frame_only_control.json")


def _narrow(text: str) -> bool:
    """The detector as it was BEFORE the widening: visual verb, no evaluation.

    Reproduced here rather than imported, because _is_frame_only now includes
    the shot-list test and the point of this tool is to measure both.
    """
    t = str(text or "")
    if pg.classify_judgment(t)[0]:
        return False
    return bool(pg._VISUAL_VERB.search(t))


def _wide(text: str) -> bool:
    if _narrow(text):
        return True
    try:
        return bool(sg.shotlist_sentences(text))
    except Exception:
        return False


def _sentences(text: str) -> list:
    parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    return [p for p in parts if len(p.split()) >= 2]


def measure_reference(path: str) -> dict:
    from measure_voice import parse_vtt
    from measure_pacing import _words_with_times, _sentences as _s
    sents = [t for _a, _b, t in _s(_words_with_times(parse_vtt(path)))]
    n = len(sents)
    nar = sum(1 for s in sents if _narrow(s))
    wid = sum(1 for s in sents if _wide(s))
    return {"file": os.path.basename(path), "sentences": n,
            "narrow": round(nar / n, 4) if n else None,
            "wide": round(wid / n, 4) if n else None}


def measure_draft(path: str) -> dict:
    d = json.load(io.open(path, encoding="utf-8-sig"))
    lines = [str(l.get("narration") or "") for l in d.get("lines") or []
             if str(l.get("narration") or "").strip()]
    sents = [s for t in lines for s in _sentences(t)]
    out = {"file": os.path.basename(path), "lines": len(lines),
           "sentences": len(sents)}
    for name, fn in (("narrow", _narrow), ("wide", _wide)):
        out[f"{name}_line"] = (round(sum(1 for t in lines if fn(t))
                                     / len(lines), 4) if lines else None)
        out[f"{name}_sent"] = (round(sum(1 for s in sents if fn(s))
                                     / len(sents), 4) if sents else None)
    return out


def main() -> int:
    refs = []
    if os.path.isdir(REF_DIR):
        for f in sorted(os.listdir(REF_DIR)):
            if f.endswith(".vtt") and ".en" in f:
                try:
                    refs.append(measure_reference(os.path.join(REF_DIR, f)))
                except Exception as e:                      # pragma: no cover
                    refs.append({"file": f, "error": str(e)})
    ok = [r for r in refs if r.get("wide") is not None]
    nar = sorted(r["narrow"] for r in ok)
    wid = sorted(r["wide"] for r in ok)

    drafts = []
    for n in ("draft.json", "draft_prerewrite.json",
              "draft_overcorrected.json"):
        p = os.path.join(ROOT, "projects", "tokyodrift2006", n)
        if os.path.exists(p):
            drafts.append(measure_draft(p))

    conv = None
    base = [d for d in drafts if d.get("wide_sent")]
    if base:
        fs = [d["wide_line"] / d["wide_sent"] for d in base
              if d["wide_sent"]]
        conv = round(sum(fs) / len(fs), 3) if fs else None

    print(f"{'reference':36} {'narrow':>8} {'wide':>8}")
    for r in ok:
        print(f"{r['file'][:36]:36} {100*r['narrow']:7.1f}% "
              f"{100*r['wide']:7.1f}%")
    if wid:
        print(f"\nby SENTENCE  narrow {[round(100*x,1) for x in nar]}")
        print(f"             wide   {[round(100*x,1) for x in wid]}")
        print(f"             wide: min {100*wid[0]:.1f}%  median "
              f"{100*wid[len(wid)//2]:.1f}%  max {100*wid[-1]:.1f}%")
    print()
    print(f"{'draft':36} {'n/line':>8} {'w/line':>8} {'n/sent':>8} "
          f"{'w/sent':>8}")
    for d in drafts:
        print(f"{d['file'][:36]:36} {100*d['narrow_line']:7.1f}% "
              f"{100*d['wide_line']:7.1f}% {100*d['narrow_sent']:7.1f}% "
              f"{100*d['wide_sent']:7.1f}%")
    print(f"\nline/sentence conversion measured on our drafts: {conv}")

    rec = None
    if wid and conv:
        ref_line_eq = sorted(round(x * conv, 4) for x in wid)
        print(f"references converted to our LINE basis (x{conv}): "
              f"{[round(100*x,1) for x in ref_line_eq]}")
        rec = round(ref_line_eq[-1] + 0.01, 2)
        print(f"\nthe old cap 0.13 sat just above the reference maximum on "
              f"the NARROW instrument.")
        print(f"On the WIDE instrument the reference maximum in line-basis "
              f"terms is {ref_line_eq[-1]:.3f}, so the same rule gives "
              f"{rec:.2f}.")
        live = next((d for d in drafts if d["file"] == "draft.json"), None)
        if live:
            print(f"live draft wide/line {live['wide_line']:.4f} - "
                  + ("INSIDE" if live["wide_line"] <= rec else "OVER")
                  + f" a {rec:.2f} cap")

    json.dump({
        "instrument_narrow": "visual verb, no evaluation (pre-widening)",
        "instrument_wide": ("narrow OR a shot-list sentence "
                            "(pipeline.shotlist_gates.shotlist_sentences)"),
        "basis_note": ("references by SENTENCE; our drafts by LINE and by "
                       "SENTENCE; the line/sentence conversion is measured "
                       "on our own drafts, never assumed"),
        "references": refs,
        "reference_sentence_share": {"narrow": nar, "wide": wid},
        "drafts": drafts,
        "line_per_sentence_conversion": conv,
        "recommended_cap_line_basis": rec,
    }, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"written: {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
