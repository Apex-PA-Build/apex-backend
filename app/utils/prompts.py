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
        "name": "extend_calendar_event",
        "description": "Extend an existing calendar event by adding more minutes to its end time. Use when user says 'extend', 'need more time', 'not done yet, give me X more minutes'. Never create a new event for this.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_title": {"type": "string", "description": "Title of the event to extend"},
                "extra_minutes": {"type": "integer", "description": "How many more minutes to add"},
            },
            "required": ["event_title", "extra_minutes"],
        },
    },
    {
        "name": "complete_calendar_event",
        "description": "Mark a calendar event as completed/cancelled and dismiss its follow-up reminder. Use when user confirms they finished or cancelled a scheduled event.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_title": {"type": "string", "description": "Title of the calendar event to mark complete"},
                "outcome": {"type": "string", "enum": ["completed", "cancelled", "partial"], "description": "What happened with the event"},
            },
            "required": ["event_title", "outcome"],
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
                "message_type": {"type": "string", "enum": ["scheduling_request", "financial_settle", "follow_up_nudge", "info_request"]},
                "content": {"type": "object"},
            },
            "required": ["to_user_id", "message_type", "content"],
        },
    },

    # ── Tasks ──────────────────────────────────────────────────
    {"name": "delete_task", "description": "Permanently delete a task.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
    {"name": "get_overdue_tasks", "description": "Get all overdue tasks — tasks past their due date and not done.", "input_schema": {"type": "object", "properties": {}}},

    # ── Calendar ───────────────────────────────────────────────
    {"name": "reschedule_calendar_event", "description": "Move an existing calendar event to a new time.", "input_schema": {"type": "object", "properties": {"event_title": {"type": "string"}, "new_start_at": {"type": "string", "description": "ISO 8601"}, "new_end_at": {"type": "string", "description": "ISO 8601"}}, "required": ["event_title", "new_start_at", "new_end_at"]}},
    {"name": "delete_calendar_event", "description": "Cancel and delete a calendar event.", "input_schema": {"type": "object", "properties": {"event_title": {"type": "string"}}, "required": ["event_title"]}},
    {"name": "get_week_schedule", "description": "Get all calendar events for the current week.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "find_free_slot", "description": "Find an available time slot of a given duration this week.", "input_schema": {"type": "object", "properties": {"duration_minutes": {"type": "integer"}, "prefer": {"type": "string", "enum": ["morning", "afternoon", "evening"]}}, "required": ["duration_minutes"]}},
    {"name": "get_upcoming_events", "description": "Get upcoming calendar events for the next N days.", "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "default": 7}}}},

    # ── Reminders ──────────────────────────────────────────────
    {"name": "get_reminders", "description": "Get the user's reminders, optionally filtered by status.", "input_schema": {"type": "object", "properties": {"status": {"type": "string", "enum": ["pending", "fired", "snoozed"]}}}},
    {"name": "snooze_reminder", "description": "Snooze a reminder for a number of minutes.", "input_schema": {"type": "object", "properties": {"reminder_title": {"type": "string"}, "minutes": {"type": "integer", "default": 30}}, "required": ["reminder_title"]}},
    {"name": "dismiss_reminder", "description": "Dismiss a reminder.", "input_schema": {"type": "object", "properties": {"reminder_title": {"type": "string"}}, "required": ["reminder_title"]}},

    # ── Finance ────────────────────────────────────────────────
    {"name": "log_expense", "description": "Log a personal expense.", "input_schema": {"type": "object", "properties": {"amount": {"type": "number"}, "category": {"type": "string", "enum": ["food", "transport", "shopping", "health", "entertainment", "bills", "investment", "other"]}, "description": {"type": "string"}, "paid_to": {"type": "string"}}, "required": ["amount", "category"]}},
    {"name": "get_spending_summary", "description": "Get spending summary for the last N days.", "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "default": 30}}}},
    {"name": "track_subscription", "description": "Track a recurring subscription or bill.", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "amount": {"type": "number"}, "cycle": {"type": "string", "enum": ["daily", "weekly", "monthly", "yearly"]}, "next_due": {"type": "string"}}, "required": ["name", "amount", "cycle"]}},
    {"name": "get_subscriptions", "description": "List all active subscriptions and bills.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "track_owed_money", "description": "Track money owed between you and someone.", "input_schema": {"type": "object", "properties": {"person": {"type": "string"}, "amount": {"type": "number"}, "direction": {"type": "string", "enum": ["they_owe_me", "i_owe_them"]}, "reason": {"type": "string"}}, "required": ["person", "amount", "direction", "reason"]}},
    {"name": "get_owed_money", "description": "See who owes you money and who you owe.", "input_schema": {"type": "object", "properties": {}}},

    # ── Habits ─────────────────────────────────────────────────
    {"name": "create_habit", "description": "Create a new habit to track daily or weekly.", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "frequency": {"type": "string", "enum": ["daily", "weekly"]}, "remind_at": {"type": "string", "description": "HH:MM time"}}, "required": ["title"]}},
    {"name": "log_habit", "description": "Mark a habit as done for today.", "input_schema": {"type": "object", "properties": {"habit_title": {"type": "string"}, "note": {"type": "string"}}, "required": ["habit_title"]}},
    {"name": "get_habits", "description": "List all active habits.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_habit_streaks", "description": "Get current streak counts for all habits.", "input_schema": {"type": "object", "properties": {}}},

    # ── Projects ───────────────────────────────────────────────
    {"name": "create_project", "description": "Create a new project (larger than a goal, has multiple tasks).", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "due_date": {"type": "string"}}, "required": ["title"]}},
    {"name": "get_projects", "description": "List all active projects.", "input_schema": {"type": "object", "properties": {"status": {"type": "string", "enum": ["active", "paused", "completed"]}}}},
    {"name": "get_project_status", "description": "Get detailed status of a specific project including its tasks.", "input_schema": {"type": "object", "properties": {"project_title": {"type": "string"}}, "required": ["project_title"]}},
    {"name": "update_project", "description": "Update a project's status or details.", "input_schema": {"type": "object", "properties": {"project_title": {"type": "string"}, "status": {"type": "string", "enum": ["active", "paused", "completed", "abandoned"]}}, "required": ["project_title"]}},

    # ── Notes & Ideas ──────────────────────────────────────────
    {"name": "create_note", "description": "Save a note or idea.", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "content": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}}, "required": ["content"]}},
    {"name": "search_notes", "description": "Search through saved notes.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "get_notes", "description": "Get recent notes.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "append_to_note", "description": "Add more content to an existing note.", "input_schema": {"type": "object", "properties": {"note_title": {"type": "string"}, "content": {"type": "string"}}, "required": ["note_title", "content"]}},

    # ── Lists ──────────────────────────────────────────────────
    {"name": "add_to_list", "description": "Add an item to a named list (grocery, shopping, packing, etc).", "input_schema": {"type": "object", "properties": {"list_name": {"type": "string"}, "item": {"type": "string"}, "list_type": {"type": "string", "enum": ["grocery", "shopping", "todo", "packing", "general"]}}, "required": ["list_name", "item"]}},
    {"name": "get_list", "description": "Get all items in a named list.", "input_schema": {"type": "object", "properties": {"list_name": {"type": "string"}}, "required": ["list_name"]}},
    {"name": "clear_list", "description": "Clear all items from a list (e.g. after shopping).", "input_schema": {"type": "object", "properties": {"list_name": {"type": "string"}}, "required": ["list_name"]}},

    # ── Routines ───────────────────────────────────────────────
    {"name": "create_routine", "description": "Create a saved routine with steps (e.g. morning routine).", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "steps": {"type": "array", "items": {"type": "string"}}, "trigger_at": {"type": "string", "description": "HH:MM time"}}, "required": ["title", "steps"]}},
    {"name": "get_routines", "description": "List all saved routines.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "run_routine", "description": "Run a saved routine — returns its steps for APEX to walk through.", "input_schema": {"type": "object", "properties": {"routine_title": {"type": "string"}}, "required": ["routine_title"]}},

    # ── People & Relationships ─────────────────────────────────
    {"name": "add_person_note", "description": "Save a note about a person — birthday, preferences, relationship context.", "input_schema": {"type": "object", "properties": {"person": {"type": "string"}, "note": {"type": "string"}}, "required": ["person", "note"]}},
    {"name": "get_person_info", "description": "Get everything APEX knows about a specific person.", "input_schema": {"type": "object", "properties": {"person": {"type": "string"}}, "required": ["person"]}},
    {"name": "add_birthday", "description": "Remember someone's birthday and set a reminder.", "input_schema": {"type": "object", "properties": {"person": {"type": "string"}, "date": {"type": "string", "description": "MM-DD or YYYY-MM-DD"}, "remind_days_before": {"type": "integer", "default": 3}}, "required": ["person", "date"]}},
    {"name": "get_upcoming_birthdays", "description": "Get birthdays coming up in the next 30 days.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "log_interaction", "description": "Log that you interacted with someone today.", "input_schema": {"type": "object", "properties": {"person": {"type": "string"}, "note": {"type": "string"}}, "required": ["person"]}},
    {"name": "relationship_health", "description": "Show people you haven't interacted with in a while.", "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "default": 30}}}},

    # ── Health & Wellness ──────────────────────────────────────
    {"name": "log_workout", "description": "Log a workout or physical activity.", "input_schema": {"type": "object", "properties": {"activity": {"type": "string"}, "duration_minutes": {"type": "integer"}, "note": {"type": "string"}}, "required": ["activity"]}},
    {"name": "log_meal", "description": "Log what you ate.", "input_schema": {"type": "object", "properties": {"meal": {"type": "string"}, "when": {"type": "string", "enum": ["breakfast", "lunch", "dinner", "snack"]}}, "required": ["meal"]}},
    {"name": "log_sleep", "description": "Log last night's sleep.", "input_schema": {"type": "object", "properties": {"hours": {"type": "number"}, "quality": {"type": "string", "enum": ["poor", "okay", "good", "great"]}}, "required": ["hours"]}},
    {"name": "log_water", "description": "Log water intake in glasses.", "input_schema": {"type": "object", "properties": {"glasses": {"type": "integer"}}, "required": ["glasses"]}},
    {"name": "get_health_summary", "description": "Get a summary of health logs for the past week.", "input_schema": {"type": "object", "properties": {}}},

    # ── Journaling & Reflection ────────────────────────────────
    {"name": "add_journal_entry", "description": "Save a journal entry or reflection.", "input_schema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
    {"name": "log_win", "description": "Record a win or accomplishment worth celebrating.", "input_schema": {"type": "object", "properties": {"win": {"type": "string"}}, "required": ["win"]}},
    {"name": "get_wins", "description": "Show recent wins and accomplishments.", "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "default": 30}}}},

    # ── Learning & Reading ─────────────────────────────────────
    {"name": "add_book", "description": "Add a book to the reading list.", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "author": {"type": "string"}, "status": {"type": "string", "enum": ["want_to_read", "reading", "completed"]}}, "required": ["title"]}},
    {"name": "log_learning", "description": "Log something you learned today.", "input_schema": {"type": "object", "properties": {"content": {"type": "string"}, "topic": {"type": "string"}}, "required": ["content"]}},
    {"name": "get_reading_list", "description": "Get current reading list and learning log.", "input_schema": {"type": "object", "properties": {}}},

    # ── Drafting & Communication ───────────────────────────────
    {"name": "draft_message", "description": "Draft a message or reply for the user. Returns the draft text.", "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "about": {"type": "string"}, "tone": {"type": "string", "enum": ["professional", "friendly", "assertive", "apologetic"]}}, "required": ["to", "about"]}},
    {"name": "draft_email", "description": "Draft a professional email.", "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "about": {"type": "string"}, "tone": {"type": "string", "enum": ["professional", "friendly", "assertive"]}}, "required": ["to", "about"]}},
    {"name": "follow_up_tracker", "description": "Track something you're waiting for from someone.", "input_schema": {"type": "object", "properties": {"waiting_for": {"type": "string"}, "from_person": {"type": "string"}, "deadline": {"type": "string"}}, "required": ["waiting_for", "from_person"]}},
    {"name": "delegation_tracker", "description": "Track something you delegated to someone.", "input_schema": {"type": "object", "properties": {"task": {"type": "string"}, "delegated_to": {"type": "string"}, "due_date": {"type": "string"}}, "required": ["task", "delegated_to"]}},

    # ── Decision Support ───────────────────────────────────────
    {"name": "compare_options", "description": "Compare two or more options and give a recommendation.", "input_schema": {"type": "object", "properties": {"options": {"type": "array", "items": {"type": "string"}}, "context": {"type": "string"}}, "required": ["options"]}},
    {"name": "pros_cons", "description": "Generate pros and cons for a decision.", "input_schema": {"type": "object", "properties": {"decision": {"type": "string"}}, "required": ["decision"]}},

    # ── Proactive & Insights ───────────────────────────────────
    {"name": "workload_check", "description": "Check if the user is overcommitted this week.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "deadline_countdown", "description": "Show days remaining until a task or goal deadline.", "input_schema": {"type": "object", "properties": {"item": {"type": "string"}}, "required": ["item"]}},
    {"name": "get_daily_summary", "description": "Get a summary of what was accomplished today.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_focus_recommendation", "description": "Recommend what the user should focus on right now based on energy, deadlines, and priorities.", "input_schema": {"type": "object", "properties": {"energy_level": {"type": "string", "enum": ["low", "medium", "high"]}}}},

    # ── Utilities ─────────────────────────────────────────────
    {"name": "calculate", "description": "Do a quick calculation or unit conversion.", "input_schema": {"type": "object", "properties": {"expression": {"type": "string", "description": "Math expression or conversion e.g. '2000 * 30' or '500 USD to INR'"}}, "required": ["expression"]}},
    {"name": "time_zone_convert", "description": "Convert a time from one timezone to another.", "input_schema": {"type": "object", "properties": {"time": {"type": "string"}, "from_tz": {"type": "string"}, "to_tz": {"type": "string"}}, "required": ["time", "from_tz", "to_tz"]}},
    {"name": "get_weather", "description": "Get current weather for a city.", "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}},
]

TOOL_STATUS_MESSAGES: dict[str, str] = {
    # Tasks
    "create_task": "Adding that to your tasks...",
    "get_tasks": "Checking your task list...",
    "update_task": "Updating that task...",
    "delete_task": "Removing that task...",
    "get_overdue_tasks": "Checking what's overdue...",
    # Memory
    "search_memories": "Searching through what I know about you...",
    "store_memory": "Saving that to memory...",
    # Calendar
    "get_today_schedule": "Pulling up your calendar...",
    "create_calendar_event": "Creating that calendar event...",
    "extend_calendar_event": "Extending that for you...",
    "complete_calendar_event": "Marking that as done...",
    "reschedule_calendar_event": "Rescheduling that event...",
    "delete_calendar_event": "Cancelling that event...",
    "get_week_schedule": "Pulling up your week...",
    "find_free_slot": "Finding a free slot for you...",
    "get_upcoming_events": "Checking what's coming up...",
    # Goals
    "get_goals": "Checking your goals...",
    "create_goal": "Setting up that goal...",
    "update_goal": "Updating your goal...",
    # Reminders
    "create_reminder": "Setting that reminder...",
    "get_reminders": "Checking your reminders...",
    "snooze_reminder": "Snoozing that reminder...",
    "dismiss_reminder": "Dismissing that reminder...",
    # Finance
    "log_expense": "Logging that expense...",
    "get_spending_summary": "Crunching your spending...",
    "track_subscription": "Saving that subscription...",
    "get_subscriptions": "Checking your subscriptions...",
    "track_owed_money": "Tracking that for you...",
    "get_owed_money": "Checking who owes what...",
    # Habits
    "create_habit": "Setting up that habit...",
    "log_habit": "Logging that habit...",
    "get_habits": "Checking your habits...",
    "get_habit_streaks": "Checking your streaks...",
    # Projects
    "create_project": "Setting up that project...",
    "get_projects": "Checking your projects...",
    "get_project_status": "Pulling up project status...",
    "update_project": "Updating that project...",
    # Notes
    "create_note": "Saving that note...",
    "search_notes": "Searching your notes...",
    "get_notes": "Pulling up your notes...",
    "append_to_note": "Adding to that note...",
    # Lists
    "add_to_list": "Adding that to your list...",
    "get_list": "Pulling up your list...",
    "clear_list": "Clearing that list...",
    # Routines
    "create_routine": "Saving that routine...",
    "get_routines": "Checking your routines...",
    "run_routine": "Running your routine...",
    # People
    "add_person_note": "Saving that about them...",
    "get_person_info": "Pulling up what I know about them...",
    "add_birthday": "Saving that birthday...",
    "get_upcoming_birthdays": "Checking upcoming birthdays...",
    "log_interaction": "Logging that interaction...",
    "relationship_health": "Checking in on your relationships...",
    # Health
    "log_workout": "Logging that workout...",
    "log_meal": "Logging that meal...",
    "log_sleep": "Logging your sleep...",
    "log_water": "Logging your water intake...",
    "get_health_summary": "Pulling up your health summary...",
    # Journaling
    "add_journal_entry": "Saving that journal entry...",
    "log_win": "Celebrating that win...",
    "get_wins": "Pulling up your wins...",
    # Learning
    "add_book": "Adding that to your reading list...",
    "log_learning": "Saving what you learned...",
    "get_reading_list": "Checking your reading list...",
    # Drafting
    "draft_message": "Drafting that message...",
    "draft_email": "Writing that email...",
    "follow_up_tracker": "Tracking that follow-up...",
    "delegation_tracker": "Tracking that delegation...",
    # Decision support
    "compare_options": "Thinking through the options...",
    "pros_cons": "Weighing the pros and cons...",
    # Proactive
    "workload_check": "Checking your workload...",
    "deadline_countdown": "Calculating time remaining...",
    "get_daily_summary": "Summarising your day...",
    "get_focus_recommendation": "Figuring out what matters most right now...",
    # Utilities
    "calculate": "Calculating...",
    "time_zone_convert": "Converting that time...",
    "get_weather": "Checking the weather...",
    # Agent
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
