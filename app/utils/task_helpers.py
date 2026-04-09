from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.task import Task

OVERLOAD_THRESHOLD = 10       # tasks in a single day
CRITICAL_OVERLOAD_THRESHOLD = 15
FOCUS_QUADRANT_PRIORITY = [1, 2, 3, 4]  # preferred order for focus-now


def score_urgency(task: "Task") -> int:
    """0–3 urgency score based on due date proximity."""
    if task.due_at is None:
        return 0
    now = datetime.now(timezone.utc)
    hours_left = (task.due_at - now).total_seconds() / 3600
    if hours_left < 0:
        return 3  # overdue
    if hours_left < 24:
        return 3
    if hours_left < 72:
        return 2
    if hours_left < 168:
        return 1
    return 0


def score_importance(task: "Task") -> int:
    """0–3 importance score based on priority field and goal linkage."""
    base = {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(task.priority, 1)
    if task.goal_id is not None:
        base = min(base + 1, 3)
    return base


def heuristic_quadrant(task: "Task") -> int:
    """Fallback Eisenhower quadrant without LLM, based on urgency/importance scores."""
    u = score_urgency(task)
    i = score_importance(task)
    urgent = u >= 2
    important = i >= 2
    if urgent and important:
        return 1
    if not urgent and important:
        return 2
    if urgent and not important:
        return 3
    return 4


def detect_overload(task_count: int) -> dict[str, bool | str]:
    if task_count >= CRITICAL_OVERLOAD_THRESHOLD:
        return {
            "overloaded": True,
            "severity": "critical",
            "message": f"You have {task_count} tasks today. Let's be honest — what are the 3 that actually matter?",
        }
    if task_count >= OVERLOAD_THRESHOLD:
        return {
            "overloaded": True,
            "severity": "moderate",
            "message": f"{task_count} tasks is a lot. Want me to identify what can be deferred?",
        }
    return {"overloaded": False, "severity": "none", "message": ""}


def pick_focus_task(tasks: list["Task"], energy: str | None = None) -> "Task | None":
    """
    Pick the single most important task to focus on right now.
    Prefers Q1 → Q2 with nearest due date.
    """
    if not tasks:
        return None

    def sort_key(t: "Task") -> tuple[int, int, float]:
        quadrant = t.eisenhower_quadrant or heuristic_quadrant(t)
        urgency = score_urgency(t)
        # Earlier due date = smaller float = higher priority
        due_score = (
            (t.due_at - datetime.now(timezone.utc)).total_seconds()
            if t.due_at
            else float("inf")
        )
        return (FOCUS_QUADRANT_PRIORITY.index(quadrant), -urgency, due_score)

    pending = [t for t in tasks if t.status in ("pending", "in_progress")]

    if energy == "low":
        # If low energy, filter out high energy tasks unless they are overdue (urgency=3)
        filtered = [t for t in pending if t.energy_required != "high" or score_urgency(t) >= 3]
        if filtered:
            pending = filtered

    if not pending:
        return None
    return sorted(pending, key=sort_key)[0]
