"""
Run the pipeline's OWN [VOICE-VISUAL] audit on the current and proposed
bindings, and print the comparison.

    python tools/measure_binding.py --project tokyodrift2006

The point is to use pipeline.binding_audit unchanged. A metric invented here
could flatter the prototype; the one the pipeline already reports cannot.

Both bindings are evaluated in THROWAWAY scratch projects
(projects/_p4_cur, projects/_p4_new) so the real draft.json is never written
to. schemas.load_draft/load_shots/load_names all read from a project dir, so
the scratch dirs get a copy of shots.json and names.json and nothing else.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from pipeline import schemas  # noqa: E402
from pipeline.binding_audit import binding_audit  # noqa: E402


def build(scratch: str, src_pdir: Path, draft: dict) -> Path:
    p = config.project_dir(scratch)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)
    p.mkdir(parents=True, exist_ok=True)
    for f in ("shots.json", "names.json"):
        if (src_pdir / f).exists():
            shutil.copy2(src_pdir / f, p / f)
    (p / "draft.json").write_text(
        json.dumps(draft, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def _widen_claim_types() -> list[str]:
    """Let the audit load the CURRENT draft at all.

    THIS IS A DEFECT ON main, NOT A CONVENIENCE HERE.
    `schemas.load_draft('tokyodrift2006')` raises on origin/main (06bcd9a):
    the draft uses claim.type 'aftermath', 'establishing' and 'montage', and
    schemas._CLAIM_TYPES lists none of them. draft.py wraps that load in a
    try/except that prints "Phase 1 audits skipped (draft parse)" and returns
    - so [VOICE-VISUAL] and the other Phase 1 audits DO NOT RUN on the
    shipped draft, and nothing says so louder than one dim line. That is the
    "a gate that fails silently" class the Stage 2 plan opens with.

    The whitelist is widened IN MEMORY, from this measurement tool only. No
    repo file is edited, and both arms of the comparison get the identical
    patch, so the current-vs-proposed numbers stay comparable. The real fix
    belongs to whoever owns the draft schema.
    """
    extra = ["aftermath", "establishing", "montage"]
    added = [t for t in extra if t not in schemas._CLAIM_TYPES]
    for t in added:
        schemas._CLAIM_TYPES.add(t) if isinstance(
            schemas._CLAIM_TYPES, set) else schemas._CLAIM_TYPES.append(t)
    return added


def audit(scratch: str) -> dict:
    d = schemas.load_draft(scratch)
    shots_by_id, pool_families, problems = schemas.load_shots(scratch)
    names = schemas.load_names(scratch)
    r = binding_audit(d, shots_by_id, pool_families, names)
    kinds: dict[str, int] = {}
    for i in r.issues:
        kinds[i.issue] = kinds.get(i.issue, 0) + 1
    return {
        "verified_match": r.verified_match,
        "verified_mismatch": r.verified_mismatch,
        # `mismatches` is a property on BindingResult, not a method.
        "mismatches": len(r.mismatches),
        "issues_total": len(r.issues),
        "by_kind": kinds,
        "footage_dropped": len(problems),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--draft", default="draft_a2b75fd.json")
    a = ap.parse_args()

    added = _widen_claim_types()
    if added:
        print(f"NOTE: widened schemas._CLAIM_TYPES in memory with {added} - "
              f"without this, load_draft raises and the pipeline's Phase 1 "
              f"audits silently do not run on the shipped draft. See "
              f"_widen_claim_types().\n")

    pdir = config.project_dir(a.project)
    fdir = pdir / "_fingerprints"
    base = json.loads((pdir / a.draft).read_text(encoding="utf-8-sig"))
    prop = json.loads((fdir / "proposed_binding.json").read_text(
        encoding="utf-8"))
    newmap = {b["id"]: b for b in prop["binding"]}

    cur = json.loads(json.dumps(base))
    new = json.loads(json.dumps(base))
    n_rebound = 0
    for ln in new["lines"]:
        b = newmap.get(ln.get("id"))
        if b and b["new_shot"] != b["old_shot"]:
            ln["clip_start"] = b["new_start"]
            ln["clip_end"] = b["new_end"]
            n_rebound += 1

    build("_p4_cur", pdir, cur)
    build("_p4_new", pdir, new)

    print(f"re-pointed {n_rebound} line(s)\n")
    rc = audit("_p4_cur")
    rn = audit("_p4_new")

    print(f"{'[VOICE-VISUAL] via pipeline.binding_audit':<42}"
          f"{'current':>10}{'proposed':>10}")
    for k in ("verified_match", "verified_mismatch", "mismatches",
              "issues_total", "footage_dropped"):
        print(f"  {k:<40}{rc[k]:>10}{rn[k]:>10}")
    kinds = sorted(set(rc["by_kind"]) | set(rn["by_kind"]))
    print(f"\n  {'by kind':<40}{'current':>10}{'proposed':>10}")
    for k in kinds:
        print(f"  {k:<40}{rc['by_kind'].get(k,0):>10}"
              f"{rn['by_kind'].get(k,0):>10}")

    (fdir / "voice_visual.json").write_text(json.dumps(
        {"rebound_lines": n_rebound, "current": rc, "proposed": rn},
        indent=1), encoding="utf-8")

    for s in ("_p4_cur", "_p4_new"):
        shutil.rmtree(config.project_dir(s), ignore_errors=True)
    print("\nscratch projects removed; the real draft.json was never written")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
