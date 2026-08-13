import json, io
pt = lambda s: sum(float(x)*m for x, m in zip(str(s).split(":"), (3600, 60, 1)))
print(f'{"phim":<34}{"phu":>7}{"shot/phut":>11}')
for p in ["johnwick2014_linear", "interstellar2014_linear",
          "spidermannowayhome2021_linear", "shutterisland2010_linear"]:
    S = json.load(io.open(f"projects/{p}/shots.json", encoding="utf-8-sig"))["shots"]
    dur = json.load(io.open(f"projects/{p}/transcript.json", encoding="utf-8-sig")).get("duration")
    tot = sum(pt(s["clip_end"]) - pt(s["clip_start"]) for s in S
              if s.get("clip_start") and s.get("clip_end"))
    print(f'{p:<34}{100*tot/dur:>6.0f}%{len(S)/(dur/60):>10.2f}')