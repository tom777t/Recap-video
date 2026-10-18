# -*- coding: utf-8 -*-
"""
assemble_moments.py - gom `spans.json.d/*.json` thanh `windows_llm.json`.

Quy tac seam (ghim trong docs/WINDOW_GROUPING_V2_CRITERION.md):
  1. span i SO HUU [own_start, own_end)
  2. moment thuoc ve span nao chua DIEM GIUA cua no -> moment vat qua seam duoc
     giu NGUYEN VEN, dung MOT lan, boi span giu phan lon no
  3. mau thuan con lai go deterministic:
       - chong lan: cat tai cu cat that gan giua vung chong lan nhat
       - ho: keo moment truoc den dau moment sau
  4. MOI dieu chinh deu duoc DEM va BAO CAO. Neu seam phai chinh nhieu thi
     co che overlap da that bai, va con so noi dieu do.

Khong bao gio im lang: span thieu / hong duoc goi ten, va thoi gian chung bo
trong duoc bao cao nhu mot lo hong, khong phai lam tron.

Dung:
    python tools/assemble_moments.py <project>
"""
from __future__ import annotations
import argparse, bisect, io, json, os, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

VISIBLE = {"action", "dialogue", "establishing", "montage", "reaction", "transition"}
STORY = {"aftermath", "discovery", "emotion", "reveal", "setup"}
VOCAB = VISIBLE | STORY
CENSOR = {"none", "blur_light", "blur_heavy"}


