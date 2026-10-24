# -*- coding: utf-8 -*-
"""Gom `draft.json.d/act*.json` thanh `draft.json`, danh so lai theo thu tu
thoi gian, va BAO CAO - khong im lang - nhung dong co `window_adjusted`.

Dung:
    python tools/assemble_draft.py <project> [--title "..."]
"""
from __future__ import annotations
import argparse, io, json, os, re, sys

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
    # 2026-09-11: mac dinh o day tung la "Bad Genius (2017)" - ten mot phim
    # KHAC. Moi project khong truyen --title deu in ra tieu de do, va
    # tokyodrift2006/script.txt da mang no suot. Mot gia tri mac dinh la ten
    # rieng cua mot du an khac khong bao gio dung; tot nhat la khong co mac
    # dinh, roi suy ra tu beat map.
    ap.add_argument("--title", default=None)
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

    # Sort into playback order by clip_start - but NOT every line HAS one.
    # Intro-owned lines (over_montage hook, film_intro) carry no clip window by
    # schema rule and play in the prepended block, so they sort to the FRONT in
    # authored order. Pool/montage lines have no single timestamp either; they
    # keep their authored position by inheriting the last timed line's stamp, so
    # a b-roll line stays next to the beat it was written against.
    # Subscripting l["clip_start"] here raised KeyError the same way the render
    # clip loop did - see pipeline/render.py INTRO_OWNED.
    _INTRO_OWNED = ("over_montage", "film_intro")
    keys, last = {}, 0.0
    for i, l in enumerate(lines):
        if any(l.get(k) for k in _INTRO_OWNED):
            keys[id(l)] = (0, -1.0, i)          # front, authored order
            continue
        cs = l.get("clip_start")
        if cs:
            try:
                last = pt(cs)
            except Exception:
                missing.append(f"line {l.get('id')}: bad clip_start {cs!r}")
        keys[id(l)] = (1, last, i)              # untimed -> stays in place
    lines.sort(key=lambda l: keys[id(l)])
    for i, l in enumerate(lines, 1):
        l["id"] = i

    adj = [l["id"] for l in lines if l.get("window_adjusted")]
    words = sum(len(str(l.get("narration", "")).split()) for l in lines)
    title = a.title
    if not title:
        # H1 cua beat map la nguon gan nhat cho ten phim.
        bp = pdir / "beats_proposal.md"
        if bp.exists():
            for ln in io.open(bp, encoding="utf-8-sig").read().splitlines():
                if ln.startswith("# "):
                    title = re.sub(r"\s*[-\u2013]\s*Beat List.*$", "",
                                   ln[2:]).strip()
                    break
    if not title:
        title = a.project
    out = {"title": title, "target_minutes": a.target,
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

    # --- PHASE 1: bao cao ngay tai cho, truoc khi validator chay -----------
    import statistics as _st
    narr = [l for l in lines if str(l.get("narration", "")).strip()]
    if narr:
        wl = [len(str(l["narration"]).split()) for l in narr]
        sd = _st.pstdev(wl) if len(wl) > 1 else 0.0
        print(f"words/line: mean {_st.mean(wl):.1f}  SD {sd:.1f} "
              f"(bar 9.0; human reference 13.7)")
        pay = {}
        for l in narr:
            pay[l.get("payload") or "(none)"] = pay.get(
                l.get("payload") or "(none)", 0) + 1
        print("payload: " + "  ".join(f"{k}={v}" for k, v in sorted(pay.items())))
        if pay.get("(none)"):
            print(f"  CANH BAO: {pay['(none)']} dong khong co `payload` - "
                  f"[PAYLOAD-MIX] se tu choi draft nay.")
        tags = {}
        for l in lines:
            tags[l.get("delivery") or "(none)"] = tags.get(
                l.get("delivery") or "(none)", 0) + 1
        print("delivery: " + "  ".join(f"{k}={v}" for k, v in sorted(tags.items())))
        for need in ("intro", "outro", "hook"):
            if not tags.get(need):
                print(f"  CANH BAO: khong co dong <{need}>.")

    # Tieu de "<Phim> (<nam>)" la mau tieu de yeu nhat cua the loai va bay gio
    # bi [HOOK] tu choi. Bao o day de khong phai cho den luc validator chay.
    if re.search(r"\(\s*(19|20)\d{2}\s*\)\s*$", title):
        print(f"  CANH BAO: tieu de {title!r} co dang '<Phim> (<nam>)'. "
              f"[HOOK] se tu choi. Dung --title de dat mot tieu de tien de: "
              f"[vai] + [tien de phi thuong] + [he qua bi giau].")
    print(f"da ghi {pdir / 'draft.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
