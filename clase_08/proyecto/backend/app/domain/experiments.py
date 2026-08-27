"""Experiment lifecycle policy."""

TRANSITIONS = {
    "draft": {"running"},
    "running": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
}


def require_transition(current: str, target: str) -> None:
    if target != current and target not in TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid experiment transition: {current} -> {target}")