def pt(ts) -> float:
    p = [float(x) for x in str(ts).split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def hms(s: float) -> str:
    s = max(0.0, float(s))
    return f"{int(s)//3600:02d}:{(int(s)%3600)//60:02d}:{s%60:06.3f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--out", default="windows_llm.json")
    a = ap.parse_args()
    pdir = config.project_dir(a.project)

    sp = pdir / "spans.json"
    if not sp.exists():
        # Mot stage cua pipeline phai that bai bang MOT CAU, khong phai bang
        # traceback - nguoi doc can biet chay lai cai gi, khong can stack.
        print(f"thieu {sp}\n"
              f"  chay truoc: python tools/make_spans.py {a.project} "
              f"--from 0 --to <duration>")
        return 1
    meta = json.load(io.open(sp, encoding="utf-8"))
    cuts = sorted(float(x) for x in
                  json.load(io.open(pdir / "_cuts.json", encoding="utf-8"))["cuts"])
    d = pdir / "spans.json.d"
    spans = {s["id"]: s for s in meta["spans"]}

    kept, problems, missing = [], [], []
    for sid, sp in sorted(spans.items()):
        f = d / f"{sid}.json"
        if not f.exists():
            missing.append(sid)
            continue
        try:
            obj = json.load(io.open(f, encoding="utf-8"))
        except Exception as e:
            problems.append(f"{sid}: khong doc duoc JSON ({e})")
            missing.append(sid)
            continue
        moms = obj.get("moments") or []
        shots = sp["shots"]
        nsh = len(shots)
        seen, ok_span = [], True
        for k, m in enumerate(moms):
            idx = m.get("shots") or []
            if not idx or list(idx) != list(range(idx[0], idx[-1] + 1)):
                problems.append(f"{sid}#{k}: shots khong lien tiep {idx}")
                ok_span = False
                continue
            if idx[0] < 0 or idx[-1] >= nsh:
                problems.append(f"{sid}#{k}: chi so shot ngoai pham vi {idx}")
                ok_span = False
                continue
            seen += list(idx)
            a0, b0 = shots[idx[0]]["start"], shots[idx[-1]]["end"]
            try:
                ca, cb = pt(m["clip_start"]), pt(m["clip_end"])
            except Exception:
                ca, cb = a0, b0
            if abs(ca - a0) > 0.05 or abs(cb - b0) > 0.05:
                problems.append(
                    f"{sid}#{k}: moc khong khop shot list "
                    f"({m.get('clip_start')}..{m.get('clip_end')} vs "
                    f"{hms(a0)}..{hms(b0)}) - dung shot list")
            dep = [str(x).strip().lower() for x in (m.get("depicts") or [])]
            badv = [x for x in dep if x not in VOCAB]
            if badv:
                problems.append(f"{sid}#{k}: depicts ngoai tu vung {badv}")
            if not (set(dep) & VISIBLE):
                problems.append(f"{sid}#{k}: KHONG co nhan VISIBLE "
                                f"(depicts={dep or '[]'}) - cham 0 tren truc nhin")
            cen = str(m.get("censor", "none")).strip().lower()
            if cen not in CENSOR:
                problems.append(f"{sid}#{k}: censor la {cen!r}")
                cen = "none"
            kept.append({"span": sid, "a": a0, "b": b0, "mid": (a0 + b0) / 2,
                         "shots": list(idx), "depicts": dep,
                         "chars": [str(x) for x in (m.get("chars") or [])],
                         "action": str(m.get("action", "")).strip(),
                         "censor": cen,
                         **({"censor_note": m["censor_note"]}
                            if m.get("censor_note") else {})})
        if ok_span and sorted(seen) != list(range(nsh)):
            miss = sorted(set(range(nsh)) - set(seen))
            dup = sorted({x for x in seen if seen.count(x) > 1})
            problems.append(f"{sid}: khong lat kin span "
                            f"(thieu {miss[:6]}{'...' if len(miss) > 6 else ''}, "
                            f"trung {dup[:6]})")

    # --- quy tac so huu theo DIEM BAT DAU ----------------------------------
    # 2026-09-08: ban dau la DIEM GIUA, va no SAI - test MOMENT-SEAM bat duoc.
    # Vung overlap chi noi VE PHIA TRUOC (ext_end), nen mot moment vat qua seam
    # CHI CO THE do span TRUOC sinh ra - span sau bat dau tu chinh cai seam do,
    # no khong bao gio nhin thay phan dau. Giao quyen so huu cho span chua diem
    # giua tuc la giao cho span KHONG THE sinh ra no -> moment bi roi mat hoan
    # toan, roi buoc va-ho lang le lap lai cho trong bang mot cua so khac.
    # Tren badgenius day chinh la 13 lan va-ho va 85.79s dich chuyen.
    # Dung quy tac: span nao chua DIEM BAT DAU thi giu, va duoc giu NGUYEN VEN
    # ke ca khi no chay qua mep.
    own = []
    for m in kept:
        sp = spans[m["span"]]
        if sp["own_start"] <= m["a"] < sp["own_end"]:
            own.append(m)
    own.sort(key=lambda x: (x["a"], x["b"]))

    # --- go mau thuan con lai, DEM lai -------------------------------------
    adj_overlap, adj_gap, total_shift = 0, 0, 0.0
    out = []
    for m in own:
        if not out:
            out.append(m)
            continue
        prev = out[-1]
        if m["a"] < prev["b"] - 1e-6:                      # chong lan
            # Uu tien moment TRUOC: span truoc da nhin thay ca phan duoi voi
            # day du ngu canh, nen no la ben co co so de quyet dinh moment ket
            # thuc o dau. Cat dau moment sau ve bang duoi moment truoc.
            total_shift += prev["b"] - m["a"]
            m["a"] = prev["b"]
            adj_overlap += 1
            if m["b"] - m["a"] <= 1e-6:
                continue
        elif m["a"] > prev["b"] + 1e-6:                    # ho
            total_shift += m["a"] - prev["b"]
            prev["b"] = m["a"]
            adj_gap += 1
        if m["b"] > m["a"]:
            out.append(m)
    out = [m for m in out if m["b"] - m["a"] > 1e-6]

    reg = meta["region"]
    covered = sum(m["b"] - m["a"] for m in out)
    res = {
        "project": a.project,
        "generated_by": "tools/assemble_moments.py",
        "source": "LLM per-span grouping (tools/span_prompt.md)",
        "region": reg, "span_sec": meta["span_sec"], "overlap_sec": meta["overlap_sec"],
        "stats": {
            "spans_total": len(spans), "spans_missing": len(missing),
            "moments_raw": len(kept), "moments_kept": len(out),
            "dropped_not_owned": len(kept) - len(own),
            "seam_overlap_fixed": adj_overlap, "seam_gap_fixed": adj_gap,
            "seam_total_shift_sec": round(total_shift, 2),
            "coverage_pct": round(100 * covered / (reg[1] - reg[0]), 1),
            "median_window": round(sorted(m["b"] - m["a"] for m in out)[len(out)//2], 2) if out else 0,
            "validation_problems": len(problems),
        },
        "missing_spans": missing,
        "problems": problems,
        "windows": [{
            "id": f"m{i:04d}", "span": m["span"],
            "clip_start": hms(m["a"]), "clip_end": hms(m["b"]),
            "start_sec": round(m["a"], 3), "end_sec": round(m["b"], 3),
            "raw_duration_sec": round(m["b"] - m["a"], 3),
            "n_shots": len(m["shots"]),
            "depicts": m["depicts"], "chars": m["chars"],
            "action": m["action"], "censor": m["censor"],
            **({"censor_note": m["censor_note"]} if m.get("censor_note") else {}),
        } for i, m in enumerate(out, 1)],
    }
    io.open(pdir / a.out, "w", encoding="utf-8").write(
        json.dumps(res, ensure_ascii=False, indent=2))

    # --- catalogue may, schema ma pipeline doc duoc ------------------------
    # KHONG co truong `beat`: trong luong that, beat map duoc viet SAU
    # catalogue, va viec gan dong vao beat la viec cua nguoi viet draft.
    cat = {
        "_comment": ("Catalogue MAY. make_spans.py -> span tagging "
                     "(span_prompt.md) -> assemble_moments.py. "
                     "KHONG doc shots.json hay beats_proposal.md."),
        "_source": "LLM span grouping",
        "_window_adjust_rule": (
            "Dong draft nao khong co moment nao phu du thi NGUOI VIET duoc phep "
            "noi cua so ra cac cu cat gan nhat trong _cuts.json, va PHAI danh "
            "dau window_adjusted: true de no hien ra o khau review."),
        "project": a.project,
        "depth_target": len(res["windows"]),
        "shots": [{
            "id": f"clip:{w['clip_start'][:8]}",
            "clip_start": w["clip_start"], "clip_end": w["clip_end"],
            "chars": w["chars"], "depicts": w["depicts"],
            "action": w["action"], "censor": w["censor"],
            "raw_duration_sec": w["raw_duration_sec"],
            # KHONG author `max_narration_words_en`. Lan dau toi co ghi no bang
            # (dur*1.4-0.6)*3.0 va [CAPACITY-BASIS] bat ngay: tran tu-viet lech
            # 11% so voi tran pipeline tu suy ra, tuc la hai CO SO capacity khac
            # nhau cung ton tai va fill%/CAPACITY-WORDS tieu thu chung nhu the
            # chung so sanh duoc. Mot dai luong, mot co so - de pipeline suy ra.
            "extendable": True, "stretch_tolerance": 1.4,
            **({"censor_note": w["censor_note"]} if w.get("censor_note") else {}),
        } for w in res["windows"]],
    }
    io.open(pdir / "shots_machine.json", "w", encoding="utf-8").write(
        json.dumps(cat, ensure_ascii=False, indent=2))
    s = res["stats"]
    print(f"span {s['spans_total']} | THIEU {s['spans_missing']} "
          f"{missing if missing else ''}")
    print(f"moment: {s['moments_raw']} tho -> {s['moments_kept']} giu "
          f"({s['dropped_not_owned']} bo vi span khac so huu diem BAT DAU)")
    print(f"seam: chong lan {s['seam_overlap_fixed']} | ho {s['seam_gap_fixed']} "
          f"| tong dich {s['seam_total_shift_sec']}s")
    print(f"phu {s['coverage_pct']}% vung | trung vi cua so {s['median_window']}s")
    if problems:
        print(f"\n{len(problems)} van de validation:")
        for p in problems[:12]:
            print(f"  {p}")
    print(f"\nda ghi {pdir / a.out}")
    print(f"catalogue may: {pdir / 'shots_machine.json'} "
          f"({len(res['windows'])} shot)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
