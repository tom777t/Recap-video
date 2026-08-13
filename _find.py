import json, io, re, sys
p = "projects/shutterisland2010_linear/transcript.json"
segs = json.load(io.open(p, encoding="utf-8-sig"))["segments"]
kw = sys.argv[1].lower()
for s in segs:
    if kw in (s.get("text") or "").lower():
        t = float(s["start"])
        print(f'{int(t)//3600:02d}:{int(t)%3600//60:02d}:{int(t)%60:02d}  {s["text"].strip()[:88]}')