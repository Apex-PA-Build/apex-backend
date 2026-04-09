import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.llm_service import classify_single
from app.utils.prompt_builder import build_classification_prompt
from app.utils.task_helpers import detect_overload, heuristic_quadrant, pick_focus_task

logger = get_logger(__name__)


async def create_task(user_id: str, data: TaskCreate, db: AsyncSession) -> Task:
    task = Task(user_id=uuid.UUID(user_id), **data.model_dump())
    db.add(task)
    await db.flush()
    logger.info("task_created", user_id=user_id, task_id=str(task.id))
    return task


async def get_task(task_id: uuid.UUID, user_id: str, db: AsyncSession) -> Task:
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == uuid.UUID(user_id))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError(f"Task {task_id} not found")
    return task


async def list_tasks(
    user_id: str,
    db: AsyncSession,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Task], int]:
    q = select(Task).where(Task.user_id == uuid.UUID(user_id))
    if status:
        q = q.where(Task.status == status)
    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar_one()
    result = await db.execute(q.order_by(Task.created_at.desc()).limit(limit).offset(offset))
    return list(result.scalars().all()), total


async def update_task(task_id: uuid.UUID, user_id: str, data: TaskUpdate, db: AsyncSession) -> Task:
    task = await get_task(task_id, user_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    return task


async def delete_task(task_id: uuid.UUID, user_id: str, db: AsyncSession) -> None:
    task = await get_task(task_id, user_id, db)
    await db.delete(task)


async def bulk_defer(
    task_ids: list[uuid.UUID], user_id: str, defer_to: datetime, db: AsyncSession
) -> int:
    await db.execute(
        update(Task)
        .where(Task.id.in_(task_ids), Task.user_id == uuid.UUID(user_id))
        .values(status="deferred", due_at=defer_to)
    )
    logger.info("tasks_bulk_deferred", user_id=user_id, count=len(task_ids))
    return len(task_ids)


async def focus_now(user_id: str, db: AsyncSession, energy: str | None = None) -> dict:
    result = await db.execute(
        select(Task).where(
            Task.user_id == uuid.UUID(user_id),
            Task.status.in_(["pending", "in_progress"]),
        )
    )
    tasks = list(result.scalars().all())
    overload = detect_overload(len(tasks))
    best = pick_focus_task(tasks, energy=energy)
    alternatives = [t for t in tasks if t != best][:3]
    return {
        "task": best,
        "reason": f"Q{best.eisenhower_quadrant or heuristic_quadrant(best)} — highest priority right now." if best else "No pending tasks.",
        "alternatives": alternatives,
        "overload": overload,
    }


async def classify_tasks_eisenhower(
    task_ids: list[uuid.UUID], user_id: str, db: AsyncSession
) -> dict[str, int]:
    results: dict[str, int] = {}
    for tid in task_ids:
        task = await get_task(tid, user_id, db)
        try:
            prompt = build_classification_prompt(task.title, task.description)
            quadrant_str = await classify_single(prompt, ["1", "2", "3", "4"])
            quadrant = int(quadrant_str)
        except Exception:
            quadrant = heuristic_quadrant(task)
        task.eisenhower_quadrant = quadrant
        results[str(tid)] = quadrant
    return results

async def process_brain_dump(text: str, user_id: str, db: AsyncSession) -> list[Task]:
    from app.services.llm_service import extract_json
    system = "You are an ADHD task organization assistant. The user will dump a brain-stream of text. Identify all discrete tasks. Return ONLY a JSON array of objects. Each object must have: 'title' (string), 'priority' (string: low, medium, high, critical), 'energy_required' (string: low, medium, high). Return an empty array if no tasks found."
    extracted = await extract_json(prompt=f"Text:\n{text}", system=system)
    tasks = []
    if not isinstance(extracted, list):
        extracted = []
    for item in extracted:
        if "title" not in item:
            continue
        data = TaskCreate(
            title=item["title"][:500],
            priority=item.get("priority", "medium") if item.get("priority") in ["low", "medium", "high", "critical"] else "medium",
            energy_required=item.get("energy_required", "medium") if item.get("energy_required") in ["low", "medium", "high"] else "medium",
        )
        task = Task(user_id=uuid.UUID(user_id), **data.model_dump())
        db.add(task)
        tasks.append(task)
    await db.flush()
    return tasks

async def process_replan_day(context: str, user_id: str, db: AsyncSession) -> dict:
    from app.services.llm_service import extract_json
    
    # Get all pending tasks
    result = await db.execute(
        select(Task).where(Task.user_id == uuid.UUID(user_id), Task.status.in_(["pending", "in_progress"]))
    )
    tasks = list(result.scalars().all())
    if not tasks:
        return {"message": "You have no pending tasks to reschedule.", "tasks_rescheduled": 0, "tasks_deferred": 0}

    # Format for LLM
    task_dicts = [{"id": str(t.id), "title": t.title, "priority": t.priority, "energy_required": t.energy_required} for t in tasks]
    system = "You are a compassionate ADHD planning assistant. The user's day has failed or changed unexpectedly. You must help them replan without shame. Review their pending tasks. Return ONLY a JSON object with: 'message' (a short comforting and encouraging message), 'modifications' (an array of objects with 'id', 'action' [either 'defer_to_tomorrow' or 'keep_today']). You should heavily prefer deferring to tomorrow if the user is exhausted."
    
    response = await extract_json(prompt=f"User context: {context}\nTasks:\n{task_dicts}", system=system)
    if not isinstance(response, dict):
        response = {"message": "I've tried to organize things but encountered an error. Let's take it easy today.", "modifications": []}
    
    deferred_count = 0
    kept_count = 0
    tomorrow = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0) # roughly next day 8am
    
    modifications = response.get("modifications", [])
    for mod in modifications:
        tid = mod.get("id")
        action = mod.get("action")
        task = next((t for t in tasks if str(t.id) == tid), None)
        if task:
            if action == "defer_to_tomorrow":
                task.status = "deferred"
                task.due_at = tomorrow
                deferred_count += 1
            else:
                kept_count += 1

    await db.flush()
    return {
        "message": response.get("message", "I have rescheduled your day to give you some breathing room."),
        "tasks_rescheduled": kept_count,
        "tasks_deferred": deferred_count
    }
