"""Diagnose why [ACTION-SETUP] fires or stays silent, line by line.

Throwaway instrument, not pipeline code. It MIRRORS the two closures inside
draft._lint_script (_is_action / _has_setup) rather than importing them, so if
draft.py changes this file must be re-checked against it.

Run from the repo root:
    python diag_action_setup.py --project interstellar2014_linear

For every action line it prints:
    mid-run?      whether the previous line is also action (v2 skips these)
    setup?        whether the 4-line window cleared the gate
    matched       WHICH pattern cleared it, and on which line
so the two candidate causes of a silent gate can be told apart.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config                                    # noqa: E402
from pipeline import draft as D                  # noqa: E402


def load_pool_meta(pdir):
    bp = pdir / "broll.json"
    if not bp.exists():
        return {}
    try:
        bd = json.loads(bp.read_text(encoding="utf-8-sig"))
        return bd.get("pool", bd)
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--window", type=int, default=4)
    args = ap.parse_args()

    pdir = config.project_dir(args.project)
    draft_json = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    lines = draft_json["lines"]
    pool_meta = load_pool_meta(pdir)
    shot_index = D._load_shot_index(pdir)

    def families_of(ln):
        labs = ln.get("montage") or ([ln["pool"]] if ln.get("pool") else [])
        return {pool_meta.get(l, {}).get("family")
                for l in labs if l and isinstance(l, str)}

    def depicts_of(ln):
        dep = set()
        for lab in (ln.get("montage") or ([ln["pool"]] if ln.get("pool") else [])):
            if isinstance(lab, str):
                dep |= set((pool_meta.get(lab, {}) or {}).get("depicts") or [])
        cs = ln.get("clip_start")
        if cs and shot_index:
            try:
                t = D.parse_ts(cs)
                for a, b, sdep, _f in shot_index:
                    if a <= t < b:
                        dep |= sdep
                        break
            except Exception:
                pass
        return dep

    def is_action(ln):
        if "action" in depicts_of(ln):
            return True
        if any(D._is_action_family(f) for f in families_of(ln) if f):
            return True
        try:
            return float(ln.get("hold", 0) or 0) >= 5.0
        except (TypeError, ValueError):
            return False

    def which_cue(text):
        """Return the label of the FIRST pattern that matches, or None."""
        low = text.lower()
        for pat in D._SETUP_CUES:
            if re.search(pat, low):
                return pat
        purpose = getattr(D, "_SETUP_PURPOSE", None)
        if purpose:
            m = re.search(purpose, text)
            if m:
                return f"PURPOSE -> {m.group(0)!r}"
        return None

    flags = [is_action(x) for x in lines]
    print(f"project: {args.project}   lines: {len(lines)}   "
          f"action lines: {sum(flags)}   shots indexed: {len(shot_index)}")
    print("-" * 78)

    n_midrun = n_cleared = n_flag = 0
    for i, ln in enumerate(lines):
        if not flags[i]:
            continue
        lid = ln.get("id")
        skip = ln.get("setup_ok") or ln.get("delivery") in ("hook", "intro")
        midrun = i > 0 and flags[i - 1]

        hit = None
        for j in range(max(0, i - args.window), i + 1):
            cue = which_cue(lines[j].get("narration", ""))
            if cue:
                hit = (lines[j].get("id"), cue)
                break

        if skip:
            state = "SKIP (setup_ok/hook)"
        elif midrun:
            state = "MID-RUN (v2 skips)"
            n_midrun += 1
        elif hit:
            state = f"CLEARED by L{hit[0]}: {hit[1]}"
            n_cleared += 1
        else:
            state = ">>> WOULD FLAG <<<"
            n_flag += 1
        print(f"L{lid:<5} {state}")

    print("-" * 78)
    print(f"mid-run skipped : {n_midrun}")
    print(f"cleared by cue  : {n_cleared}")
    print(f"would flag      : {n_flag}")


if __name__ == "__main__":
    main()
