"""
Build a BLIND A/B test: which shot fits the line better, old or new?

    python tools/blind_prep.py --project tokyodrift2006 --n 40

For each sampled line it writes two frames, A and B, in RANDOM order, plus a
question file with the narration and no hint of which is which. The answer key
is written separately and is not readable from the question material.

Why blind, and why a fresh judge: every other number in this prototype is
produced by the same embedding that chose the binding, so it cannot be
evidence that the binding is good - it is the objective function talking about
itself. A judge who sees only the prose and two pictures, in random order,
with no idea which side the machine preferred, is the one measurement here
that is independent of the thing being measured.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261031)
    ap.add_argument("--batches", type=int, default=4)
    a = ap.parse_args()

    pdir = config.project_dir(a.project)
    fdir = pdir / "_fingerprints"
    prop = json.loads((fdir / "proposed_binding.json").read_text(
        encoding="utf-8"))
    # THE JUDGE MUST SEE THE REAL NARRATION, not the LLM's visual paraphrase.
    # The paraphrase is the exact text the new shot was selected to maximise
    # similarity against, so showing it would hand the new side the question
    # paper. The viewer hears the narration; that is what has to fit.
    draft = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    narr = {l["id"]: str(l.get("narration", "")).strip()
            for l in draft["lines"]}
    fp = json.loads((fdir / "fingerprints.json").read_text(encoding="utf-8"))
    frames_by_shot: dict[str, list[str]] = {}
    for p, s in zip(fp["frame_paths"], fp["frame_shot"]):
        frames_by_shot.setdefault(s, []).append(p)

    # Only lines the matcher actually MOVED can discriminate. A line whose
    # binding did not change would show the same picture twice.
    moved = [b for b in prop["binding"] if b["old_shot"] != b["new_shot"]]
    rng = random.Random(a.seed)
    rng.shuffle(moved)
    pick = moved[:a.n]
    print(f"{len(moved)} line(s) were re-pointed; sampling {len(pick)}")

    out = fdir / "blind"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    key = []
    per = max(1, len(pick) // a.batches)
    for bi in range(a.batches):
        chunk = pick[bi * per: (bi + 1) * per] if bi < a.batches - 1 \
            else pick[bi * per:]
        bdir = out / f"batch{bi+1}"
        bdir.mkdir(parents=True, exist_ok=True)
        qs = []
        for item in chunk:
            lid = item["id"]
            # middle frame of each shot - least likely to sit on a cut
            fa = frames_by_shot.get(item["old_shot"], [])
            fb = frames_by_shot.get(item["new_shot"], [])
            if not fa or not fb:
                continue
            old_img = fa[len(fa) // 2]
            new_img = fb[len(fb) // 2]
            a_is_old = rng.random() < 0.5
            qdir = bdir / f"line_{lid:03d}"
            qdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_img if a_is_old else new_img, qdir / "A.jpg")
            shutil.copy2(new_img if a_is_old else old_img, qdir / "B.jpg")
            qs.append({"line_id": lid,
                       "narration": narr.get(lid, ""),
                       "folder": str(qdir)})
            key.append({"line_id": lid, "A": "old" if a_is_old else "new",
                        "B": "new" if a_is_old else "old",
                        "old_shot": item["old_shot"],
                        "new_shot": item["new_shot"]})
        (bdir / "questions.json").write_text(
            json.dumps(qs, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"  batch{bi+1}: {len(qs)} question(s) -> {bdir}")

    # The key lives OUTSIDE the blind/ tree so a judge reading its own
    # batch folder cannot stumble into it.
    (fdir / "blind_key.json").write_text(
        json.dumps(key, indent=1), encoding="utf-8")
    sides = [k["A"] for k in key]
    print(f"\nkey written ({len(key)} items). A is old in "
          f"{sides.count('old')}/{len(sides)} - should be near half, "
          f"otherwise the randomisation is skewed and a judge with a "
          f"position bias would look right or wrong for free.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
