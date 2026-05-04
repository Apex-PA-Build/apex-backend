import json
from collections.abc import AsyncGenerator
from typing import Any

from app.core import cache
from app.core.logging import get_logger
from app.core.supabase import get_client
from app.services import agent as agent_svc
from app.services import calendar as cal_svc
from app.services import expense as expense_svc
from app.services import goal as goal_svc
from app.services import habit as habit_svc
from app.services import lists as lists_svc
from app.services import llm
from app.services import memory as mem_svc
from app.services import notes as notes_svc
from app.services import project as project_svc
from app.services import reminder as reminder_svc
from app.services import routine as routine_svc
from app.services import task as task_svc
from app.utils.prompts import APEX_TOOLS, TOOL_STATUS_MESSAGES, build_system_prompt

logger = get_logger(__name__)

_SESSION_TTL = 60 * 60 * 2  # 2 hours

# In-memory fallback — works even when Redis is not running
# Stores only clean {"role": "user"|"assistant", "content": str} turns
_memory_sessions: dict[str, list[dict[str, Any]]] = {}


def _load_history_sync(key: str) -> list[dict[str, Any]]:
    return list(_memory_sessions.get(key, []))


def _save_history_sync(key: str, history: list[dict[str, Any]]) -> None:
    # Keep last 20 turns (10 exchanges)
    _memory_sessions[key] = history[-20:]


async def _load_history(key: str) -> list[dict[str, Any]]:
    # Try Redis first, fall back to in-memory
    try:
        data = await cache.get(f"session:{key}")
        if isinstance(data, list):
            _memory_sessions[key] = data  # sync in-memory too
            return data
    except Exception:
        pass
    return _load_history_sync(key)


async def _save_history(key: str, history: list[dict[str, Any]]) -> None:
    _save_history_sync(key, history)
    try:
        await cache.set(f"session:{key}", _memory_sessions[key], ttl=_SESSION_TTL)
    except Exception:
        pass  # in-memory fallback is already saved above


async def _get_profile(user_id: str) -> dict[str, Any]:
    client = await get_client()
    result = await client.table("profiles").select("name, timezone, mood_today").eq("id", user_id).execute()
    return result.data[0] if result.data else {"name": "there", "timezone": "UTC", "mood_today": None}


async def _build_context(user_id: str, message: str) -> dict[str, Any]:
    """Retrieve relevant context for this message."""
    memories = await mem_svc.search(user_id, message, limit=8)
    tasks = await task_svc.list_tasks(user_id, status="pending", limit=8)
    schedule = await cal_svc.get_today_schedule(user_id)
    return {"memories": memories, "tasks": tasks, "events": schedule["events"]}


