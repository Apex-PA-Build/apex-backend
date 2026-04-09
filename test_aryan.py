import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.memory import Memory
import app.models.task  # required for relations
from app.core.security import create_access_token
import httpx
import json
from app.db.vector_store import upsert_memory
import google.generativeai as genai
from app.core.config import settings

genai.configure(api_key=settings.gemini_api_key)

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email.ilike("aryan%@example.com%")))
        user = res.scalars().first()
        if not user:
            print("Could not find Aryan!")
            return
            
        print(f"✅ Found Aryan (email: {user.email})! ID: {user.id}")
        
        # 1. Sync Postgres Memories to Qdrant
        # Since I dropped the Qdrant database earlier to change dimensions, 
        # I need to re-vectorize his existing memories so APEX actually has access to them!
        memories = await db.execute(select(Memory).where(Memory.user_id == user.id))
        all_mems = memories.scalars().all()
        if all_mems:
            print(f"🧠 Syncing {len(all_mems)} existing memories from Postgres back into Qdrant...")
            for mem in all_mems:
                try:
                    emb_res = genai.embed_content(
                        model="models/gemini-embedding-001",
                        content=mem.content,
                        task_type="retrieval_document"
                    )
                    await upsert_memory(
                        memory_id=mem.id,
                        embedding=emb_res["embedding"],
                        payload={"user_id": str(user.id), "content": mem.content, "category": mem.category}
                    )
                except Exception as e:
                    print("Failed to embed memory:", str(e))
        else:
            print("🧠 Aryan has no existing memories in Postgres database yet.")
            
        # 2. Generate a token
        token = create_access_token(str(user.id))
        
        # 3. Hit the Chat API!
        base_url = "http://localhost:8000/api/v1"
        async with httpx.AsyncClient(base_url=base_url) as client:
            headers = {"Authorization": f"Bearer {token}"}
            msg = "Who am I and what do you know about me? Don't hold back."
            print(f"\n🗣️ Chatting as Aryan: '{msg}'")
            
            r_chat = await client.post(
                "/chat", 
                json={"message": msg}, 
                headers=headers, 
                timeout=45.0
            )
            
            try:
                print(json.dumps(r_chat.json(), indent=2))
            except:
                print(r_chat.text)

if __name__ == "__main__":
    asyncio.run(main())
