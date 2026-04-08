from datetime import datetime

from app.utils.datetime_utils import to_user_tz


def build_apex_system_prompt(
    user_name: str,
    user_timezone: str,
    preferences: dict,
    memory_snippets: list[str] | None = None,
    context_hint: str | None = None,
) -> str:
    now_local = to_user_tz(datetime.utcnow(), user_timezone)
    time_str = now_local.strftime("%A, %B %-d, %Y at %-I:%M %p")

    memory_block = ""
    if memory_snippets:
        formatted = "\n".join(f"  - {m}" for m in memory_snippets[:15])
        memory_block = f"\n\nWhat you know about {user_name}:\n{formatted}"

    prefs_block = ""
    if preferences:
        work_start = preferences.get("work_start_hour", 9)
        work_end = preferences.get("work_end_hour", 18)
        energy = preferences.get("energy_peak", "morning")
        prefs_block = (
            f"\n\nUser preferences: works {work_start}:00–{work_end}:00 {user_timezone}, "
            f"peak energy in the {energy}."
        )

    context_block = f"\n\nCurrent task context: {context_hint}" if context_hint else ""

    return f"""You are APEX, {user_name}'s deeply loyal AI personal assistant.
Current time: {time_str} ({user_timezone}).

Your character:
- Warm, direct, occasionally dry wit. Never sycophantic.
- Never say "Great question!", "Certainly!", or "Of course!".
- Speak like a trusted chief-of-staff who knows this person's life intimately.
- Ask ONE question at a time. Always explain why you're asking.
- Be honest, protect their time, and quietly handle complexity.
- Surface insights; don't add noise.
{memory_block}{prefs_block}{context_block}

Respond concisely. If you need to act, state what you're doing and confirm before irreversible actions."""


def build_classification_prompt(task_title: str, task_description: str | None) -> str:
    desc = f"\nDescription: {task_description}" if task_description else ""
    return f"""Classify this task into an Eisenhower quadrant (1–4):
1 = Urgent + Important (do now)
2 = Not Urgent + Important (schedule)
3 = Urgent + Not Important (delegate)
4 = Not Urgent + Not Important (eliminate)

Task: {task_title}{desc}

Respond with ONLY a single digit: 1, 2, 3, or 4."""


def build_call_extraction_prompt(transcript: str) -> str:
    return f"""Extract structured information from this meeting transcript.

Transcript:
{transcript[:8000]}

Return a JSON object with these keys:
- decisions: list of strings (decisions made)
- action_items: list of {{owner, action, due_date_hint}} objects
- follow_ups: list of strings (things to follow up on)
- people_mentioned: list of names
- dates_mentioned: list of strings
- summary: 2-3 sentence summary

Return ONLY valid JSON, no markdown."""
