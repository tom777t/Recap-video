"""Chay bo de vision MU qua Gemini, dien vao VISION_EVAL.md.

    python tools/gemini_vision_eval.py <project> [--model gemini-2.5-flash]

Muc dich: tra loi cau "model free co du tot cho khau tag khong" bang SO,
khong phai bang cam giac. Ban da co 293 shot tag tay lam ground truth.

Quy trinh:
  1. tools/make_vision_eval.py <project>   -> sinh phieu MU + frame
  2. tools/gemini_vision_eval.py <project> -> Gemini dien phieu
  3. tools/score_vision_eval.py <project>  -> cham diem

Bo de phai MU: model khong duoc thay dap an, khong duoc doc transcript /
draft / shots.json. Script nay chi gui ANH + tu vung, dung nhu OpenCode da
lam o ba vong truoc, nen so sanh duoc.

Can: bien moi truong GEMINI_API_KEY, va `pip install google-genai`.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

DEPICTS_VOCAB = ["action", "aftermath", "dialogue", "discovery", "emotion",
                 "establishing", "montage", "reaction", "reveal", "setup",
                 "transition"]

PROMPT = """You are tagging one moment from a film, for a shot catalogue.

Look ONLY at the images. Do not guess from context you do not see.

Answer in exactly three lines, nothing else:

depicts: <1-2 values from this list, comma separated>
chars: <names of people you can clearly SEE, comma separated>
action: <one sentence describing what is happening on screen>

Allowed `depicts` values, and nothing else:
{vocab}

