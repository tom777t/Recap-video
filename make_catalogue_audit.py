"""Doi chieu MO TA TAY trong shots.json voi HINH THAT trong tung cua so.

    python make_catalogue_audit.py <project>

Vi sao can: loat thi nghiem vision cho thay it nhat 2 muc cua Shutter Island
mo ta mot canh KHONG nam trong cua so cua chinh no - shot18 (01:56:00) ghi
"the lake-house memory" nhung 8 frame deu la phong hai dang; shot19 (02:03:20)
ghi "Andrew accepts the truth" nhung frame la canh ben ho.

Do la mot nguon drift, va la loai te nhat: moi gate deu TIN shots.json, nen
mot line bind vao shot do se ke chuyen A trong khi hinh chieu chuyen B, va
khong co gate nao bat duoc.

Viec nay de hon viec TAG: khong can biet nhan nao la chinh, chi can thay mo ta
va hinh co phai cung mot chuyen khong.

Dung lai frame da trich san trong vision_eval/ (chay make_vision_eval.py truoc).
Khong ghi gi vao pipeline.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    proj = sys.argv[1]
    pdir = config.project_dir(proj)
    truth_p = pdir / "_vision_truth.json"
    fdir = pdir / "vision_eval"
    if not truth_p.exists() or not fdir.exists():
        print("thieu _vision_truth.json hoac vision_eval/ - chay make_vision_eval.py truoc")
        return

    truth = json.load(io.open(truth_p, encoding="utf-8"))
    md = [
        "# CATALOGUE AUDIT", "",
        "Voi tung shot: doc mo ta tay, nhin HET cac frame, roi tra loi mo ta co",
        "dung voi hinh khong.", "",
        "Bao `SAI` chi khi hinh va mo ta la HAI CHUYEN KHAC NHAU (mo ta mot canh",
        "khong co trong cua so). Khong bao SAI vi cach dung tu long leo, vi mo ta",
        "them y nghia cot truyen, hay vi mo ta bo sot chi tiet nho.", "",
        "Neu cua so chua NHIEU canh va mo ta chi noi ve mot trong so do, ghi",
        "`khong chac` va noi ro cua so gom nhung canh nao.", "",
        "Dien vao dong `- verdict:` -> `OK` | `SAI` | `khong chac`, kem mot cau ly do.",
        "", "---", "",
    ]

    n = 0
    for key, v in sorted(truth.items()):
        frames = sorted(p.name for p in fdir.glob(f"{key}_*.jpg"))
        if not frames:
            continue
        n += 1
        md += [f"### {key}  ({v['clip_start']} -> {v['clip_end']})", "",
               f"**Mo ta tay:** {v.get('action', '')}", ""]
        md += [f"![{f}](vision_eval/{f})" for f in frames]
        md += ["", "- verdict: ", ""]

    out = pdir / "CATALOGUE_AUDIT.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"da tao {out} - {n} shot")
    print("Dua file nay cho model xem, roi doc lai cac dong verdict.")


if __name__ == "__main__":
    main()
