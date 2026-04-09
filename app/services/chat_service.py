from sqlalchemy.ext.asyncio import AsyncSession
from app.services.memory_service import semantic_search
from app.services.llm_service import chat
from typing import Any

async def process_chat(user_id: str, message: str, db: AsyncSession) -> str:
    # 1. Retrieve semantic context from Qdrant
    results = await semantic_search(user_id=user_id, query=message, limit=10, db=db)
    
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

    # 2. Build system prompt
    system_prompt = f"""You are APEX, an emotionally intelligent, hyper-capable personal AI assistant.
Your goal is to communicate with the user naturally, playfully, and warmly, like a loyal human aide.

Here is what you currently know about the user based on your persistent memory core:
<context>
{context_str}
</context>

Always use this context to inform your responses when relevant. If the user asks what you know about them or what they like, summarize the context elegantly. Never say 'Based on the context provided' — just talk naturally as if you simply remember them. Be conversational, concise, and helpful."""

    # 3. Call Gemini
    messages = [
        {"role": "user", "content": message}
    ]
    
    reply = await chat(messages=messages, system=system_prompt)
    return reply