For `chars`: name only people you can identify with confidence. Recognising an
actor's face counts as identification. Guessing from scene context does not.
If you cannot identify someone who is visible, write (khong ro) rather than a
guess. List everyone who appears in ANY of the frames, not only the one you
think is most important.
{cast}"""


def _load_cast(pdir: Path) -> str:
    """Cast list, if names.json carries actors. Same input OpenCode had."""
    import json
    p = pdir / "names.json"
    if not p.exists():
        return ""
    try:
        nd = json.load(io.open(p, encoding="utf-8-sig"))
        names = nd.get("names", nd) if isinstance(nd, dict) else nd
    except Exception:
        return ""
    rows = [f"  {n['character']} - {n['actor']}"
            for n in names
            if isinstance(n, dict) and n.get("character") and n.get("actor")]
    if not rows:
        return ""
    return ("\n\nCast of this film (character - actor). Use it to put a name to "
            "a face you recognise:\n" + "\n".join(rows))


def parse_sheet(path: Path):
    """[(tag, [frame filenames])] in sheet order, test shots only."""
    out, cur, frames = [], None, []
    for raw in io.open(path, encoding="utf-8"):
        line = raw.strip()
        m = re.match(r"^###\s+(shot\d+)", line, re.I)
        if m:
            if cur:
                out.append((cur, frames))
            cur, frames = m.group(1).lower(), []
            continue
        m = re.match(r"^!\[.*?\]\(vision_eval/(.+?)\)", line)
        if m and cur:
            frames.append(m.group(1))
    if cur:
        out.append((cur, frames))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    # 2026-09-05: gemini-2.5-flash da bi Google khoa voi project MOI ("no longer
    # available to new users"). Van hien trong models.list VA GET .../models/
    # gemini-2.5-flash van tra 200 kem 'generateContent' - nhung goi that thi
    # 404. Danh sach model KHONG phai la kiem tra kha dung.
    ap.add_argument("--model", default="gemini-3.6-flash")
    ap.add_argument("--limit", type=int, default=0, help="chi chay N shot dau")
    ap.add_argument("--rpm", type=float, default=14.0,
                    help="request/phut. Free tier ~15, de 14 cho an toan")
    ap.add_argument("--force", action="store_true",
                    help="ghi phieu ngay ca khi co shot that bai (se XOA dap "
                         "an san co cua nhung shot do)")
    args = ap.parse_args()

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("thieu GEMINI_API_KEY trong bien moi truong")
        return 1

    # Kiem tra key CO HINH DANG that truoc khi goi mang.
    # 2026-09-05: bien moi truong chua dung 'AIzaXXXXXXXX...XXX' (placeholder,
    # 35/39 ky tu la chu X). Google tra ve "400 API key not valid", nghe giong
    # loi phia Google, va da dan den nhieu gio chan doan nham sang project /
    # billing / Vertex ADC. Mot input KHONG HOP LE phai bi goi ten ngay tai
    # nguon, dung de no hien ra thanh mot loi kho hieu o tang duoi.
    _bad = None
    if len(set(key)) <= 6 or key.count("X") > 8 or key.count("x") > 8:
        _bad = "trong giong PLACEHOLDER (qua it ky tu khac nhau / nhieu chu X)"
    elif not (key.startswith("AIza") or key.startswith("AQ.")):
        _bad = (f"tien to la {key[:4]!r} - key Gemini Developer API thuong bat "
                f"dau bang 'AIza', key Google Cloud kieu moi bang 'AQ.'")
    if _bad:
        print(f"GEMINI_API_KEY {_bad}.")
        print(f"  do dai={len(key)}  ky tu khac nhau={len(set(key))}  "
              f"tien to={key[:4]!r}")
        print("  Day KHONG phai loi cua Google - chua co credential that.")
        print("  Xem docs/VISION_EVAL_AUTH.md de biet cac duong con lai.")
        return 1

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("chay:  pip install google-genai")
        return 1

    pdir = config.project_dir(args.project)
    sheet = pdir / "VISION_EVAL.md"
    fdir = pdir / "vision_eval"
    if not sheet.exists() or not fdir.exists():
        print(f"thieu {sheet} hoac {fdir} - chay make_vision_eval.py truoc")
        return 1

    shots = parse_sheet(sheet)
    if args.limit:
        shots = shots[:args.limit]
    if not shots:
        print("khong doc duoc shot nao tu phieu")
        return 1

    prompt = PROMPT.format(vocab=", ".join(DEPICTS_VOCAB), cast=_load_cast(pdir))
    client = genai.Client(api_key=key)
    gap = 60.0 / max(1.0, args.rpm)

    print(f"{len(shots)} shot | model {args.model} | ~{args.rpm:.0f} req/phut")
    print(f"du kien ~{len(shots) * gap / 60:.1f} phut\n")

    answers, t0 = {}, time.time()
    for i, (tag, frames) in enumerate(shots, 1):
        parts = [prompt]
        for f in frames:
            fp = fdir / f
            if fp.exists():
                parts.append(types.Part.from_bytes(
                    data=fp.read_bytes(), mime_type="image/jpeg"))
        if len(parts) == 1:
            print(f"  {tag}: khong co frame - bo qua")
            continue

        started = time.time()
        try:
            r = client.models.generate_content(model=args.model, contents=parts)
            text = (r.text or "").strip()
        except Exception as e:
            # Khong bo qua im lang: mot shot that bai ma van ghi phieu se lam
            # diem cham sai ma khong ai biet.
            print(f"  {tag}: LOI - {str(e)[:90]}")
            text = ""

        d = c = a = ""
        for ln in text.splitlines():
            m = re.match(r"^\s*[-*]?\s*(depicts|chars|action)\s*:\s*(.*)$", ln, re.I)
            if m:
                k, v = m.group(1).lower(), m.group(2).strip()
                if k == "depicts":
                    d = v
                elif k == "chars":
                    c = v
                else:
                    a = v
        answers[tag] = (d, c, a)
        print(f"  {tag:<8} {time.time()-started:5.1f}s  {d[:28]:<30}{c[:40]}")

        if i < len(shots):
            time.sleep(max(0.0, gap - (time.time() - started)))

    # ---- AN TOAN: khong bao gio ghi de dap an bang ket qua RONG -------------
    # 2026-09-05: mot lan chay --limit 1 voi key hong da XOA dap an cua shot da
    # duoc dien san. Co che: khi goi API loi, ham gan answers[tag] = ("","",""),
    # va doan ghi ben duoi dan chuoi rong de len dong cu. Phieu nay la blind
    # eval - dap an trong do la du lieu goc, mat la mat han.
    #
    # Quy tac: neu CO shot nao that bai, khong ghi gi ca. Chay lai khi da co
    # credential that. Dung --force neu that su muon ghi de (vd co y xoa).
    # Phien ban dau cua guard nay TU CHOI GHI TOAN BO khi co bat ky shot nao
    # that bai. Ngay 2026-09-05 no lam mat 19/20 cau tra loi tot chi vi shot11
    # dinh 429 - roi lan chay lai dot sach quota free-tier (20 req/ngay/model).
    # All-or-nothing la SAI o ca hai dau: ban goc ghi de bang chuoi rong (mat du
    # lieu), ban guard vut het ket qua tot (mat cong + mat quota).
    #
    # Dung: ghi nhung shot THANH CONG, va khong dong den shot that bai.
    _failed = [t for t, v in answers.items() if not (v[0] or v[1] or v[2])]
    _ok = [t for t in answers if t not in _failed]
    if _failed:
        print(f"\n{len(_failed)}/{len(answers)} shot that bai: "
              f"{', '.join(_failed[:10])}{' ...' if len(_failed) > 10 else ''}")
        print(f"  -> GIU NGUYEN dap an cu cua nhung shot do (khong ghi de).")
        print(f"  -> Van ghi {len(_ok)} shot thanh cong.")
        if args.force:
            print("  --force: ghi de ca shot that bai bang chuoi rong.")

    # ---- ghi lai vao phieu, giu nguyen moi thu khac ----
    src = io.open(sheet, encoding="utf-8").read()
    cur = None
    out_lines = []
    for raw in src.splitlines():
        m = re.match(r"^###\s+(shot\d+)", raw.strip(), re.I)
        if m:
            cur = m.group(1).lower()
        m = re.match(r"^(\s*[-*]\s*)(depicts|chars|action)\s*:\s*(.*)$", raw, re.I)
        # chi ghi de khi shot nay CO ket qua that (hoac --force)
        if m and cur in answers and (any(answers[cur]) or args.force):
            k = m.group(2).lower()
            v = answers[cur][{"depicts": 0, "chars": 1, "action": 2}[k]]
            out_lines.append(f"{m.group(1)}{m.group(2)}: {v}")
            continue
        out_lines.append(raw)
    io.open(sheet, "w", encoding="utf-8").write("\n".join(out_lines))

    ok = sum(1 for v in answers.values() if v[0])
    print(f"\nda dien {ok}/{len(shots)} shot vao {sheet.name}"
          f"  ({(time.time()-t0)/60:.1f} phut)")
    if ok < len(shots):
        print(f"CANH BAO: {len(shots)-ok} shot khong co ket qua - diem cham se")
        print("lech. Xem log loi o tren truoc khi tin con so.")
    print(f"\nCham diem:  python tools/score_vision_eval.py {args.project}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
