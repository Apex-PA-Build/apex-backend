import json
from collections.abc import AsyncGenerator
from typing import Any

from app.core import cache
from app.core.logging import get_logger
from app.core.supabase import get_client
from app.services import agent as agent_svc
from app.services import calendar as cal_svc
from app.services import goal as goal_svc
from app.services import llm
from app.services import memory as mem_svc
from app.services import reminder as reminder_svc
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
