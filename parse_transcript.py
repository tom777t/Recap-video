import json, sys

src = sys.argv[1] if len(sys.argv) > 1 else "transcript.vi-orig.json3"
out = sys.argv[2] if len(sys.argv) > 2 else "transcript.txt"

with open(src, encoding="utf-8") as f:
    data = json.load(f)

def fmt(ms):
    s = ms // 1000
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

lines = []
plain = []
for ev in data.get("events", []):
    segs = ev.get("segs")
    if not segs:
        continue
    text = "".join(seg.get("utf8", "") for seg in segs).strip()
    if not text or text == "\n":
        continue
    text = text.replace("\n", " ").strip()
    if not text:
        continue
    start = ev.get("tStartMs", 0)
    lines.append(f"[{fmt(start)}] {text}")
    plain.append(text)

with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

with open(out.replace(".txt", "_plain.txt"), "w", encoding="utf-8") as f:
    f.write(" ".join(plain))

print(f"Wrote {len(lines)} lines to {out}")
