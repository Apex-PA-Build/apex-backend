import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.memory_service import semantic_search, extract_and_store_memories
from app.services.llm_service import chat
from typing import Any
from app.services.task_service import list_tasks

async def process_chat(user_id: str, message: str, db: AsyncSession) -> str:
    from app.core.logging import get_logger
    logger = get_logger(__name__)

    # 0. Extract and store any new memories/facts from the message
    # Awaiting to prevent SQLAlchemy concurrent AsyncSession errors, and 
    # wrapping in try/except so local environments without Qdrant don't crash.
    try:
        await extract_and_store_memories(user_id=user_id, text=message, source="chat", db=db)
    except Exception as e:
        logger.error(f"Memory extraction failed (likely Qdrant offline): {e}")

    # 1. Retrieve semantic context from Qdrant
    results = []
    try:
        results = await semantic_search(user_id=user_id, query=message, limit=10, db=db)
    except Exception as e:
        logger.error(f"Semantic search failed (likely Qdrant offline): {e}")
    
    context_lines = []
    for r in results:
        payload = r.get("payload", {})
        content = payload.get("content", "")
        category = payload.get("category", "info")
        if content:
            context_lines.append(f"- [{category.upper()}]: {content}")
            
    context_str = "\n".join(context_lines)
    if not context_str:
        context_str = "No existing memories found for this user yet."

    # 1.5 Retrieve pending tasks
    tasks, _ = await list_tasks(user_id=user_id, db=db, status="pending", limit=10)
    task_lines = []
    for t in tasks:
        task_lines.append(f"- [{t.priority.upper()}] {t.title} (Energy: {t.energy_required})")
    
    tasks_str = "\n".join(task_lines)
    if not tasks_str:
        tasks_str = "No pending tasks."

    # 2. Build system prompt
    system_prompt = f"""You are APEX, a highly capable, direct, proactive, and professional personal AI assistant.
Your goal is to act as a full-fledged intelligent partner, helping the user coordinate tasks, plan goals (like trips or projects), and recall information.

<context>
{context_str}
</context>

<pending_tasks>
{tasks_str}
</pending_tasks>

Instructions:
1. When the user expresses a goal or task (e.g., "I want to go on a trip", "plan my week"), proactively brainstorm, ask relevant follow-up questions (such as preferred dates, budget, or constraints), and offer to suggest options or handle logistics.
2. If the user asks what tasks they need to do, list their pending tasks concisely.
3. If the user asks for personal context, use the <context> supplied. Let your responses be naturally informed by these past facts.
4. If a fact wasn't provided, you can still logically deduce responses or plan proactively. Do not restrict yourself to only past facts.
5. Be professional, concise, and direct. Do not say 'Based on the context provided'. Never use emojis."""

    # 3. Call Gemini
    messages = [
        {"role": "user", "content": message}
    ]
    
    try:
        reply = await chat(messages=messages, system=system_prompt)
    except Exception as e:
        logger.error(f"LLM API Error: {e}")
        if "429" in str(e) or "quota" in str(e).lower():
            reply = "[System Messaage] Your Google Gemini API Free Tier rate limit has been exceeded. Please wait about a minute and try again."
        else:
            reply = "[System Message] My brain is currently offline. Please try again later."
            
    return reply
