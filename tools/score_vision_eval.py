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

# .parent is tools/; config.py lives at the repo ROOT, one level up. The old
# line pointed at tools/ so `import config` raised ModuleNotFoundError and the
# scorer could not be run standalone at all.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

UNSURE = ("khong ro", "không rõ", "unclear", "unsure", "n/a", "-", "")

# `depicts` mixes two kinds of label. Only the left column is in the pixels;
# the right column is what the scene DOES for the story, which a model looking
# at frames cannot know and should not be marked wrong for missing.
VISIBLE_AXIS = {"action", "dialogue", "establishing", "montage",
                "reaction", "transition"}
STORY_AXIS = {"aftermath", "discovery", "emotion", "reveal", "setup"}


def load_cast_map(project):
    """{character_lower: actor_lower} from names.json, if it carries actors."""
    import config
    p = config.project_dir(project) / "names.json"
    if not p.exists():
        return {}
    try:
        nd = json.load(io.open(p, encoding="utf-8-sig"))
        names = nd.get("names", nd) if isinstance(nd, dict) else nd
    except Exception:
        return {}
    out = {}
    for n in names:
        if isinstance(n, dict) and n.get("character") and n.get("actor"):
            out[norm(n["character"])] = norm(n["actor"])
    return out


def canon(name, cast):
    """Actor behind a character name - the identity that survives a twist.

    Andrew Laeddis and Teddy Daniels are the same man; the hand tags switch to
    the true name after the reveal while a model going by face keeps the first
    one. Scoring them as two people penalised the model twice for being right.
    Falls back to the name itself when no actor is known.
    """
    if not cast:
        return name
    if name in cast:
        return cast[name]

    def toks(x):
        # titles are not identity; "Dr. Sheehan" and "Dr. Lester Sheehan" are
        # the same man, and substring matching misses that over a middle name
        return {t for t in re.split(r"[\s.]+", x) if t and t not in
                ("dr", "mr", "mrs", "ms", "deputy", "warden", "the")}

    nt = toks(name)
    if not nt:
        return name
    for ch, actor in cast.items():
        ct = toks(ch)
        if nt and ct and (nt <= ct or ct <= nt):
            return actor
    return name


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
    vis_hit = vis_total = 0
    story_only = 0
    no_depicts = 0
    vis_excluded_ids: list[str] = []
    confuse: dict[tuple[str, str], int] = {}
    for k in filled:
        t = {norm(x) for x in truth[k]["depicts"]}
        a = set(split_list(ans[k]["depicts"]))
        tv, av = t & VISIBLE_AXIS, a & VISIBLE_AXIS
        if tv:
            vis_total += 1
            if tv & av:
                vis_hit += 1
        elif t & STORY_AXIS:
            story_only += 1
            vis_excluded_ids.append(k)
        else:
            # dap an tham chieu khong co nhan NAO - truoc day roi thang qua khe
            # va bien mat khoi ca hai con dem. Phai dem va phai noi ra.
            no_depicts += 1
            vis_excluded_ids.append(k)
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
    n_excl = len(vis_excluded_ids)
    if vis_total:
        print(f"  TRUC NHIN THAY       : {vis_hit}/{vis_total}  "
              f"({100*vis_hit/vis_total:.0f}%)  <- SO CHINH")
        print(f"     cham {vis_total}/{n} shot | LOAI TRU {n_excl} shot")
        print(f"     (chi tinh shot ma tag tay co it nhat 1 nhan nhin-thay-duoc:")
        print(f"      {', '.join(sorted(VISIBLE_AXIS))})")
    else:
        print(f"  TRUC NHIN THAY       : KHONG CHAM DUOC shot nao "
              f"(LOAI TRU ca {n_excl}/{n})")
    if n_excl:
        # D-GREEN o tang cham diem: ca khong do duoc phai duoc GOI TEN, khong
        # bao gio duoc gop vao phan sai. Mot shot ma DAP AN THAM CHIEU khong co
        # nhan truc-nhin thi khong the cham tren truc do - phat no la do mau so,
        # khong phai do may sai.
        print(f"  LOAI TRU khoi mau so : {n_excl}/{n} shot "
              f"({100*n_excl/n:.0f}%) - KHONG tinh la sai")
        if story_only:
            print(f"     {story_only} shot: tag tay CHI co nhan truc-truyen "
                  f"({', '.join(sorted(STORY_AXIS))}) - khong nam trong pixel")
        if no_depicts:
            print(f"     {no_depicts} shot: tag tay KHONG co nhan depicts nao")
        print(f"     -> {', '.join(vis_excluded_ids[:12])}"
              f"{' ...' if n_excl > 12 else ''}")
        print(f"     Xem N1a trong docs/GATE_CANDIDATES.md: catalogue da ship "
              f"thieu nhan truc-nhin tren 39% shot cua badgenius2017.")
    print(f"  co chung >=1 tag bat ky: {exact+overlap}/{n}  ({100*(exact+overlap)/n:.0f}%)")
    print(f"    trong do khop han    : {exact}/{n}  ({100*exact/n:.0f}%)")
    if confuse:
        print("  hay nham (tay -> may):")
        for (x, y), c in sorted(confuse.items(), key=lambda kv: -kv[1])[:8]:
            print(f"    {x} -> {y}  x{c}")

    # ---------- chars ----------
    cast = load_cast_map(proj)
    if cast:
        print(f"\n  (alias tu names.json: {len(cast)} nhan vat co dien vien - "
              f"cung dien vien = cung nguoi)")
    tp = fp = fn = 0
    abstain_items = 0
    abstain_shots = 0
    extras_detail = []
    empty_ref_shots: list[str] = []
    empty_ref_names = 0
    for k in filled:
        t = {norm(x) for x in truth[k]["chars"]}
        raw = ans[k]["chars"]
        items = split_list(raw)

        # ---- mau so cho CHARS -------------------------------------------
        # Neu tag tay de `chars` RONG thi khong cham duoc shot nay tren truc
        # dat-ten: khong co gi de doi chieu. Ban truoc dem MOI cai ten may gan
        # o day thanh false positive, tuc la phat may vi tham chieu thieu.
        # N1b (docs/GATE_CANDIDATES.md): 28/30 shot co `chars` rong trong
        # catalogue badgenius2017 VAN co mat nguoi nhin ro - truong rong khong
        # co nghia la khong co ai trong khung.
        if not t:
            named_here = [x for x in items if x not in UNSURE]
            if named_here:
                empty_ref_shots.append(k)
                empty_ref_names += len(named_here)
            continue
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

        def same(x, y):
            if x in y or y in x:            # "Cawley" vs "Dr. Cawley"
                return True
            cx, cy = canon(x, cast), canon(y, cast)
            return bool(cx) and cx == cy    # Laeddis vs Teddy -> same actor

        matched = {x for x in t if any(same(x, y) for y in a)}
        tp += len(matched)
        fn += len(t - matched)
        extra = [y for y in a if not any(same(y, x) for x in t)]
        fp += len(extra)
        for y in extra:
            extras_detail.append((k, y))

    print("-" * 62)
    print("CHARS")
    print(f"  nhan dung   : {tp}")
    print(f"  bo sot      : {fn}   (gom ca nguoi no tu nhan khong ro)")
    print(f"  may thay THEM nguoi: {fp}   (sau khi gop alias)")
    if extras_detail:
        print("     -> KHONG tu dong la 'bia': tag tay chi ghi nhan vat TRONG TAM,")
        print("        nguoi dung nen / thoang qua khong duoc liet ke. Doc tung ca:")
        for k, y in extras_detail[:12]:
            print(f"        [{k}] {y}")
    print(f"  tu bo qua   : {abstain_items} luot '(khong ro)' "
          f"tren {abstain_shots}/{n} shot - day la hanh vi DUNG (rule A5)")
    n_cscored = n - len(empty_ref_shots)
    if empty_ref_shots:
        print(f"  LOAI TRU khoi mau so : {len(empty_ref_shots)}/{n} shot "
              f"({100*len(empty_ref_shots)/n:.0f}%) - tag tay de `chars` RONG")
        print(f"     {empty_ref_names} ten may gan tren nhung shot do KHONG "
              f"tinh la sai - khong co gi de doi chieu")
        print(f"     -> {', '.join(empty_ref_shots[:12])}"
              f"{' ...' if len(empty_ref_shots) > 12 else ''}")
        print(f"     Xem N1b trong docs/GATE_CANDIDATES.md: 28/30 shot co "
              f"`chars` rong VAN co mat nguoi nhin ro.")
    print(f"  cham tren   : {n_cscored}/{n} shot")
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

    def _same(x, y):
        if x in y or y in x:
            return True
        cx, cy = canon(x, cast), canon(y, cast)
        return bool(cx) and cx == cy

    for k in filled:
        t = {norm(x) for x in truth[k]["chars"]}
        named = [x for x in split_list(ans[k]["chars"]) if x not in UNSURE]
        a = set(named)
        extra = [y for y in a if not any(_same(y, x) for x in t)]
        miss = [x for x in t if not any(_same(x, y) for y in a)]
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
    print("  TRUC NHIN THAY >=90%  -> may tag duoc truc nay. Nguoi chi them truc truyen.")
    print("  chars: doc tung ca 'them nguoi' truoc khi ket luan - phan lon la nhan vat nen.")
    print("  'bo sot' cao ma cac ca deu o giua cua so -> loi LAY MAU, tang so frame.")


if __name__ == "__main__":
    main()
