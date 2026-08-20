import sys; sys.path.insert(0, ".")
from pipeline import draft, catalogue
proj = "superbad2007"
info = catalogue.parse_beats(proj)
print("style      :", info.get("style"))
print("tier       :", info.get("tier"), "| declared ts_format:", info.get("ts_format"))
print("beats      :", len(info.get("beats") or []))
bt = draft.beat_times(proj)
print("doc theo   :", bt["fmt"], "(khai bao)" if bt["declared"] else "(mac dinh)")
for p in bt["problems"]:
    print("  [BEAT-MAP]", p)
if not bt["problems"]:
    o = bt["ordered"]
    print("beat dau   :", o[0][0], round(o[0][1]/60,1), "phut")
    print("beat cuoi  :", o[-1][0], round(o[-1][1]/60,1), "phut  (phim 118.7 phut)")
print("reveal map :", len(draft.parse_reveal_map(proj)), "muc")