"""
migrate_draft_v1_to_v2.py - additive Phase 1 migration for an existing draft.json.

Adds the new OPTIONAL Phase 1 fields to each line WITHOUT touching any existing
field (id / narration / pool / clip_start / clip_end / hold / delivery / visual /
flashback / montage / setup_ok are all preserved exactly):

  unit_id        -> ""        (agent fills based on skeleton.json)
  covers         -> []        (agent fills with exact must_cover strings)
  claim          -> {"type": "narration", "requires_visual": false}  (safe default)
  narrative_jump -> false

The validator will surface what still needs real values. Idempotent: re-running
never overwrites a field the agent has already filled.

Usage:  python tools/migrate_draft_v1_to_v2.py --project NAME
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402


def migrate(project: str) -> int:
    dp = config.project_dir(project) / "draft.json"
    if not dp.exists():
        print(f"no draft.json in projects/{project}/")
        return 1
    d = json.loads(dp.read_text(encoding="utf-8-sig"))
    changed = 0
    for ln in d.get("lines", []):
        if "unit_id" not in ln:
            ln["unit_id"] = ""
            changed += 1
        if "covers" not in ln:
            ln["covers"] = []
        if "claim" not in ln:
            ln["claim"] = {"type": "narration", "requires_visual": False}
        if "narrative_jump" not in ln:
            ln["narrative_jump"] = False
    dp.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"migrated {changed} lines in projects/{project}/draft.json "
          f"(existing fields untouched). Now fill unit_id / covers / claim.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    sys.exit(migrate(args.project))
