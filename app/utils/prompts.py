from datetime import datetime
from typing import Any


# ── Tool definitions for Claude tool use ─────────────────────────────────────

APEX_TOOLS: list[dict[str, Any]] = [
    {
        "name": "create_task",
        "description": "Create a new task in the user's task list.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "due_at": {"type": "string", "description": "ISO 8601 datetime or null"},
                "goal_id": {"type": "string", "description": "UUID of a goal to link this task to"},
                "energy_required": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["title"],
        },
    },
    {
        "name": "get_tasks",
        "description": "Get the user's tasks, optionally filtered by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["pending", "in_progress", "done", "deferred"]},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "update_task",
        "description": "Update an existing task's status, priority, or other fields.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "status": {"type": "string", "enum": ["pending", "in_progress", "done", "deferred", "cancelled"]},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "title": {"type": "string"},
                "due_at": {"type": "string"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "search_memories",
        "description": "Search the user's personal memory for relevant context, preferences, or facts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 8},
            },
            "required": ["query"],
        },
    },
    {
        "name": "store_memory",
        "description": "Save an important fact, preference, decision, or pattern about the user to long-term memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "category": {
                    "type": "string",
                    "enum": ["preference", "relationship", "pattern", "fact", "decision", "commitment"],
                },
            },
            "required": ["content", "category"],
        },
    },
    {
        "name": "get_today_schedule",
        "description": "Get today's calendar events, free blocks, and any detected conflicts.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_calendar_event",
        "description": "Create a new calendar event.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_at": {"type": "string", "description": "ISO 8601 datetime"},
                "end_at": {"type": "string", "description": "ISO 8601 datetime"},
                "location": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
                "description": {"type": "string"},
            },
            "required": ["title", "start_at", "end_at"],
        },
    },
    {
        "name": "get_goals",
        "description": "Get the user's active goals and their current progress.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_goal",
        "description": "Create a new long-term goal for the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "category": {
                    "type": "string",
                    "enum": ["work", "health", "finance", "personal", "learning"],
                },
                "target_date": {"type": "string", "description": "ISO date (YYYY-MM-DD)"},
                "description": {"type": "string"},
            },
            "required": ["title", "category"],
        },
    },
    {
        "name": "update_goal",
        "description": "Update a goal's progress percentage, status, or other fields.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "string"},
                "progress_pct": {"type": "integer", "description": "Progress 0-100"},
                "status": {"type": "string", "enum": ["active", "paused", "completed", "abandoned"]},
                "title": {"type": "string"},
            },
            "required": ["goal_id"],
        },
    },
    {
        "name": "create_reminder",
        "description": "Create a smart reminder for the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"},
                "remind_at": {"type": "string", "description": "ISO 8601 datetime"},
                "type": {"type": "string", "enum": ["time", "deadline", "relationship"]},
            },
            "required": ["title", "remind_at"],
        },
    },
    {
        "name": "send_agent_message",
        "description": "Send a message from this user's APEX to another user's APEX (PA-to-PA coordination).",
        "input_schema": {
            "type": "object",
            "properties": {
                "to_user_id": {"type": "string"},
                "message_type": {
                    "type": "string",
                    "enum": ["scheduling_request", "financial_settle", "follow_up_nudge", "info_request"],
                },
                "content": {"type": "object"},
            },
            "required": ["to_user_id", "message_type", "content"],
        },
    },
]

TOOL_STATUS_MESSAGES: dict[str, str] = {
    "create_task": "Adding that to your tasks...",
    "get_tasks": "Checking your task list...",
    "update_task": "Updating that task...",
    "search_memories": "Searching through what I know about you...",
    "store_memory": "Saving that to memory...",
    "get_today_schedule": "Pulling up your calendar...",
    "create_calendar_event": "Creating that calendar event...",
    "get_goals": "Checking your goals...",
    "create_goal": "Setting up that goal...",
    "update_goal": "Updating your goal...",
    "create_reminder": "Setting that reminder...",
    "send_agent_message": "Reaching out to their assistant...",
}


# ── System Prompts ────────────────────────────────────────────────────────────

