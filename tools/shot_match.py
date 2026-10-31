"""
MEASURE-ONLY prototype of Phase 4 item 1: re-bind each narrated line to a shot.

    python tools/shot_match.py --project tokyodrift2006

Reads the cached fingerprints, the LLM's visual description per line, and
proposes a new line->shot binding. Then measures the proposed binding against
the current one with the SAME functions the pipeline already uses, so the
comparison is not against a metric invented for the occasion.

CHANGES NOTHING. It writes a report and a proposed binding to
projects/<p>/_fingerprints/. It does not touch draft.json and the render
never reads any of it.

THREE SCORES, AND WHY THESE THREE
  image-text  cosine between the CLIP text embedding of the line's visual
              description and the mean CLIP image embedding of the shot's
              three frames. This is the only term that looks at the PICTURE.
  time        a Gaussian on the distance between the shot's midpoint and the
              line's current midpoint. Recaps move forward through a film; a
              shot forty minutes away is almost certainly wrong even if it
              looks right.
  text        token overlap between the description and the shot's own
              `action` prose, `depicts` tags and `chars`. Those were written
              by a different process (the span tagger), so agreement between
              them and the image is weak independent evidence.

ASSIGNMENT IS A DP, NOT A GREEDY ARGMAX
Each shot may be used once and the bindings must advance through the film.
Greedy picking violates both: two lines grab the same best shot, and line 40
lands before line 39. The DP below is the classic monotonic alignment -
dp[i][j] = max(dp[i][j-1], dp[i-1][j-1] + score(i,j)) - which enforces "at
most once" and "in film order" by construction rather than by a repair pass.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

W_IMAGE, W_TIME, W_TEXT = 1.0, 0.55, 0.35
NEIGHBOURHOOD_SEC = 150.0      # how far a line may be re-pointed
TIME_SIGMA = 60.0
PHASH_BITS = 5                 # the plan's "<=5 bits is a duplicate"

# CALIBRATED, and the calibration is mostly a warning. tools/calibrate_dup.py
# measured all 140,715 shot pairs in this film:
#   unrelated pairs (pHash>12 and >120s apart): p99 0.9238, MAX 0.9835
#   pHash-confirmed duplicates:                 min 0.8697, median 0.9267
# The two distributions overlap almost completely - two unrelated shots of the
# same film reach 0.98 because they share a grade, a cast and a lens. 0.93 is
# the lowest bar that keeps the false-positive rate under 1%, and even there
# it flags 823 unrelated pairs.
#
# The first version of this file used 0.92 by intuition and reported 105
# "duplicate pairs" among the 108 shots a binding uses, i.e. nearly all of
# them. That was a broken threshold presented as a finding.
#
# There are only TWO pHash-confirmed duplicate pairs in the entire film, so
# there is almost no ground truth to calibrate against. Treat the embedding
# duplicate count as INDICATIVE ONLY and read pHash as the real signal.
EMB_DUP = 0.93
MODEL_PATH = Path("models/ViT-B-32.pt")

_STOP = set("a an the and or of in on at to for with from into over under "
            "his her its their this that these those is are was were be been "
            "as by it he she they them him up out off then than there here "
            "which who whom while after before during between across".split())


def hhmmss(s: str) -> float:
    p = str(s).split(":")
    if len(p) == 3:
        return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
    if len(p) == 2:
        return int(p[0]) * 60 + float(p[1])
    return float(s)


def toks(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", str(s).lower())
            if len(w) > 2 and w not in _STOP}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--draft", default="draft_a2b75fd.json")
    a = ap.parse_args()

    pdir = config.project_dir(a.project)
    fdir = pdir / "_fingerprints"
    z = np.load(fdir / "embeddings.npz", allow_pickle=False)
    shot_emb = z["shot_emb"]
    shot_ids = [str(x) for x in z["shot_ids"]]
    frame_shot = [str(x) for x in z["frame_shot"]]
    phash = z["phash"]

    shots_raw = json.loads((pdir / "shots.json").read_text(encoding="utf-8"))
    shots_raw = shots_raw["shots"] if isinstance(shots_raw, dict) else shots_raw
    shot_by_id = {s["id"]: s for s in shots_raw}
    order = sorted(range(len(shot_ids)),
                   key=lambda i: hhmmss(shot_by_id[shot_ids[i]]["clip_start"]))
    shot_ids = [shot_ids[i] for i in order]
    shot_emb = shot_emb[order]
    s_start = np.array([hhmmss(shot_by_id[s]["clip_start"]) for s in shot_ids])
    s_end = np.array([hhmmss(shot_by_id[s]["clip_end"]) for s in shot_ids])
    s_mid = (s_start + s_end) / 2.0
    s_toks = [toks(" ".join([shot_by_id[s].get("action", "")]
                            + list(shot_by_id[s].get("depicts") or [])
                            + list(shot_by_id[s].get("chars") or [])))
              for s in shot_ids]

    # per-shot pHash list (3 frames each)
    ph_by_shot: dict[str, list[int]] = {}
    for i, sid in enumerate(frame_shot):
        ph_by_shot.setdefault(sid, []).append(int(phash[i]))

    draft = json.loads((pdir / a.draft).read_text(encoding="utf-8-sig"))
    visuals = json.loads((fdir / "visuals.json").read_text(encoding="utf-8"))
    lines = [l for l in draft["lines"]
             if str(l.get("narration", "")).strip() and l.get("clip_start")]
    lines.sort(key=lambda l: hhmmss(l["clip_start"]))

    # ---- text embeddings for the visual descriptions ---------------------
    import torch
    import open_clip
    torch.set_num_threads(10)
    model = open_clip.load_openai_model(str(MODEL_PATH), device="cpu")
    model.eval()
    tok = open_clip.get_tokenizer("ViT-B-32")
    descs = [visuals.get(str(l["id"]), "") for l in lines]
    t0 = time.perf_counter()
    with torch.no_grad():
        tt = tok(descs)
        tf = model.encode_text(tt)
        tf = tf / tf.norm(dim=-1, keepdim=True)
    line_emb = tf.numpy().astype(np.float32)
    print(f"text embeddings: {len(descs)} in {time.perf_counter()-t0:.1f}s")

    # ---- score matrix ----------------------------------------------------
    L, S = len(lines), len(shot_ids)
    NEG = -1e9
    score = np.full((L, S), NEG, dtype=np.float32)
    img_sim = line_emb @ shot_emb.T                    # cosine, both unit norm
    for i, ln in enumerate(lines):
        mid = (hhmmss(ln["clip_start"]) + hhmmss(ln["clip_end"])) / 2.0
        near = np.abs(s_mid - mid) <= NEIGHBOURHOOD_SEC
        if not near.any():
            near = np.abs(s_mid - mid) <= NEIGHBOURHOOD_SEC * 3
        lt = toks(descs[i])
        for j in np.where(near)[0]:
            ov = len(lt & s_toks[j]) / max(1, len(lt))
            tprox = float(np.exp(-((s_mid[j] - mid) ** 2) /
                                 (2 * TIME_SIGMA ** 2)))
            score[i, j] = (W_IMAGE * float(img_sim[i, j])
                           + W_TIME * tprox + W_TEXT * ov)

    # ---- monotonic DP ----------------------------------------------------
    t0 = time.perf_counter()
    dp = np.full((L + 1, S + 1), NEG, dtype=np.float64)
    dp[0, :] = 0.0
    back = np.zeros((L + 1, S + 1), dtype=np.int8)      # 1 = take, 0 = skip
    for i in range(1, L + 1):
        for j in range(1, S + 1):
            skip = dp[i, j - 1]
            take = dp[i - 1, j - 1] + score[i - 1, j - 1]
            if take >= skip:
                dp[i, j], back[i, j] = take, 1
            else:
                dp[i, j], back[i, j] = skip, 0
    # walk back
    assign: dict[int, int] = {}
    i, j = L, S
    while i > 0 and j > 0:
        if back[i, j] == 1:
            assign[i - 1] = j - 1
            i -= 1
            j -= 1
        else:
            j -= 1
    print(f"DP {L}x{S} in {time.perf_counter()-t0:.1f}s, "
          f"assigned {len(assign)}/{L}")

    # ---- near-duplicate counting ----------------------------------------
    def dup_pairs(binding: list[str]) -> dict:
        """Count repeats among the shots a binding actually uses."""
        uniq = list(dict.fromkeys(binding))
        reused = len(binding) - len(uniq)
        ph_pairs, emb_pairs = set(), set()
        idx = {s: shot_ids.index(s) for s in uniq if s in shot_ids}
        for x in range(len(uniq)):
            for y in range(x + 1, len(uniq)):
                sa, sb = uniq[x], uniq[y]
                ha = ph_by_shot.get(sa, [])
                hb = ph_by_shot.get(sb, [])
                if ha and hb:
                    best = min(bin(p ^ q).count("1") for p in ha for q in hb)
                    if best <= PHASH_BITS:
                        ph_pairs.add((sa, sb))
                if sa in idx and sb in idx:
                    c = float(shot_emb[idx[sa]] @ shot_emb[idx[sb]])
                    if c >= EMB_DUP:
                        emb_pairs.add((sa, sb))
        return {"shots_used": len(uniq), "same_shot_reused": reused,
                "phash_pairs": len(ph_pairs), "embedding_pairs": len(emb_pairs),
                "either": len(ph_pairs | emb_pairs)}

    def shot_for_window(a0: float, b0: float) -> str:
        """Which catalogued shot does a current binding sit in?"""
        mid = (a0 + b0) / 2.0
        inside = [k for k in range(S) if s_start[k] <= mid <= s_end[k]]
        if inside:
            return shot_ids[inside[0]]
        return shot_ids[int(np.argmin(np.abs(s_mid - mid)))]

    cur_binding = [shot_for_window(hhmmss(l["clip_start"]),
                                   hhmmss(l["clip_end"])) for l in lines]
    new_binding = [shot_ids[assign[i]] if i in assign else cur_binding[i]
                   for i in range(L)]

    cur_dup = dup_pairs(cur_binding)
    new_dup = dup_pairs(new_binding)

    out = {
        "project": a.project, "draft": a.draft,
        "lines": L, "shots": S,
        "weights": {"image": W_IMAGE, "time": W_TIME, "text": W_TEXT},
        "neighbourhood_sec": NEIGHBOURHOOD_SEC,
        "phash_bits": PHASH_BITS, "embedding_dup_cosine": EMB_DUP,
        "duplicates": {"current": cur_dup, "proposed": new_dup},
        "changed": sum(1 for i in range(L)
                       if cur_binding[i] != new_binding[i]),
        "binding": [
            {"id": lines[i]["id"],
             "visual": descs[i],
             "old_shot": cur_binding[i],
             "new_shot": new_binding[i],
             "old_start": lines[i]["clip_start"],
             "new_start": shot_by_id[new_binding[i]]["clip_start"],
             "new_end": shot_by_id[new_binding[i]]["clip_end"],
             "img_sim_old": round(float(
                 img_sim[i, shot_ids.index(cur_binding[i])]), 4),
             "img_sim_new": round(float(
                 img_sim[i, shot_ids.index(new_binding[i])]), 4)}
            for i in range(L)],
    }
    (fdir / "proposed_binding.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"\nchanged binding on {out['changed']}/{L} lines")
    print(f"\n{'':22}{'current':>10}{'proposed':>10}")
    for k in ("shots_used", "same_shot_reused", "phash_pairs",
              "embedding_pairs", "either"):
        print(f"  {k:<20}{cur_dup[k]:>10}{new_dup[k]:>10}")
    mo = float(np.mean([b["img_sim_old"] for b in out["binding"]]))
    mn = float(np.mean([b["img_sim_new"] for b in out["binding"]]))
    print(f"\n  mean image-text cosine   old {mo:.4f}   new {mn:.4f}   "
          f"{mn-mo:+.4f}")
    print(f"\nwrote {fdir/'proposed_binding.json'}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
