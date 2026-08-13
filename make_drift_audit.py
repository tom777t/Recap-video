"""Doi chieu LOI KE (draft.json) voi HINH THAT - khong phai mo ta trong shots.json.

    python make_drift_audit.py <project>

Vi sao doi thuoc do: ban da tung dich cua so clip bang tay de chua drift, nhung
mo ta `action` trong shots.json thi khong sua theo. Nen ban audit truoc do -
so MO TA voi HINH - phat hien ra mo ta CU, chu chua han la video hong.

Cai quyet dinh chat luong video la: cau narration doc len co khop voi hinh dang
chieu khong. Mo ta chi la ghi chu trung gian.

Vi du that (Shutter Island):
  shot15  mo ta: "Cawley va Naehring noi Teddy den mot minh"   <- lech
          line 31: "When Teddy makes it back to the hospital"   <- KHOP hinh
  shot11  mo ta: "mot benh nhan lao vao Teddy suyt giet anh"    <- lech
          line 24: "one inmate rushes Teddy and nearly kills"   <- CUNG lech

Ca dau la mo ta cu. Ca sau la drift that. Chi phep do nay tach duoc hai thu do.

Dung frame da trich trong vision_eval/. Khong ghi gi vao pipeline.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def pt(t) -> float:
    return sum(float(x) * m for x, m in zip(str(t).split(":"), (3600, 60, 1)))


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    proj = sys.argv[1]
    pdir = config.project_dir(proj)
    truth_p, fdir = pdir / "_vision_truth.json", pdir / "vision_eval"
    if not truth_p.exists() or not fdir.exists():
        print("thieu _vision_truth.json hoac vision_eval/ - chay make_vision_eval.py truoc")
        return

    truth = json.load(io.open(truth_p, encoding="utf-8"))
    lines = json.load(io.open(pdir / "draft.json", encoding="utf-8-sig"))["lines"]

    md = [
        "# DRIFT AUDIT - loi ke vs hinh", "",
        "Voi tung muc: doc CAU NARRATION, nhin het cac frame, tra loi cau do co",
        "khop voi hinh dang chieu khong.", "",
        "Day KHONG phai so mo ta catalogue voi hinh - mo ta co the da cu sau khi",
        "cua so duoc dich tay de chua drift. Chi so LOI KE voi HINH.", "",
        "`OK`        - nguoi xem nghe cau nay va nhin hinh nay se thay khop",
        "`DRIFT`     - hinh dang chieu mot chuyen khac han voi cau dang doc",
        "`mot phan`  - khop y chinh nhung co frame lac sang canh khac", "",
        "Dien vao `- verdict:` kem mot cau ly do.", "", "---", "",
    ]

    n = 0
    for key, v in sorted(truth.items()):
        frames = sorted(p.name for p in fdir.glob(f"{key}_*.jpg"))
        if not frames:
            continue
        a, b = pt(v["clip_start"]), pt(v["clip_end"])
        bound = [l for l in lines
                 if l.get("clip_start") and a <= pt(l["clip_start"]) < b]
        if not bound:
            continue
        n += 1
        md += [f"### {key}  ({v['clip_start']} -> {v['clip_end']})", ""]
        for l in bound:
            md += [f"**Line {l.get('id')} doc len:** {l.get('narration', '')}", ""]
        md += [f"![{f}](vision_eval/{f})" for f in frames]
        md += ["", "- verdict: ", ""]

    out = pdir / "DRIFT_AUDIT.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"da tao {out} - {n} muc co line bind vao")


if __name__ == "__main__":
    main()
