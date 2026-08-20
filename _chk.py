import json, io, collections
pt = lambda s: sum(float(x)*m for x,m in zip(str(s).split(":"), (3600,60,1)))
P = "projects/superbad2007/"
S = json.load(io.open(P+"shots.json", encoding="utf-8-sig"))["shots"]
N = json.load(io.open(P+"names.json", encoding="utf-8-sig"))["names"]
known = {(n.get("character") or n).lower() for n in N}
VOCAB = {"action","aftermath","dialogue","discovery","emotion","establishing",
         "montage","reaction","reveal","setup","transition"}
print("shots:", len(S))
ids = [s.get("id") for s in S]
dup = [k for k,v in collections.Counter(ids).items() if v > 1]
print("id trung      :", dup or "khong")
bad_dep = [(s["id"], s.get("depicts")) for s in S
           if not s.get("depicts") or set(s["depicts"]) - VOCAB or len(s["depicts"]) > 2]
print("depicts sai   :", len(bad_dep)); [print("   ", b) for b in bad_dep[:6]]
bad_win = [s["id"] for s in S if not s.get("clip_start") or not s.get("clip_end")
           or pt(s["clip_end"]) <= pt(s["clip_start"])]
print("cua so hong   :", len(bad_win)); [print("   ", b) for b in bad_win[:6]]
order = [pt(s["clip_start"]) for s in S if s.get("clip_start")]
print("khong tang dan:", sum(1 for a,b in zip(order, order[1:]) if b < a))
unk = sorted({c for s in S for c in (s.get("chars") or []) if c.lower() not in known})
print("chars la      :", unk or "khong")
d = [pt(s["clip_end"])-pt(s["clip_start"]) for s in S]
print("do dai: trung vi %.1fs | tong phu %.0f%%" % (sorted(d)[len(d)//2], 100*sum(d)/(118.7*60)))