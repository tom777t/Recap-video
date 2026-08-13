import json, io, statistics as st
pt = lambda s: sum(float(x)*m for x, m in zip(str(s).split(":"), (3600, 60, 1)))
print(f'{"phim":<34}{"shot":>5}{"trung vi":>10}{"tb":>8}{"dai nhat":>10}{">20s":>7}')
for p in ["johnwick2014_linear", "interstellar2014_linear",
          "spidermannowayhome2021_linear", "shutterisland2010_linear"]:
    S = json.load(io.open(f"projects/{p}/shots.json", encoding="utf-8-sig"))["shots"]
    d = [pt(s["clip_end"]) - pt(s["clip_start"]) for s in S
         if s.get("clip_start") and s.get("clip_end")]
    long = sum(1 for x in d if x > 20)
    print(f'{p:<34}{len(d):>5}{st.median(d):>9.1f}s{st.mean(d):>7.1f}s'
          f'{max(d):>9.1f}s{long:>4} ({100*long/len(d):.0f}%)')