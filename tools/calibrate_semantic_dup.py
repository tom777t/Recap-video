"""Calibrate the same-point detector, and report whether it GENERALISED.

One human-labelled positive is a thin basis for a bar, so recall is also
measured on PARAPHRASES generated from approved lines: each paraphrase
restates one approved line's proposition in different words and is appended
after it. A detector that fires on the one pair it was built for and on none
of the paraphrases has memorised, not generalised, and this tool says so.

Precision is measured on the 103 adjacent pairs of the APPROVED draft, which
are labelled negatives: the viewer approved the draft apart from three named
fixes, so any other adjacent pair firing is a false positive.
"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

from pipeline import semantic_dup as sd                      # noqa: E402

PROJ = os.path.join(ROOT, "projects", "tokyodrift2006")
OUT = os.path.join(ROOT, "config", "semantic_dup_control.json")

# The one pair a human reader reported in the approved draft.
POSITIVE = (59, 60)

# Paraphrase probes: (line id to restate, a restatement in different words).
# Written to say the SAME thing as the named line using different verbs and
# nouns, which is the failure mode being detected. They are not drawn from
# the draft, so firing on them is evidence of generalisation.
PARAPHRASES = [
    (32, "The car he put up was not even his - a stranger had handed him "
         "the keys, and now he owed that stranger a motor he could not buy."),
    (73, "The old man informs him that the partner he trusted had been "
         "siphoning cash out of the business for years."),
    (79, "The vehicle goes up in flames and the man inside it does not "
         "survive the blaze."),
    (60, "He and his friend push cheap merchandise to passers-by because "
         "rubber for the wheels costs cash he does not have."),
    (110, "His friend is moving through the crowd taking fistfuls of other "
          "people's cash off them."),
]


def _load(name: str) -> list:
    d = json.load(io.open(os.path.join(PROJ, name), encoding="utf-8-sig"))
    return [l for l in d["lines"] if str(l.get("narration") or "").strip()]


def run(lines: list, min_idf: float, min_args: int) -> set:
    return {(r["a"], r["b"]) for r in
            sd.adjacent_duplicates(lines, min_idf, min_args)}


def main() -> int:
    final = _load("draft.json")
    by_id = {l["id"]: l for l in final}

    rows = []
    for min_idf in (1.5, 1.75, 2.0, 2.25, 2.5, 3.0):
        for min_args in (1, 2):
            hits = run(final, min_idf, min_args)
            tp = 1 if POSITIVE in hits else 0
            fp = sorted(h for h in hits if h != POSITIVE)

            # recall on paraphrases: insert each after its source line and
            # check the pair fires, measured one probe at a time so probes
            # cannot mask each other.
            caught = 0
            missed = []
            for lid, text in PARAPHRASES:
                if lid not in by_id:
                    continue
                probe = dict(by_id[lid])
                probe["id"] = 9000 + lid
                probe["narration"] = text
                seq = []
                for l in final:
                    seq.append(l)
                    if l["id"] == lid:
                        seq.append(probe)
                if (lid, 9000 + lid) in run(seq, min_idf, min_args):
                    caught += 1
                else:
                    missed.append(lid)
            rows.append({
                "min_idf": min_idf, "min_args": min_args,
                "control_caught": bool(tp),
                "false_positives": len(fp),
                "fp_pairs": [list(x) for x in fp[:8]],
                "paraphrases_caught": caught,
                "paraphrases_total": len([p for p in PARAPHRASES
                                          if p[0] in by_id]),
                "paraphrases_missed": missed,
            })

    print(f"{'min_idf':>8} {'min_args':>9} {'control':>8} {'false+':>7} "
          f"{'paraphrase recall':>18}")
    for r in rows:
        print(f"{r['min_idf']:>8} {r['min_args']:>9} "
              f"{'HIT' if r['control_caught'] else 'miss':>8} "
              f"{r['false_positives']:>7} "
              f"{r['paraphrases_caught']}/{r['paraphrases_total']:>16}")

    ok = [r for r in rows if r["control_caught"]]
    best = None
    if ok:
        # fewest false positives, then best paraphrase recall. A setting that
        # catches the control by firing on everything is not a calibration.
        best = sorted(ok, key=lambda r: (r["false_positives"],
                                         -r["paraphrases_caught"]))[0]
        print()
        print(f"CHOSEN: min_idf={best['min_idf']}, "
              f"min_args={best['min_args']} - catches the reported pair, "
              f"{best['false_positives']} false positive(s) on "
              f"{len(final) - 1} approved adjacent pairs, paraphrase recall "
              f"{best['paraphrases_caught']}/{best['paraphrases_total']}")
        if best["fp_pairs"]:
            print(f"  false positives: {best['fp_pairs']}")
        if best["paraphrases_caught"] == 0:
            print("  WARNING: zero paraphrase recall. The detector fires on "
                  "the pair it was built for and on no restatement it was "
                  "not shown, which is memorisation, not generalisation.")
    else:
        print()
        print("NO SETTING catches the reported pair. Reported rather than "
              "widened until it does.")

    json.dump({
        "instrument": "pipeline.semantic_dup.adjacent_duplicates",
        "not_an_embedding": ("no pretrained sentence encoder is obtainable "
                             "here - model downloads return a ~46 KB page in "
                             "place of a 349-byte file, size varying per "
                             "request, so every checksum fails"),
        "rejected_instruments": {
            "line_content_overlap": "control 0.21 against a 0.50 bar",
            "clause_min_overlap": ("control outside the top twelve; a "
                                   "two-word clause sharing one stem scores "
                                   "1.00"),
            "tfidf_cosine": ("control 0.037 with 33 approved pairs scoring "
                             "higher"),
        },
        "labelled_positive": list(POSITIVE),
        "labelled_negatives": len(final) - 2,
        "paraphrase_probes": len(PARAPHRASES),
        "sweep": rows,
        "chosen": best,
    }, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"written: {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
