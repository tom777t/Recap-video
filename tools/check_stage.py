# -*- coding: utf-8 -*-
"""
check_stage.py - tra loi MOT cau hoi ve trang thai mot project, bang MOT dong
tren stdout, de run.ps1 quyet dinh bo qua hay chay lai mot buoc.

Vi sao khong chi dung Test-Path: "co file" khong phai "xong". spans.json tung
ton tai day du trong khi 12/30 span mat sach frame o phan duoi - file co, buoc
hong, va khong gi phat hien ra. Moi cau hoi o day kiem CAI BEN TRONG.

Cau hoi:
    duration        thoi luong nguon, giay (tu _cuts.json)
    spans           OK | <ly do hong>
    tags-todo       danh sach span chua tag, hoac NONE
    beats-todo      so chunk con thieu (tren 8), hoac NONE
    acts-todo       so act chua viet, hoac NONE
    draft-round     so vong draft da chay (tu state.json)
    draft-round-inc tang bien dem len 1, in gia tri moi
"""
from __future__ import annotations
import io, json, os, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

N_BEAT_CHUNKS = 8


def jload(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def main() -> int:
    proj, q = sys.argv[1], sys.argv[2]
    pdir = config.project_dir(proj)

    if q == "duration":
        c = jload(pdir / "_cuts.json", {})
        cuts = sorted(float(x) for x in (c.get("cuts") or [])
                      if isinstance(x, (int, float)))
        print(f"{cuts[-1]:.0f}" if cuts else "0")
        return 0

    if q == "spans":
        m = jload(pdir / "spans.json")
        if not m:
            print("MISSING")
            return 0
        bad = []
        for s in m.get("spans", []):
            fs = s.get("frames") or []
            if any(not isinstance(f, dict) for f in fs):
                bad.append(f"{s['id']}:frames-not-mapped")
                continue
            have = {f.get("shot_i") for f in fs}
            miss = [i for i in range(len(s.get("shots") or [])) if i not in have]
            if miss:
                bad.append(f"{s['id']}:{len(miss)}-shots-no-frame")
        print("OK" if not bad else "BAD " + " ".join(bad[:6]))
        return 0

    if q == "tags-todo":
        m = jload(pdir / "spans.json", {})
        ids = [s["id"] for s in m.get("spans", [])]
        d = pdir / "spans.json.d"
        have = {f.stem for f in d.glob("*.json")} if d.exists() else set()
        todo = [i for i in ids if i not in have]
        print(" ".join(todo) if todo else "NONE")
        return 0

    if q == "beats-todo":
        d = pdir / "beats.json.d"
        have = {f.stem for f in d.glob("chunk*.json")} if d.exists() else set()
        todo = [k for k in range(1, N_BEAT_CHUNKS + 1)
                if f"chunk{k}" not in have]
        print(len(todo) if todo else "NONE")
        return 0

    if q == "acts-todo":
        # So act lay tu beats_proposal.md (cac dong "ACT n"); khong co thi 4.
        bp = pdir / "beats_proposal.md"
        n = 0
        if bp.exists():
            import re
            n = len(re.findall(r"^ACT \d", bp.read_text(encoding="utf-8-sig"),
                               re.M))
        n = n or 4
        d = pdir / "draft.json.d"
        have = {f.stem for f in d.glob("act*.json")} if d.exists() else set()
        # act4 co the bi chia thanh act4a/act4b - coi la da co neu co tien to
        todo = [k for k in range(1, n + 1)
                if not any(h.startswith(f"act{k}") for h in have)]
        print(len(todo) if todo else "NONE")
        return 0

    if q in ("draft-round", "draft-round-inc"):
        sp = pdir / "state.json"
        st = jload(sp, {}) or {}
        cur = int(st.get("draft_rounds", 0))
        if q == "draft-round-inc":
            cur += 1
            st["draft_rounds"] = cur
            io.open(sp, "w", encoding="utf-8").write(
                json.dumps(st, ensure_ascii=False, indent=2))
        print(cur)
        return 0

    print(f"UNKNOWN-QUESTION {q}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
