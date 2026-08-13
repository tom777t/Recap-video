import json, io
P = "projects/shutterisland2010_linear/"
OLD, NS, NE = "01:32:10.0", "01:36:40.846", "01:36:58.197"

p = P + "shots.json"
d = json.load(io.open(p, encoding="utf-8-sig"))
for s in d["shots"]:
    if s.get("clip_start") == OLD:
        s["clip_start"], s["clip_end"] = NS, NE
        s["action"] = ("Back at the hospital, Cawley tells Teddy he arrived alone - "
                       "there never was a partner. (window re-anchored 2026-08-11 "
                       "from transcript + scene cuts; verified against frames)")
        print("shots.json:", s.get("id"), "->", NS, NE)
io.open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2))

p = P + "draft.json"
d = json.load(io.open(p, encoding="utf-8-sig"))
for l in d["lines"]:
    if str(l.get("clip_start", "")).startswith("01:32:10"):
        l["clip_start"], l["clip_end"] = NS, NE
        print("draft.json: line", l.get("id"), "->", NS, NE)
io.open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2))