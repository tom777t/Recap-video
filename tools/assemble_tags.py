# -*- coding: utf-8 -*-
"""
assemble_tags.py - gom shots.json.d/*.json thanh mot file, va BAO CAO LO HONG.

Vi sao ton tai
--------------
Moi shot duoc tag boi mot subagent rieng, context rieng, ghi ra mot file rieng.
Do la ca diem manh (khong co context decay: shot thu 250 khong he "met" hon shot
thu 1) va diem yeu (khong ai nhin thay toan canh). Script nay la cho toan canh
duoc kiem tra.

Nguyen tac lay tu chinh cac loi da mac trong ngay 2026-09-05:
  * Thieu file KHONG bao gio duoc im lang. Mot catalogue thieu 12/250 shot ma
    khong noi gi thi te hon la khong co catalogue.
  * Khong bao gio ghi de ban co san bang du lieu rong (xem muc "guard that bai"
    trong docs/VISION_EVAL_AUTH.md).
  * Ghi tung shot, khong ghi nguyen khoi - that bai cua mot shot khong duoc
    keo theo 249 shot kia.

Dung:
    python tools/assemble_tags.py <project> [--expect 250] [--out shots_tagged.json]
"""
from __future__ import annotations
import argparse, io, json, os, re, sys

VISIBLE = {"action", "dialogue", "establishing", "montage", "reaction",
           "transition"}
STORY = {"aftermath", "discovery", "emotion", "reveal", "setup"}
VOCAB = VISIBLE | STORY


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--expect", type=int, default=0,
                    help="so shot KY VONG co; thieu se bi bao")
    ap.add_argument("--out", default="shots_tagged.json")
    a = ap.parse_args()

    root = os.path.join("projects", a.project)
    d = os.path.join(root, "shots.json.d")
    if not os.path.isdir(d):
        print(f"khong co {d}")
        return 1

    entries, problems = {}, []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(d, fn)
        try:
            obj = json.load(io.open(p, encoding="utf-8-sig"))
        except Exception as e:
            problems.append(f"{fn}: khong parse duoc JSON - {e}")
            continue
        tag = obj.get("shot") or os.path.splitext(fn)[0]
        dep = [str(x).strip().lower() for x in (obj.get("depicts") or [])]
        ch = [str(x).strip() for x in (obj.get("chars") or [])]
        act = (obj.get("action") or "").strip()

        bad = [x for x in dep if x not in VOCAB]
        if bad:
            problems.append(f"{tag}: nhan ngoai tu vung: {', '.join(bad)}")
        if not (set(dep) & VISIBLE):
            problems.append(f"{tag}: KHONG co nhan VISIBLE nao "
                            f"(depicts={dep or '[]'}) - se cham 0 tren truc nhin")
        if not act:
            problems.append(f"{tag}: action rong")
        if not ch:
            problems.append(f"{tag}: chars rong")
        entries[tag] = {"shot": tag, "depicts": dep, "chars": ch,
                        "action": act}

    def num(t):
        m = re.search(r"(\d+)", t)
        return int(m.group(1)) if m else 0

    got = sorted(entries, key=num)
    print(f"gom duoc {len(got)} shot tu {d}")

    if a.expect:
        have = {num(t) for t in got}
        missing = [n for n in range(1, a.expect + 1) if n not in have]
        if missing:
            # D-GREEN: mot audit thieu input PHAI noi ra, khong bao gio bao sach
            print(f"\nTHIEU {len(missing)}/{a.expect} shot: "
                  f"{', '.join(f'shot{n:02d}' for n in missing[:20])}"
                  f"{' ...' if len(missing) > 20 else ''}")
            print("  -> chay lai RIENG nhung shot nay; khong can lam lai ca lo.")
        else:
            print(f"du ca {a.expect} shot.")

    if problems:
        print(f"\n{len(problems)} van de:")
        for p in problems:
            print(f"  {p}")
    else:
        print("khong co van de ve tu vung / truong rong.")

    out = os.path.join(root, a.out)
    if os.path.exists(out):
        print(f"\n{a.out} da ton tai - KHONG ghi de. Xoa hoac doi --out.")
        return 1
    io.open(out, "w", encoding="utf-8").write(
        json.dumps({"shots": [entries[t] for t in got]},
                   ensure_ascii=False, indent=2))
    print(f"\nda ghi {out} ({len(got)} shot)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