async def _extend_calendar_event(user_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Extend an existing event's end_at and replace its follow-up reminder."""
    from datetime import timedelta
    from app.utils.datetime import parse_iso
    event_title = tool_input["event_title"]
    extra_minutes = int(tool_input["extra_minutes"])
    client = await get_client()

    # Find the event
    result = await (
        client.table("calendar_events")
        .select("id, title, end_at")
        .eq("user_id", user_id)
        .ilike("title", f"%{event_title}%")
        .eq("is_cancelled", False)
        .order("start_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return {"status": "not_found", "message": f"No active event found matching '{event_title}'"}

    event = result.data[0]
    new_end = (parse_iso(event["end_at"]) + timedelta(minutes=extra_minutes)).isoformat()

    # Update end_at
    await (
        client.table("calendar_events")
        .update({"end_at": new_end})
        .eq("id", event["id"])
        .execute()
    )

    # Dismiss old fired/pending follow-up reminder
    await (
        client.table("reminders")
        .update({"status": "dismissed"})
        .eq("user_id", user_id)
        .in_("status", ["fired", "pending"])
        .contains("metadata", {"event_id": event["id"]})
        .execute()
    )

    # Create new follow-up reminder at the new end time
    await client.table("reminders").insert({
        "user_id": user_id,
        "title": f"Did you complete: {event['title']}?",
        "body": "Your extended session just ended. How did it go?",
        "type": "follow_up",
        "remind_at": new_end,
        "status": "pending",
        "metadata": {
            "type": "event_followup",
            "event_id": event["id"],
            "event_title": event["title"],
            "actions": [
                {"label": "✅ Done", "message": f"I completed '{event['title']}'"},
                {"label": "🔄 Extend 10 min", "message": f"Extend '{event['title']}' by 10 more minutes"},
                {"label": "⏸ Partially done", "message": f"I partially completed '{event['title']}', need to continue later"},
            ],
        },
    }).execute()

    return {"status": "extended", "event_id": event["id"], "new_end_at": new_end, "extra_minutes": extra_minutes}


async def _complete_calendar_event(user_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Mark a calendar event as cancelled and dismiss its follow-up reminder."""
    event_title = tool_input["event_title"]
    outcome = tool_input.get("outcome", "completed")
    client = await get_client()

    # Find the event by title
    result = await (
        client.table("calendar_events")
        .select("id, title")
        .eq("user_id", user_id)
        .ilike("title", f"%{event_title}%")
        .eq("is_cancelled", False)
        .order("start_at", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return {"status": "not_found", "message": f"No active event found matching '{event_title}'"}

    event = result.data[0]

    # Mark event as cancelled (completed events are cancelled in calendar)
    await (
        client.table("calendar_events")
        .update({"is_cancelled": True})
        .eq("id", event["id"])
        .execute()
    )

    # Dismiss any associated follow-up reminder
    await (
        client.table("reminders")
        .update({"status": "dismissed"})
        .eq("user_id", user_id)
        .eq("status", "fired")
        .contains("metadata", {"event_id": event["id"]})
        .execute()
    )

    return {"status": outcome, "event_id": event["id"], "event_title": event["title"]}


async def _reschedule_calendar_event(user_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    result = await (
        client.table("calendar_events")
        .select("id, title")
        .eq("user_id", user_id)
        .ilike("title", f"%{tool_input['event_title']}%")
        .eq("is_cancelled", False)
        .order("start_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return {"error": f"No event found matching '{tool_input['event_title']}'"}
    event = result.data[0]
    await client.table("calendar_events").update({"start_at": tool_input["new_start_at"], "end_at": tool_input["new_end_at"]}).eq("id", event["id"]).execute()
    return {"rescheduled": True, "event_title": event["title"], "new_start_at": tool_input["new_start_at"]}


async def _delete_calendar_event(user_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    result = await (
        client.table("calendar_events")
        .update({"is_cancelled": True})
        .eq("user_id", user_id)
        .ilike("title", f"%{tool_input['event_title']}%")
        .execute()
    )
    return {"deleted": bool(result.data), "event_title": tool_input["event_title"]}


async def _get_week_schedule(user_id: str) -> dict[str, Any]:
    from datetime import timedelta
    from app.utils.datetime import start_of_day, utcnow
    now = utcnow()
    start = start_of_day()
    end = (now + timedelta(days=7)).replace(hour=23, minute=59, second=59)
    client = await get_client()
    result = await (
        client.table("calendar_events")
        .select("title, start_at, end_at, location, attendees")
        .eq("user_id", user_id)
        .eq("is_cancelled", False)
        .gte("start_at", start.isoformat())
        .lte("start_at", end.isoformat())
        .order("start_at")
        .execute()
    )
    return {"events": result.data or [], "from": start.isoformat(), "to": end.isoformat()}


async def _find_free_slot(user_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    schedule = await _get_week_schedule(user_id)
    from app.utils.datetime import find_free_blocks
    blocks = find_free_blocks(schedule["events"])
    duration = tool_input.get("duration_minutes", 60)
    prefer = tool_input.get("prefer", "morning")
    prefer_hours = {"morning": (8, 12), "afternoon": (12, 17), "evening": (17, 21)}
    start_h, end_h = prefer_hours.get(prefer, (8, 20))
    for block in blocks:
        if block["duration_minutes"] >= duration:
            import datetime as dt
            block_start = dt.datetime.fromisoformat(block["start_at"])
            if start_h <= block_start.hour < end_h:
                return {"found": True, "start_at": block["start_at"], "duration_minutes": duration, "prefer": prefer}
    suitable = [b for b in blocks if b["duration_minutes"] >= duration]
    if suitable:
        return {"found": True, "start_at": suitable[0]["start_at"], "duration_minutes": duration}
    return {"found": False, "message": f"No free {duration}-minute slot found this week"}


async def _get_upcoming_events(user_id: str, days: int) -> dict[str, Any]:
    from datetime import timedelta
    from app.utils.datetime import utcnow
    now = utcnow()
    end = now + timedelta(days=days)
    client = await get_client()
    result = await (
        client.table("calendar_events")
        .select("title, start_at, end_at, location")
        .eq("user_id", user_id)
        .eq("is_cancelled", False)
        .gte("start_at", now.isoformat())
        .lte("start_at", end.isoformat())
        .order("start_at")
        .execute()
    )
    return {"events": result.data or [], "days": days}


async def _snooze_reminder_by_title(user_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    result = await (
        client.table("reminders")
        .select("id")
        .eq("user_id", user_id)
        .ilike("title", f"%{tool_input['reminder_title']}%")
        .in_("status", ["pending", "fired"])
        .limit(1)
        .execute()
    )
    if not result.data:
        return {"error": "Reminder not found"}
    return await reminder_svc.snooze(user_id, result.data[0]["id"], tool_input.get("minutes", 30))


async def _dismiss_reminder_by_title(user_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    result = await (
        client.table("reminders")
        .update({"status": "dismissed"})
        .eq("user_id", user_id)
        .ilike("title", f"%{tool_input['reminder_title']}%")
        .execute()
    )
    return {"dismissed": bool(result.data)}


async def _add_birthday(user_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    person = tool_input["person"]
    date = tool_input["date"]
    remind_days = tool_input.get("remind_days_before", 3)
    await mem_svc.store(user_id, f"{person}'s birthday is {date}", "relationship", source="user_explicit")
    return {"saved": True, "person": person, "date": date, "remind_days_before": remind_days}


async def _draft_message(tool_input: dict[str, Any]) -> dict[str, Any]:
    prompt = f"Draft a {tool_input.get('tone', 'professional')} message to {tool_input['to']} about: {tool_input['about']}. Write only the message body, no subject line."
    draft = await llm.complete(prompt, max_tokens=500)
    return {"draft": draft, "to": tool_input["to"]}


async def _draft_email(tool_input: dict[str, Any]) -> dict[str, Any]:
    prompt = f"Draft a {tool_input.get('tone', 'professional')} email to {tool_input['to']} about: {tool_input['about']}. Include subject line. Format as:\nSubject: ...\n\nBody: ..."
    draft = await llm.complete(prompt, max_tokens=600)
    return {"draft": draft, "to": tool_input["to"], "subject": tool_input.get("subject", "")}


async def _compare_options(tool_input: dict[str, Any]) -> dict[str, Any]:
    options = ", ".join(tool_input["options"])
    context = tool_input.get("context", "")
    prompt = f"Compare these options: {options}. Context: {context}. Give a concise recommendation with key reasons. Be direct."
    result = await llm.complete(prompt, max_tokens=400)
    return {"comparison": result, "options": tool_input["options"]}


async def _pros_cons(tool_input: dict[str, Any]) -> dict[str, Any]:
    prompt = f"List pros and cons for: {tool_input['decision']}. Be specific and practical. Format as Pros: ... Cons: ..."
    result = await llm.complete(prompt, max_tokens=400)
    return {"analysis": result, "decision": tool_input["decision"]}


async def _workload_check(user_id: str) -> dict[str, Any]:
    schedule = await _get_week_schedule(user_id)
    tasks = await task_svc.list_tasks(user_id, status="pending", limit=50)
    overdue = [t for t in tasks if t.get("due_at") and t["due_at"] < __import__("datetime").datetime.utcnow().isoformat()]
    high_priority = [t for t in tasks if t.get("priority") in ("high", "critical")]
    total_meeting_min = sum(
        int((__import__("datetime").datetime.fromisoformat(e["end_at"]) - __import__("datetime").datetime.fromisoformat(e["start_at"])).total_seconds() / 60)
        for e in schedule["events"] if e.get("end_at") and e.get("start_at")
    )
    overcommitted = total_meeting_min > 300 or len(high_priority) > 5
    return {
        "total_meeting_minutes_this_week": total_meeting_min,
        "pending_tasks": len(tasks),
        "overdue_tasks": len(overdue),
        "high_priority_tasks": len(high_priority),
        "overcommitted": overcommitted,
        "assessment": "You're overcommitted this week." if overcommitted else "Workload looks manageable.",
    }


async def _deadline_countdown(user_id: str, item: str) -> dict[str, Any]:
    import datetime as dt
    tasks = await task_svc.list_tasks(user_id, status="pending", limit=50)
    goals = await goal_svc.list_goals(user_id)
    now = dt.datetime.utcnow().date()
    for t in tasks:
        if item.lower() in t["title"].lower() and t.get("due_at"):
            due = dt.datetime.fromisoformat(t["due_at"]).date()
            return {"item": t["title"], "due": str(due), "days_remaining": (due - now).days, "type": "task"}
    for g in goals:
        if item.lower() in g["title"].lower() and g.get("target_date"):
            due = dt.date.fromisoformat(g["target_date"])
            return {"item": g["title"], "due": str(due), "days_remaining": (due - now).days, "type": "goal"}
    return {"error": f"No deadline found for '{item}'"}


async def _daily_summary(user_id: str) -> dict[str, Any]:
    import datetime as dt
    today_start = dt.datetime.utcnow().replace(hour=0, minute=0, second=0).isoformat()
    client = await get_client()
    done_tasks = await (
        client.table("tasks")
        .select("title")
        .eq("user_id", user_id)
        .eq("status", "done")
        .gte("updated_at", today_start)
        .execute()
    )
    schedule = await cal_svc.get_today_schedule(user_id)
    memories = await mem_svc.search(user_id, "today completed done finished", limit=5)
    return {
        "tasks_completed_today": [t["title"] for t in (done_tasks.data or [])],
        "meetings_today": len(schedule["events"]),
        "total_meeting_minutes": schedule["total_meeting_minutes"],
        "recent_context": [m["content"] for m in memories],
    }


async def _calculate(expression: str) -> dict[str, Any]:
    try:
        allowed = set("0123456789+-*/().% ")
        clean = "".join(c for c in expression if c in allowed)
        if clean:
            result = eval(clean)  # noqa: S307 — safe: only math chars allowed
            return {"expression": expression, "result": result}
        return {"expression": expression, "result": "Could not evaluate"}
    except Exception:
        return {"expression": expression, "result": "Could not evaluate — please rephrase"}


async def _tz_convert(tool_input: dict[str, Any]) -> dict[str, Any]:
    try:
        from datetime import datetime
        import zoneinfo
        t = tool_input["time"]
        from_tz = zoneinfo.ZoneInfo(tool_input["from_tz"])
        to_tz = zoneinfo.ZoneInfo(tool_input["to_tz"])
        dt = datetime.strptime(t, "%H:%M").replace(tzinfo=from_tz)
        converted = dt.astimezone(to_tz)
        return {"original": t, "from": tool_input["from_tz"], "converted": converted.strftime("%H:%M"), "to": tool_input["to_tz"]}
    except Exception as e:
        return {"error": str(e)}


async def _get_weather(city: str) -> dict[str, Any]:
    try:
        async with __import__("httpx").AsyncClient() as http:
            geo = await http.get(f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1", timeout=10)
            if not geo.json().get("results"):
                return {"error": f"City '{city}' not found"}
            loc = geo.json()["results"][0]
            weather = await http.get(
                "https://api.open-meteo.com/v1/forecast",
                params={"latitude": loc["latitude"], "longitude": loc["longitude"], "current_weather": True},
                timeout=10,
            )
            cw = weather.json().get("current_weather", {})
            return {"city": city, "temperature_c": cw.get("temperature"), "wind_kph": cw.get("windspeed"), "condition_code": cw.get("weathercode")}
    except Exception as e:
        return {"error": str(e)}


async def _execute_tool(user_id: str, tool_name: str, tool_input: dict[str, Any]) -> Any:
    """Dispatch a tool call to the appropriate service."""
    match tool_name:
        case "create_task":
            return await task_svc.create(user_id, tool_input)
        case "get_tasks":
            return await task_svc.list_tasks(user_id, **{k: v for k, v in tool_input.items() if k in ("status", "limit")})
        case "update_task":
            task_id = tool_input.pop("task_id")
            return await task_svc.update(user_id, task_id, tool_input)
        case "search_memories":
            return await mem_svc.search(user_id, tool_input["query"], tool_input.get("limit", 8))
        case "store_memory":
            return await mem_svc.store(user_id, tool_input["content"], tool_input["category"])
        case "get_today_schedule":
            return await cal_svc.get_today_schedule(user_id)
        case "create_calendar_event":
            return await cal_svc.create_event(user_id, tool_input)
        case "get_goals":
            return await goal_svc.list_goals(user_id)
        case "create_goal":
            return await goal_svc.create(user_id, tool_input)
        case "update_goal":
            goal_id = tool_input.pop("goal_id")
            return await goal_svc.update(user_id, goal_id, tool_input)
        case "create_reminder":
            return await reminder_svc.create(user_id, tool_input)
        case "extend_calendar_event":
            return await _extend_calendar_event(user_id, tool_input)
        case "complete_calendar_event":
            return await _complete_calendar_event(user_id, tool_input)
        case "delete_task":
            return await task_svc.delete(user_id, tool_input["task_id"])
        case "get_overdue_tasks":
            return await task_svc.list_tasks(user_id, status="pending", limit=20)
        # Calendar
        case "reschedule_calendar_event":
            return await _reschedule_calendar_event(user_id, tool_input)
        case "delete_calendar_event":
            return await _delete_calendar_event(user_id, tool_input)
        case "get_week_schedule":
            return await _get_week_schedule(user_id)
        case "find_free_slot":
            return await _find_free_slot(user_id, tool_input)
        case "get_upcoming_events":
            return await _get_upcoming_events(user_id, tool_input.get("days", 7))
        # Reminders
        case "get_reminders":
            return await reminder_svc.list_reminders(user_id, status=tool_input.get("status"))
        case "snooze_reminder":
            return await _snooze_reminder_by_title(user_id, tool_input)
        case "dismiss_reminder":
            return await _dismiss_reminder_by_title(user_id, tool_input)
        # Finance
        case "log_expense":
            return await expense_svc.log(user_id, tool_input)
        case "get_spending_summary":
            return await expense_svc.summary(user_id, days=tool_input.get("days", 30))
        case "track_subscription":
            return await expense_svc.add_subscription(user_id, tool_input)
        case "get_subscriptions":
            return await expense_svc.list_subscriptions(user_id)
        case "track_owed_money":
            return await expense_svc.track_owed(user_id, tool_input["person"], tool_input["amount"], tool_input["direction"], tool_input["reason"])
        case "get_owed_money":
            return await expense_svc.get_owed(user_id)
        # Habits
        case "create_habit":
            return await habit_svc.create(user_id, tool_input)
        case "log_habit":
            return await habit_svc.log(user_id, tool_input["habit_title"], tool_input.get("note"))
        case "get_habits":
            return await habit_svc.list_habits(user_id)
        case "get_habit_streaks":
            return await habit_svc.get_streaks(user_id)
        # Projects
        case "create_project":
            return await project_svc.create(user_id, tool_input)
        case "get_projects":
            return await project_svc.list_projects(user_id, status=tool_input.get("status"))
        case "get_project_status":
            return await project_svc.get_status(user_id, tool_input["project_title"])
        case "update_project":
            return await project_svc.update(user_id, tool_input["project_title"], {k: v for k, v in tool_input.items() if k != "project_title"})
        # Notes
        case "create_note":
            return await notes_svc.create(user_id, tool_input)
        case "search_notes":
            return await notes_svc.search(user_id, tool_input["query"])
        case "get_notes":
            return await notes_svc.list_notes(user_id)
        case "append_to_note":
            return await notes_svc.append(user_id, tool_input["note_title"], tool_input["content"])
        # Lists
        case "add_to_list":
            return await lists_svc.add_item(user_id, tool_input["list_name"], tool_input["item"], tool_input.get("list_type", "general"))
        case "get_list":
            return await lists_svc.get_list(user_id, tool_input["list_name"])
        case "clear_list":
            return await lists_svc.clear_list(user_id, tool_input["list_name"])
        # Routines
        case "create_routine":
            return await routine_svc.create(user_id, tool_input)
        case "get_routines":
            return await routine_svc.list_routines(user_id)
        case "run_routine":
            return await routine_svc.run(user_id, tool_input["routine_title"])
        # People
        case "add_person_note":
            return await mem_svc.store(user_id, f"{tool_input['person']}: {tool_input['note']}", "relationship", source="user_explicit")
        case "get_person_info":
            return await mem_svc.search(user_id, tool_input["person"], limit=10)
        case "add_birthday":
            return await _add_birthday(user_id, tool_input)
        case "get_upcoming_birthdays":
            return await mem_svc.search(user_id, "birthday", limit=20)
        case "log_interaction":
            return await mem_svc.store(user_id, f"Interacted with {tool_input['person']} today. {tool_input.get('note', '')}", "relationship")
        case "relationship_health":
            return await mem_svc.search(user_id, "last spoke interacted with", limit=20)
        # Health
        case "log_workout":
            return await mem_svc.store(user_id, f"Workout: {tool_input['activity']} for {tool_input.get('duration_minutes', '?')} minutes. {tool_input.get('note', '')}", "pattern")
        case "log_meal":
            return await mem_svc.store(user_id, f"{tool_input.get('when', 'meal').capitalize()}: {tool_input['meal']}", "pattern")
        case "log_sleep":
            return await mem_svc.store(user_id, f"Slept {tool_input['hours']} hours. Quality: {tool_input.get('quality', 'okay')}", "pattern")
        case "log_water":
            return await mem_svc.store(user_id, f"Drank {tool_input['glasses']} glasses of water today", "pattern")
        case "get_health_summary":
            return await mem_svc.search(user_id, "workout sleep meal water health", limit=20)
        # Journaling
        case "add_journal_entry":
            return await mem_svc.store(user_id, tool_input["content"], "fact", source="user_explicit")
        case "log_win":
            return await mem_svc.store(user_id, f"Win: {tool_input['win']}", "fact", source="user_explicit")
        case "get_wins":
            return await mem_svc.search(user_id, "win accomplished completed shipped", limit=15)
        # Learning
        case "add_book":
            return await mem_svc.store(user_id, f"Book: {tool_input['title']} by {tool_input.get('author', 'unknown')} — status: {tool_input.get('status', 'want_to_read')}", "fact")
        case "log_learning":
            return await mem_svc.store(user_id, f"Learned: {tool_input['content']} (topic: {tool_input.get('topic', 'general')})", "fact")
        case "get_reading_list":
            return await mem_svc.search(user_id, "book reading learning course", limit=15)
        # Drafting
        case "draft_message":
            return await _draft_message(tool_input)
        case "draft_email":
            return await _draft_email(tool_input)
        case "follow_up_tracker":
            return await mem_svc.store(user_id, f"Waiting for: {tool_input['waiting_for']} from {tool_input['from_person']}. Deadline: {tool_input.get('deadline', 'none')}", "commitment")
        case "delegation_tracker":
            return await mem_svc.store(user_id, f"Delegated to {tool_input['delegated_to']}: {tool_input['task']}. Due: {tool_input.get('due_date', 'none')}", "commitment")
        # Decision support
        case "compare_options":
            return await _compare_options(tool_input)
        case "pros_cons":
            return await _pros_cons(tool_input)
        # Proactive
        case "workload_check":
            return await _workload_check(user_id)
        case "deadline_countdown":
            return await _deadline_countdown(user_id, tool_input["item"])
        case "get_daily_summary":
            return await _daily_summary(user_id)
        case "get_focus_recommendation":
            return await task_svc.focus_now(user_id, energy=tool_input.get("energy_level"))
        # Utilities
        case "calculate":
            return await _calculate(tool_input["expression"])
        case "time_zone_convert":
            return await _tz_convert(tool_input)
        case "get_weather":
            return await _get_weather(tool_input["city"])
        # Agent
        case "send_agent_message":
            return await agent_svc.send_message(
                from_user_id=user_id,
                to_user_id=tool_input["to_user_id"],
                message_type=tool_input["message_type"],
                content=tool_input["content"],
            )
        case _:
            return {"error": f"Unknown tool: {tool_name}"}


async def process(user_id: str, message: str, session_id: str | None = None) -> dict[str, Any]:
    """Non-streaming chat — runs the full agentic loop and returns final reply."""
    profile = await _get_profile(user_id)
    context = await _build_context(user_id, message)

    system = build_system_prompt(
        user_name=profile["name"],
        user_timezone=profile.get("timezone", "UTC"),
        mood=profile.get("mood_today"),
        memories=context["memories"],
        events=context["events"],
        tasks=context["tasks"],
    )

    # Load prior conversation history (clean text turns only)
    sess_key = f"{user_id}:{session_id}" if session_id else None
    history = await _load_history(sess_key) if sess_key else []

    # Working message list includes history + current user message
    # History contains only clean text turns safe to replay
    messages: list[dict[str, Any]] = [*history, {"role": "user", "content": message}]
    tools_used: list[str] = []

    # Agentic loop — up to 5 tool-use rounds
    for _ in range(5):
        text, new_tools, tool_calls = await llm.chat_with_tools(messages, system, APEX_TOOLS)
        tools_used.extend(new_tools)

        if not tool_calls:
            await mem_svc.extract_and_store(user_id, f"User: {message}\nAPEX: {text}")
            if sess_key:
                # Save only clean text turns — no tool_use/tool_result blocks
                clean_history = [
                    m for m in history  # prior turns
                ]
                clean_history.append({"role": "user", "content": message})
                clean_history.append({"role": "assistant", "content": text})
                await _save_history(sess_key, clean_history)
            return {"reply": text, "tools_used": tools_used}

        # Build assistant message with tool use blocks (for this turn only)
        assistant_content: list[dict[str, Any]] = []
        if text:
            assistant_content.append({"type": "text", "text": text})
        for call in tool_calls:
            assistant_content.append({
                "type": "tool_use", "id": call["id"], "name": call["name"], "input": call["input"],
            })
        messages.append({"role": "assistant", "content": assistant_content})

        # Execute tools and collect results
        tool_results: list[dict[str, Any]] = []
        for call in tool_calls:
            result = await _execute_tool(user_id, call["name"], dict(call["input"]))
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": call["id"],
                "content": json.dumps(result, default=str),
            })
        messages.append({"role": "user", "content": tool_results})

    return {"reply": "I ran into a problem completing that. Want to try again?", "tools_used": tools_used}


async def stream(user_id: str, message: str, session_id: str | None = None) -> AsyncGenerator[dict[str, Any], None]:
    """Streaming chat — yields SSE events. Maintains session history same as process()."""
    profile = await _get_profile(user_id)
    context = await _build_context(user_id, message)

    system = build_system_prompt(
        user_name=profile["name"],
        user_timezone=profile.get("timezone", "UTC"),
        mood=profile.get("mood_today"),
        memories=context["memories"],
        events=context["events"],
        tasks=context["tasks"],
    )

    sess_key = f"{user_id}:{session_id}" if session_id else None
    history = await _load_history(sess_key) if sess_key else []

    messages: list[dict[str, Any]] = [*history, {"role": "user", "content": message}]
    full_reply = ""

    for _ in range(5):
        async for event in llm.stream_with_tools(messages, system, APEX_TOOLS):
            if event["type"] == "chunk":
                full_reply += event["content"]
                yield event
            elif event["type"] == "tool_start":
                status_msg = TOOL_STATUS_MESSAGES.get(event["name"], "Working on it...")
                yield {"type": "tool_status", "name": event["name"], "message": status_msg}
            elif event["type"] == "tool_done":
                yield event
            elif event["type"] == "done":
                await mem_svc.extract_and_store(user_id, f"User: {message}\nAPEX: {full_reply}")
                if sess_key:
                    clean_history = [*history]
                    clean_history.append({"role": "user", "content": message})
                    clean_history.append({"role": "assistant", "content": full_reply})
                    await _save_history(sess_key, clean_history)
                yield {"type": "done"}
                return
            elif event["type"] == "tool_calls":
                calls = event["calls"]
                raw_content = event["raw_content"]

                assistant_content: list[dict[str, Any]] = []
                if full_reply:
                    assistant_content.append({"type": "text", "text": full_reply})
                for block in raw_content:
                    if block.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use", "id": block.id, "name": block.name, "input": block.input,
                        })
                messages.append({"role": "assistant", "content": assistant_content})
                full_reply = ""

                tool_results: list[dict[str, Any]] = []
                for call in calls:
                    result = await _execute_tool(user_id, call["name"], dict(call["input"]))
                    yield {"type": "tool_result", "name": call["name"], "result": result}
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": call["id"],
                        "content": json.dumps(result, default=str),
                    })
                messages.append({"role": "user", "content": tool_results})
                break

    yield {"type": "done"}
