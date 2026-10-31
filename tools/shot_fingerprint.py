"""
Fingerprint every shot ONCE: 3 frames, a CLIP embedding, and a pHash.

    python tools/shot_fingerprint.py --project tokyodrift2006

MEASURE-ONLY. Writes nothing the render reads. Output goes to
projects/<p>/_fingerprints/ and is pure cache: delete it and it rebuilds.

WHICH MODEL, AND WHY NOT THE ONE THE PLAN NAMES
The plan says PE-Core-B/16 or SigLIP 2. Both licences were checked first, via
api.github.com because raw.githubusercontent.com and huggingface.co are both
intercepted on this network:

  facebookresearch/perception_models  Apache-2.0, and apps/pe/README.md says
      "All checkpoints released on this page ... Apache 2.0" with
      PE-Core-B16-224 listed on it. Commercial use permitted. (The FAIR
      Noncommercial licence in that repo covers PLM, a different model - worth
      stating because it is the obvious thing to get wrong.)
  google-research/big_vision          Apache-2.0.
  openai/CLIP                         MIT.

So PE-Core is both the better model and licence-clean. It is nonetheless NOT
used here, because it cannot be downloaded on this machine: huggingface.co
returns a Microsoft sign-in page for every file path, with TLS verification on
or off, and open_clip routes every pretrained tag through the Hub. SigLIP 2 is
reachable as a 1.4 GB big_vision .npz from Google's GCS bucket, but loading
that needs jax plus a parameter-name mapping, which is a lot of risk for a
prototype.

What IS reachable is openaipublic.azureedge.net, so this uses OpenAI
CLIP ViT-B/32 - MIT, sha256 verified against the digest OpenAI publishes in
the URL itself. CONSEQUENCE WORTH STATING PLAINLY: ViT-B/32 is a weaker and
much older encoder than PE-Core-B/16, so every match number this produces is
a FLOOR, not an estimate of what the real thing would do.

pHash is implemented here rather than imported: the `imagehash` package wants
scipy for its DCT and scipy is not installed, and a 32x32 DCT-II is a dozen
lines.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

FRAMES_PER_SHOT = 3
FRAME_PX = 256
MODEL_PATH = Path("models/ViT-B-32.pt")


def hhmmss(s: str) -> float:
    p = str(s).split(":")
    if len(p) == 3:
        return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
    if len(p) == 2:
        return int(p[0]) * 60 + float(p[1])
    return float(s)


def frame_times(a: float, b: float, n: int = FRAMES_PER_SHOT) -> list[float]:
    """Sample inside the shot, never on its edges.

    A frame taken at the exact cut point is as likely to belong to the
    neighbouring shot as to this one, and on a dissolve it belongs to both.
    Quarters avoid both ends.
    """
    span = max(0.0, b - a)
    if span <= 0.05:
        return [a]
    return [a + span * f for f in ((0.25, 0.5, 0.75) if n == 3
                                   else [(i + 1) / (n + 1) for i in range(n)])]


# --------------------------------------------------------------------------- #
# pHash: 64-bit perceptual hash via a 32x32 DCT-II, low-frequency 8x8 block
# --------------------------------------------------------------------------- #
_DCT_M: np.ndarray | None = None


def _dct_matrix(n: int = 32) -> np.ndarray:
    global _DCT_M
    if _DCT_M is None or _DCT_M.shape[0] != n:
        k = np.arange(n).reshape(-1, 1)
        x = np.arange(n).reshape(1, -1)
        m = np.cos(np.pi * (2 * x + 1) * k / (2 * n))
        m[0, :] *= 1.0 / np.sqrt(2.0)
        _DCT_M = m * np.sqrt(2.0 / n)
    return _DCT_M


def phash64(gray32: np.ndarray) -> int:
    m = _dct_matrix(32)
    d = m @ gray32 @ m.T
    block = d[:8, :8].copy()
    # Drop the DC term before taking the median: it carries overall
    # brightness, which would otherwise dominate and make every dark frame
    # look like every other dark frame.
    flat = block.flatten()[1:]
    med = float(np.median(flat))
    bits = (block.flatten() > med).astype(np.uint8)
    bits[0] = 0
    out = 0
    for b in bits:
        out = (out << 1) | int(b)
    return out


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# --------------------------------------------------------------------------- #
# frame extraction
# --------------------------------------------------------------------------- #
def extract_one(ff: str, src: Path, t: float, out: Path) -> bool:
    if out.exists() and out.stat().st_size > 0:
        return True
    r = subprocess.run(
        [ff, "-y", "-hide_banner", "-loglevel", "error",
         "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1",
         "-vf", f"scale={FRAME_PX}:-2:flags=bilinear",
         "-q:v", "4", str(out)],
        capture_output=True, text=True)
    return r.returncode == 0 and out.exists() and out.stat().st_size > 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0,
                    help="only the first N shots (for a quick check)")
    a = ap.parse_args()

    pdir = config.project_dir(a.project)
    src = pdir / "source.mp4"
    shots = json.loads((pdir / "shots.json").read_text(encoding="utf-8"))
    shots = shots["shots"] if isinstance(shots, dict) else shots
    if a.limit:
        shots = shots[:a.limit]

    fdir = pdir / "_fingerprints"
    imgdir = fdir / "frames"
    imgdir.mkdir(parents=True, exist_ok=True)

    if not MODEL_PATH.exists():
        print(f"model missing: {MODEL_PATH}")
        return 1

    # ---- 1. frames -------------------------------------------------------
    jobs = []
    for sh in shots:
        a0, b0 = hhmmss(sh["clip_start"]), hhmmss(sh["clip_end"])
        for k, t in enumerate(frame_times(a0, b0)):
            key = hashlib.sha1(f"{sh['id']}|{k}|{t:.3f}".encode()).hexdigest()[:16]
            jobs.append((sh["id"], k, t, imgdir / f"{key}.jpg"))

    ff = config.ffmpeg()
    print(f"shots {len(shots)} -> {len(jobs)} frames "
          f"({FRAMES_PER_SHOT} per shot, at 25/50/75% of each window)")
    t0 = time.perf_counter()
    n_new = 0
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(extract_one, ff, src, t, p): (sid, k)
                for sid, k, t, p in jobs if not p.exists()}
        n_new = len(futs)
        done = 0
        for fu in cf.as_completed(futs):
            done += 1
            if done % 200 == 0:
                print(f"    {done}/{len(futs)} frames")
    t_frames = time.perf_counter() - t0
    print(f"  frame extraction: {t_frames:.1f}s "
          f"({n_new} new, {len(jobs)-n_new} cached)")

    # ---- 2. embed + phash ------------------------------------------------
    import torch
    from PIL import Image
    import open_clip
    torch.set_num_threads(max(1, (config_cpu := 10)))

    t0 = time.perf_counter()
    # OpenAI's published .pt is a TorchScript JIT ARCHIVE, not a state dict,
    # so create_model_and_transforms(pretrained=<path>) fails on it under
    # torch>=2.6 ("Cannot use weights_only=True with TorchScript archives").
    # load_openai_model handles the JIT format and converts it into an
    # open_clip model; it accepts a local path as well as a model name.
    model = open_clip.load_openai_model(str(MODEL_PATH), device="cpu")
    model.eval()
    preprocess = open_clip.image_transform(
        model.visual.image_size, is_train=False)
    t_load = time.perf_counter() - t0
    print(f"  model load: {t_load:.1f}s (CLIP ViT-B/32, MIT, local file)")

    paths = [p for _, _, _, p in jobs]
    ids = [(sid, k) for sid, k, _, _ in jobs]
    embs = np.zeros((len(paths), 512), dtype=np.float32)
    hashes: list[int] = []

    t0 = time.perf_counter()
    BATCH = 32
    with torch.no_grad():
        for i in range(0, len(paths), BATCH):
            batch_paths = paths[i:i + BATCH]
            tensors, grays = [], []
            for p in batch_paths:
                try:
                    im = Image.open(p).convert("RGB")
                except Exception:
                    im = Image.new("RGB", (FRAME_PX, FRAME_PX))
                tensors.append(preprocess(im))
                grays.append(np.asarray(
                    im.convert("L").resize((32, 32), Image.BILINEAR),
                    dtype=np.float64))
            x = torch.stack(tensors)
            f = model.encode_image(x)
            f = f / f.norm(dim=-1, keepdim=True)
            embs[i:i + len(batch_paths)] = f.numpy().astype(np.float32)
            hashes.extend(phash64(g) for g in grays)
            if (i // BATCH) % 10 == 0:
                print(f"    embedded {min(i+BATCH, len(paths))}/{len(paths)}")
    t_embed = time.perf_counter() - t0
    print(f"  embed + pHash: {t_embed:.1f}s for {len(paths)} frames "
          f"({t_embed/max(1,len(paths))*1000:.0f} ms/frame on CPU)")

    # ---- 3. per-shot aggregate ------------------------------------------
    by_shot: dict[str, list[int]] = {}
    for idx, (sid, _k) in enumerate(ids):
        by_shot.setdefault(sid, []).append(idx)
    shot_ids = [sh["id"] for sh in shots]
    shot_emb = np.zeros((len(shot_ids), 512), dtype=np.float32)
    for si, sid in enumerate(shot_ids):
        rows = embs[by_shot[sid]]
        v = rows.mean(axis=0)
        n = np.linalg.norm(v)
        shot_emb[si] = v / n if n > 0 else v

    np.savez_compressed(
        fdir / "embeddings.npz",
        frame_emb=embs, shot_emb=shot_emb,
        frame_shot=np.array([s for s, _ in ids]),
        frame_slot=np.array([k for _, k in ids]),
        shot_ids=np.array(shot_ids),
        phash=np.array(hashes, dtype=np.uint64))
    meta = {
        "model": "openai CLIP ViT-B/32 (local ViT-B-32.pt)",
        "model_licence": "MIT (openai/CLIP, verified via api.github.com)",
        "licence_note": ("PE-Core-B/16 is Apache-2.0 and would be preferred; "
                         "huggingface.co is blocked on this network so it "
                         "could not be downloaded. Numbers here are a floor."),
        "frames_per_shot": FRAMES_PER_SHOT,
        "shots": len(shots), "frames": len(paths),
        "seconds": {"frames": round(t_frames, 1), "model_load": round(t_load, 1),
                    "embed_phash": round(t_embed, 1)},
        "frame_paths": [str(p) for p in paths],
        "frame_shot": [s for s, _ in ids],
    }
    (fdir / "fingerprints.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\nwrote {fdir/'embeddings.npz'} and fingerprints.json")
    print(f"TOTAL {t_frames + t_load + t_embed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
