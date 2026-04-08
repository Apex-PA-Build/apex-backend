from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.task_helpers import (
    detect_overload,
    heuristic_quadrant,
    pick_focus_task,
    score_importance,
    score_urgency,
)


def make_task(
    priority="medium",
    due_hours: float | None = None,
    goal_id=None,
    status="pending",
    quadrant: int | None = None,
):
    task = MagicMock()
    task.priority = priority
    task.goal_id = goal_id
    task.status = status
    task.eisenhower_quadrant = quadrant
    if due_hours is not None:
        task.due_at = datetime.now(timezone.utc) + timedelta(hours=due_hours)
    else:
        task.due_at = None
    return task


class TestScoreUrgency:
    def test_no_due_date_returns_zero(self):
        task = make_task()
        assert score_urgency(task) == 0

    def test_overdue_returns_three(self):
        task = make_task(due_hours=-1)
        assert score_urgency(task) == 3

    def test_due_in_12h_returns_three(self):
        task = make_task(due_hours=12)
        assert score_urgency(task) == 3

    def test_due_in_48h_returns_two(self):
        task = make_task(due_hours=48)
        assert score_urgency(task) == 2

    def test_due_in_1_week_returns_one(self):
        task = make_task(due_hours=120)
        assert score_urgency(task) == 1

    def test_due_far_future_returns_zero(self):
        task = make_task(due_hours=500)
        assert score_urgency(task) == 0


class TestScoreImportance:
    def test_low_priority_returns_zero(self):
        task = make_task(priority="low")
        assert score_importance(task) == 0

    def test_critical_returns_three(self):
        task = make_task(priority="critical")
        assert score_importance(task) == 3

    def test_goal_linked_bumps_score(self):
        import uuid
        task = make_task(priority="medium", goal_id=uuid.uuid4())
        assert score_importance(task) == 2  # medium=1 + goal bonus=1

    def test_goal_linked_capped_at_three(self):
        import uuid
        task = make_task(priority="critical", goal_id=uuid.uuid4())
        assert score_importance(task) == 3  # capped


class TestHeuristicQuadrant:
    def test_urgent_important_is_q1(self):
        task = make_task(priority="critical", due_hours=10)
        assert heuristic_quadrant(task) == 1

    def test_not_urgent_important_is_q2(self):
        task = make_task(priority="high", due_hours=500)
        assert heuristic_quadrant(task) == 2

    def test_urgent_not_important_is_q3(self):
        task = make_task(priority="low", due_hours=10)
        assert heuristic_quadrant(task) == 3

    def test_not_urgent_not_important_is_q4(self):
        task = make_task(priority="low")
        assert heuristic_quadrant(task) == 4


class TestDetectOverload:
    def test_no_overload_below_threshold(self):
        result = detect_overload(5)
        assert result["overloaded"] is False

    def test_moderate_overload(self):
        result = detect_overload(11)
        assert result["overloaded"] is True
        assert result["severity"] == "moderate"

    def test_critical_overload(self):
        result = detect_overload(16)
        assert result["overloaded"] is True
        assert result["severity"] == "critical"


class TestPickFocusTask:
    def test_returns_none_for_empty_list(self):
        assert pick_focus_task([]) is None

    def test_prefers_q1_over_q2(self):
        q1 = make_task(priority="critical", due_hours=10, quadrant=1)
        q2 = make_task(priority="high", due_hours=500, quadrant=2)
        result = pick_focus_task([q2, q1])
        assert result == q1

    def test_ignores_done_tasks(self):
        done = make_task(priority="critical", due_hours=1, status="done", quadrant=1)
        pending = make_task(priority="low", status="pending", quadrant=4)
        result = pick_focus_task([done, pending])
        assert result == pending

    def test_returns_none_if_all_done(self):
        tasks = [make_task(status="done"), make_task(status="cancelled")]
        assert pick_focus_task(tasks) is None
