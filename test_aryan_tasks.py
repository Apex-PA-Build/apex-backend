import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.memory import Memory
import app.models.task
import app.models.goal
import app.models.integration
from app.core.security import create_access_token
import httpx
import json

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email.ilike("aryan%@example.com%")))
        user = res.scalars().first()
        if not user:
            print("Could not find Aryan!")
            return
            
        print(f"✅ Found Aryan (email: {user.email})! ID: {user.id}")
        
        # 1. Generate a token
        token = create_access_token(str(user.id))
        
        # 2. Hit the APIs!
        base_url = "http://localhost:8000/api/v1"
        try:
            async with httpx.AsyncClient(base_url=base_url) as client:
                headers = {"Authorization": f"Bearer {token}"}
                
                # A: Seed some tasks
                print("\n🧠 Injecting tasks via Brain-Dump...")
                bd_resp = await client.post(
                    "/tasks/brain-dump",
                    json={"text": "I really need to finish the final physics paper by 10pm tonight, and also buy milk from the corner store."},
                    headers=headers,
                    timeout=45.0
                )
                print(f"Brain dump status: {bd_resp.status_code}")
                
                # B: Ask Chat
                msg = "What do I need to get done?"
                print(f"\n🗣️ Chatting as Aryan: '{msg}'")
                
                r_chat = await client.post(
                    "/chat", 
                    json={"message": msg}, 
                    headers=headers, 
                    timeout=45.0
                )
                print(f"Chat status: {r_chat.status_code}")
                
                try:
                    print(json.dumps(r_chat.json(), indent=2))
                except:
                    print(r_chat.text)
                    
        except Exception as e:
            print("Test failed!", str(e))

if __name__ == "__main__":
    asyncio.run(main())
