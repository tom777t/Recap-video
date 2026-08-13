import json, io
cuts = [float(c) for c in json.load(io.open(
    "projects/shutterisland2010_linear/_cuts.json", encoding="utf-8"))["cuts"]]
hms = lambda s: f"{int(s)//3600:02d}:{int(s)%3600//60:02d}:{int(s)%60:02d}"
best = []
for i, c in enumerate(cuts):
    if not (3900 <= c <= 4300):
        continue
    n = sum(1 for x in cuts if c <= x < c + 20)
    best.append((n, c))
best.sort(reverse=True)
print("cua so 20s co nhieu cu cat nhat (= cat nhanh = hon loan):")
for n, c in best[:6]:
    print(f"  {hms(c)}  {n} cu cat")