def build_system_prompt(
    user_name: str,
    user_timezone: str,
    mood: str | None,
    memories: list[dict],
    events: list[dict],
    tasks: list[dict],
) -> str:
    now = datetime.now()

    memory_block = ""
    if memories:
        lines = "\n".join(f"  • [{m['category']}] {m['content']}" for m in memories)
        memory_block = f"\n\nWHAT I KNOW ABOUT {user_name.upper()}:\n{lines}"

    schedule_block = ""
    if events:
        lines = "\n".join(
            f"  • {e['title']} at {e['start_at'][:16]}"
            + (f" with {', '.join(e['attendees'])}" if e.get("attendees") else "")
            for e in events
        )
        schedule_block = f"\n\nTODAY'S SCHEDULE:\n{lines}"

    task_block = ""
    if tasks:
        lines = "\n".join(
            f"  • [{t['priority']}] {t['title']}"
            + (f" — due {t['due_at'][:10]}" if t.get("due_at") else "")
            for t in tasks[:8]
        )
        task_block = f"\n\nPENDING TASKS:\n{lines}"

    mood_line = f"\n\nMOOD TODAY: {mood}" if mood else ""

    return f"""You are APEX, {user_name}'s personal AI assistant — a brilliant, deeply loyal chief of staff who knows {user_name}'s life intimately.

TODAY: {now.strftime('%A, %B %d, %Y')} | {now.strftime('%I:%M %p')} ({user_timezone}){mood_line}{memory_block}{schedule_block}{task_block}

PERSONALITY:
- Warm but never sycophantic. Direct but never cold. You have opinions and share them.
- Never say "Great question!", "Certainly!", "Of course!", "Absolutely!", or "Sure!".
- Speak like a brilliant, trusted friend who happens to be world-class at getting things done.
- When the user is overwhelmed, distill things to the 3 that actually matter.

WHEN TO ASK QUESTIONS (do this first, before using any tool):
- The request is vague or has multiple valid interpretations → ask ONE focused question to clarify.
- You are missing a critical piece of information to complete the task (e.g. due date, priority, who it's for).
- The user seems to be thinking something through rather than requesting an action — engage them conversationally.
- A decision has significant consequences (financial, scheduling conflict, deleting data) — confirm intent first.
- Example: "Add a task for the meeting" → ask "Which meeting, and when do you need this done by?"

WHEN TO ACT WITHOUT ASKING:
- The request is specific and complete: all needed info is present.
- The action is clearly reversible and low-stakes (adding a task, setting a reminder).
- The user has already answered your clarifying question in this conversation.
- When you do act, confirm briefly: "Done — added to your tasks."

CONVERSATION STYLE:
- Ask ONE question at a time. Never stack multiple questions in one message.
- Always say WHY you're asking — it shows you're thinking, not just collecting data.
- If you asked a question and the user answered, use that answer immediately — don't ask again.
- Engage naturally. Not every message needs a tool call. Sometimes just talking is the right move.

RULES:
- Financial actions always require explicit confirmation before proceeding.
- PA-to-PA messages (send_agent_message) — tell the user exactly what you're sending before you send it.
- Memory is your superpower — use search_memories before answering anything personal about the user.
- Proactively surface risks, conflicts, and opportunities from the context above."""


def build_brief_prompt(
    user_name: str,
    events: list[dict],
    tasks: list[dict],
    memories: list[dict],
    agent_messages: list[dict],
) -> str:
    return f"""Generate a morning brief for {user_name}. Write it like a brilliant, warm chief-of-staff speaking directly — not a report.

SCHEDULE: {events}
PENDING TASKS: {tasks}
RECENT CONTEXT & MEMORIES: {memories}
PENDING FROM CONTACTS: {agent_messages}

Return ONLY valid JSON with these exact fields:
{{
  "greeting": "2-3 sentence personalized greeting that references something specific from today",
  "narrative": "3-5 sentence narrative of the day ahead — what matters, what to watch, what to protect",
  "focus_recommendation": "One specific, actionable first-thing recommendation with clear reasoning",
  "risks": ["list of specific risks or schedule conflicts detected"],
  "quick_wins": ["2-3 things completable in under 10 minutes"],
  "mood_prompt": "One warm, specific question about how they're feeling — tied to what's at stake today"
}}"""


def build_memory_extraction_prompt(text: str) -> str:
    return f"""Extract important personal facts from this text worth remembering long-term.

TEXT: {text}

Return ONLY valid JSON array. Only extract genuinely lasting, important facts (not trivial details):
[
  {{
    "content": "The fact to remember, written as a clear statement",
    "category": "preference|relationship|pattern|fact|decision|commitment"
  }}
]

Categories:
- preference: What they like/dislike (food, work style, communication, timing, tools)
- relationship: Facts about people they interact with (behavioral patterns, relationships)
- pattern: Recurring behaviors or tendencies you've observed
- fact: Important factual info (amounts owed, deadlines, key data points)
- decision: Decisions they've made
- commitment: Things they've promised to do for others

Return [] if nothing important. Maximum 5 memories per extraction."""


def build_call_extraction_prompt(transcript: str) -> str:
    return f"""Analyze this call transcript and extract structured information.

TRANSCRIPT:
{transcript}

Return ONLY valid JSON:
{{
  "summary": "2-3 sentence summary of what the call was about and the key outcome",
  "decisions": ["clear decisions made during the call"],
  "action_items": [
    {{
      "title": "specific action to be taken",
      "owner": "me (the user) | them | person name",
      "due_date": "date if mentioned, else null"
    }}
  ],
  "follow_ups": ["things to follow up on"],
  "people_mentioned": ["full names or identifiers of people mentioned"],
  "key_dates": ["important dates, deadlines, or timeframes mentioned"]
}}"""


def build_eisenhower_prompt(title: str, description: str | None, due_at: str | None) -> str:
    return f"""Classify this task into an Eisenhower quadrant. Return ONLY the number 1, 2, 3, or 4.

Task: {title}
Description: {description or 'None'}
Due: {due_at or 'No deadline'}

1 = Urgent + Important (crisis, deadline-driven, direct impact on goals)
2 = Not urgent + Important (planning, relationships, long-term work)
3 = Urgent + Not important (interruptions, others' priorities)
4 = Not urgent + Not important (busywork, low-value activities)"""


def build_weekly_review_prompt(user_name: str, goals: list[dict], completed_tasks: list[dict]) -> str:
    return f"""Write a weekly goal review for {user_name}. Be honest, warm, and constructive.

GOALS AND PROGRESS: {goals}
COMPLETED THIS WEEK: {completed_tasks}

Return ONLY valid JSON:
{{
  "narrative": "3-4 sentence honest reflection on the week — wins, what fell short, and why",
  "on_track": ["goal titles that are on track"],
  "behind": ["goal titles that are falling behind"],
  "recommendations": ["2-3 specific, actionable recommendations for next week"],
  "wins": ["notable accomplishments this week worth celebrating"]
}}"""
