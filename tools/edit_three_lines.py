"""
Edit exactly three narration lines, spread across the film, and record what
changed. This is the re-render benchmark's input.

    python tools/edit_three_lines.py --project tokyodrift2006 --apply
    python tools/edit_three_lines.py --project tokyodrift2006 --restore

The edit SHORTENS each line by one trailing word. Shortening is deliberate:
a longer line can breach its shot's capacity and trip [BINDING-VIOLATION],
which would turn a timing benchmark into a draft-repair session. Shorter text
cannot.

The three lines are picked at the 10%, 50% and 90% marks of the narrated
lines, not at random and not adjacent, because the question being measured is
"how much of the film gets rebuilt when three scattered lines change" - three
neighbours would sit inside one xfade batch and flatter the old pipeline.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

BACKUP = "draft_before_3line_edit.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()

    pdir = config.project_dir(a.project)
    dp = pdir / "draft.json"
    bp = pdir / BACKUP

    if a.restore:
        if not bp.exists():
            print(f"no {BACKUP} to restore from")
            return 1
        dp.write_text(bp.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"restored draft.json from {BACKUP}")
        return 0

    draft = json.loads(dp.read_text(encoding="utf-8-sig"))
    lines = draft["lines"]
    narrated = [l for l in lines
                if str(l.get("narration", "")).strip()
                and not l.get("narration_silence_seconds")
                and not l.get("film_speaks_seconds")]
    if len(narrated) < 10:
        print("too few narrated lines")
        return 1

    picks = [narrated[int(len(narrated) * f)] for f in (0.10, 0.50, 0.90)]

    if a.apply and not bp.exists():
        bp.write_text(dp.read_text(encoding="utf-8-sig"), encoding="utf-8")
        print(f"backed up draft.json -> {BACKUP}")

    changed = []
    for ln in picks:
        old = str(ln["narration"]).strip()
        words = old.split()
        if len(words) < 6:
            continue
        new = " ".join(words[:-1])
        # keep terminal punctuation so the read does not run on
        if old[-1] in ".!?" and new[-1] not in ".!?":
            new = new.rstrip(",;:") + old[-1]
        changed.append({"id": ln["id"], "words_before": len(words),
                        "words_after": len(new.split()),
                        "old_tail": " ".join(words[-4:]),
                        "new_tail": " ".join(new.split()[-4:])})
        if a.apply:
            ln["narration"] = new

    if a.apply:
        dp.write_text(json.dumps(draft, ensure_ascii=False, indent=2),
                      encoding="utf-8")

    print(f"{'APPLIED' if a.apply else 'DRY RUN'} - 3 lines edited:")
    for c in changed:
        print(f"  line {c['id']:>3}: {c['words_before']} -> "
              f"{c['words_after']} words   ...{c['old_tail']!r} -> "
              f"...{c['new_tail']!r}")
    ids = [c["id"] for c in changed]
    print(f"\nedited ids: {ids}")
    print(f"of {len(narrated)} narrated lines, so a content-keyed cache should "
          f"rebuild {len(ids)} clip(s) and reuse {len(narrated)-len(ids)}.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
