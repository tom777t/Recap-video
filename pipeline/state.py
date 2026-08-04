"""Engine-owned per-project stage state (projects/<name>/state.json).

Written by the ENGINE, never hand-edited. Records whether a draft is in the
OUTLINE stage (3a: coverage + binding only) or SCRIPT stage (3b: enrichment,
DRAFT-TARGET applies). Promotion outline->script is ONE-WAY and EXPLICIT for now
(a human runs `recap.py draft --promote`); the engine computes outline_ready and
records its judgment + metrics here so the decision is auditable.
"""
import json
from datetime import datetime, timezone

import config

DEFAULT_STAGE = "outline"
VALID_STAGES = ("outline", "script")


def _path(project: str):
    return config.project_dir(project) / "state.json"


def load_state(project: str) -> dict:
    """Return the project's state dict; defaults to stage=outline if absent.
    Never raises: a missing/corrupt file yields the default."""
    p = _path(project)
    if not p.exists():
        return {"stage": DEFAULT_STAGE}
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        if not isinstance(d, dict) or d.get("stage") not in VALID_STAGES:
            return {"stage": DEFAULT_STAGE}
        return d
    except Exception:
        return {"stage": DEFAULT_STAGE}


def get_stage(project: str) -> str:
    return load_state(project).get("stage", DEFAULT_STAGE)


def save_state(project: str, state: dict) -> None:
    _path(project).write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def promote_to_script(project: str, reason: str, metrics: dict) -> dict:
    """Set stage=script (one-way). Returns the written state."""
    state = load_state(project)
    state["stage"] = "script"
    state["stage_reason"] = reason
    state["stage_updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state["outline_metrics"] = metrics
    save_state(project, state)
    return state
