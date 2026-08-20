import json, io
pt = lambda s: sum(float(x)*m for x,m in zip(str(s).split(":"), (3600,60,1)))
P = "projects/superbad2007/"
S = json.load(io.open(P+"shots.json", encoding="utf-8-sig"))["shots"]
L = json.load(io.open(P+"draft.json", encoding="utf-8-sig"))["lines"]
cen = [s for s in S if (s.get("censor") or "none") != "none"]
print(f'{"shot":<22}{"censor":<12}{"line":<7}{"khop khoa?"}')
print("-"*62)
applied = missed = 0
for s in cen:
    a, b = pt(s["clip_start"]), pt(s["clip_end"])
    inside = [l for l in L if l.get("clip_start") and a <= pt(l["clip_start"]) < b]
    if not inside:
        print(f'{s["clip_start"]:<22}{s["censor"]:<12}{"(khong)":<7}-')
        continue
    for l in inside:
        ok = (l.get("clip_start") == s["clip_start"] and l.get("clip_end") == s["clip_end"])
        if ok: applied += 1
        else:  missed += 1
        print(f'{s["clip_start"]:<22}{s["censor"]:<12}{str(l["id"]):<7}{"CO MO" if ok else "KHONG MO"}')
print("-"*62)
print(f"thuc su mo: {applied} | truot vi anchor A3: {missed}")