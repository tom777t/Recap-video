"""Cham diem phieu VISION_EVAL.md da dien, so voi tag lam tay.

    python score_vision_eval.py <project>

Cham RIENG hai cot, vi chung la hai bai toan kho khac han nhau:
  - depicts : phan loai kieu canh. Nhin khung hinh la doan duoc.
  - chars   : ai trong khung. Kho hon nhieu, va la cho da hong trong lich su
              (vu lan Sandman/Electro o Spider-Man -> sinh ra rule A5 + A6).

Cot `action` khong cham tu dong duoc (no la NGHIA) - script chi in canh nhau
de ban tu doc.

Luu y ve `(khong ro)`: model tu nhan khong ro KHONG bi tinh la sai. Rule A5 noi
ro "admit uncertainty + flag" la hanh vi DUNG. No duoc dem rieng thanh "tu bo
qua", vi mot model biet im lang khi khong chac thi dung duoc; mot model doan bua
thi khong.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

UNSURE = ("khong ro", "không rõ", "unclear", "unsure", "n/a", "-", "")


def norm(s: str) -> str:
    s = s.strip().strip("`").strip("()[]").strip()
    return re.sub(r"\s+", " ", s.lower())


def split_list(s: str) -> list[str]:
    s = s.strip()
    if not s or norm(s) in UNSURE:
        return []
    return [norm(x) for x in re.split(r"[,;/]", s) if norm(x)]


def parse_sheet(path: Path) -> dict:
    out, cur = {}, None
    for raw in io.open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        m = re.match(r"^###\s+(shot\d+)", line.strip(), re.I)
        if m:
            cur = m.group(1).lower()
            out[cur] = {"depicts": "", "chars": "", "action": ""}
            continue
        if not cur:
            continue
        m = re.match(r"^\s*[-*]\s*(depicts|chars|action)\s*:\s*(.*)$", line, re.I)
        if m:
            out[cur][m.group(1).lower()] = m.group(2).strip()
    return out


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    proj = sys.argv[1]
    pdir = config.project_dir(proj)
    truth = json.load(io.open(pdir / "_vision_truth.json", encoding="utf-8"))
    ans = parse_sheet(pdir / "VISION_EVAL.md")

    filled = [k for k in truth if ans.get(k, {}).get("depicts", "").strip()]
    print(f"da dien {len(filled)}/{len(truth)} shot")
    if not filled:
        print("chua dien gi - dua VISION_EVAL.md cho OpenCode truoc")
        return

    # ---------- depicts ----------
    exact = overlap = zero = 0
    confuse: dict[tuple[str, str], int] = {}
    for k in filled:
        t = {norm(x) for x in truth[k]["depicts"]}
        a = set(split_list(ans[k]["depicts"]))
        if a == t:
            exact += 1
        elif a & t:
            overlap += 1
        else:
            zero += 1
            for x in sorted(t):
                for y in sorted(a):
                    confuse[(x, y)] = confuse.get((x, y), 0) + 1

    n = len(filled)
    print("=" * 62)
    print("DEPICTS")
    print(f"  CO CHUNG >=1 TAG     : {exact+overlap}/{n}  ({100*(exact+overlap)/n:.0f}%)  <- so chinh")
    print(f"    trong do khop han  : {exact}/{n}  ({100*exact/n:.0f}%)")
    print(f"  truot han            : {zero}/{n}  ({100*zero/n:.0f}%)")
    print("  (Luu y: shot lam tay la CUA SO nhieu khoanh khac - vd mot window 17s")
    print("   vua co dialogue vua co emotion - nen 'khop han' la nguong qua chat.")
    print("   'Co chung >=1 tag' moi la thuoc do dung voi ground truth kieu nay.)")
    if confuse:
        print("  hay nham (tay -> may):")
        for (x, y), c in sorted(confuse.items(), key=lambda kv: -kv[1])[:8]:
            print(f"    {x} -> {y}  x{c}")

    # ---------- chars ----------
    tp = fp = fn = 0
    abstain_items = 0
    abstain_shots = 0
    for k in filled:
        t = {norm(x) for x in truth[k]["chars"]}
        raw = ans[k]["chars"]
        items = split_list(raw)
        # QUAN TRONG: '(khong ro)' co the nam LAN trong danh sach - vd
        # "Teddy Daniels, (khong ro)". Phai tach no ra, khong duoc tinh la mot
        # cai ten bia. Ban truoc cua script nay dem nham nhu vay va thoi phong
        # con so "bia them".
        named = [x for x in items if x not in UNSURE]
        abstain_items += len(items) - len(named)
        if not named:
            abstain_shots += 1
            if items:
                continue
        a = set(named)
        # so khop long: ten tay "Dr. Cawley" vs may "Cawley"
        matched = set()
        for x in t:
            if any(x in y or y in x for y in a):
                matched.add(x)
        tp += len(matched)
        fn += len(t - matched)
        fp += sum(1 for y in a if not any(y in x or x in y for x in t))

    print("-" * 62)
    print("CHARS")
    print(f"  nhan dung   : {tp}")
    print(f"  bo sot      : {fn}   (gom ca nguoi no tu nhan khong ro)")
    print(f"  bia them    : {fp}   <- nguy hiem nhat (dat ten sai cho nguoi co that)")
    print(f"  tu bo qua   : {abstain_items} luot '(khong ro)' "
          f"tren {abstain_shots}/{n} shot - day la hanh vi DUNG (rule A5)")
    if tp + fp:
        print(f"  do chinh xac: {100*tp/(tp+fp):.0f}%   (trong so cai no DAM dat ten)")
    if tp + fn:
        print(f"  do phu      : {100*tp/(tp+fn):.0f}%")

    # ---------- chars: soi tung truong hop lech ----------
    # Cot "bia them" chi co nghia neu ta biet no bia CAI GI. Ground truth la
    # nhan cho CA CUA SO 17-30s, con model chi thay 3 frame tinh - nen mot cai
    # ten "bia" co the la nguoi CO THAT tren man hinh ma nguoi tag khong liet ke.
    # Khong doc tay tung cai thi khong tach duoc "model sai" khoi "ground truth tho".
    print("-" * 62)
    print("CHARS - tung shot lech (tay | may):")
    for k in filled:
        t = {norm(x) for x in truth[k]["chars"]}
        named = [x for x in split_list(ans[k]["chars"]) if x not in UNSURE]
        a = set(named)
        extra = [y for y in a if not any(y in x or x in y for x in t)]
        miss = [x for x in t if not any(x in y or y in x for y in a)]
        if not extra and not miss:
            continue
        print(f"  [{k}]")
        print(f"    tay : {', '.join(sorted(t)) or '(rong)'}")
        print(f"    may : {', '.join(sorted(a)) or '(khong ro)'}")
        if extra:
            print(f"    -> may THEM: {', '.join(extra)}")
        if miss:
            print(f"    -> may SOT : {', '.join(miss)}")

    # ---------- action ----------
    print("=" * 62)
    print("ACTION - khong cham tu dong duoc, doc canh nhau:")
    for k in filled[:10]:
        print(f"\n  [{k}]")
        print(f"    tay: {truth[k]['action'][:110]}")
        print(f"    may: {ans[k]['action'][:110]}")

    print("\n" + "=" * 62)
    print("Doc ket qua:")
    print("  depicts cao + chars thap -> may tag depicts, NGUOI lam chars. Van la thang lon.")
    print("  chars 'bia them' > 0     -> chua the tin. Phai ep no ghi '(khong ro)' manh hon.")
    print("  ca hai deu thap          -> frame tinh khong du; can nhieu frame hon / model khac.")


if __name__ == "__main__":
    main()
