# -*- coding: utf-8 -*-
"""Gom `draft.json.d/act*.json` thanh `draft.json`, danh so lai theo thu tu
thoi gian, va BAO CAO - khong im lang - nhung dong co `window_adjusted`.

Dung:
    python tools/assemble_draft.py <project> [--title "..."]
"""
from __future__ import annotations
import argparse, io, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def pt(ts) -> float:
    p = [float(x) for x in str(ts).split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--title", default="Bad Genius (2017)")
    ap.add_argument("--target", type=float, default=20.0)
    a = ap.parse_args()
    pdir = config.project_dir(a.project)
    d = pdir / "draft.json.d"

    acts, missing, lines = [], [], []
    for f in sorted(d.glob("act*.json")) if d.exists() else []:
        try:
            o = json.load(io.open(f, encoding="utf-8"))
        except Exception as e:
            missing.append(f"{f.name}: JSON hong ({e})")
            continue
        acts.append(f.name)
        lines += o.get("lines") or []
    if not lines:
        print("khong co dong nao - chua act nao duoc viet")
        return 1

    lines.sort(key=lambda l: pt(l["clip_start"]))
    for i, l in enumerate(lines, 1):
        l["id"] = i

    adj = [l["id"] for l in lines if l.get("window_adjusted")]
    words = sum(len(str(l.get("narration", "")).split()) for l in lines)
    out = {"title": a.title, "target_minutes": a.target,
           "voice": "en-US",
           "stage_note": ("Draft MAY. Viet tu shots_machine.json + "
                          "beats_proposal.md bang vong draft act-by-act. "
                          f"{len(adj)} dong co window_adjusted."),
           "lines": lines}
    io.open(pdir / "draft.json", "w", encoding="utf-8").write(
        json.dumps(out, ensure_ascii=False, indent=2))
    print(f"{len(acts)} act | {len(lines)} dong | {words} tu "
          f"(~{words/150:.1f} phut doc)")
    if missing:
        print(f"FILE HONG: {missing}")
    print(f"window_adjusted: {len(adj)} dong"
          + (f" -> {adj}" if adj else ""))
    beats = {}
    for l in lines:
        beats.setdefault(l.get("note", "?"), 0)
        beats[l["note"]] += 1
    print(f"beat duoc phuc vu: {len(beats)}")
    print(f"da ghi {pdir / 'draft.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
