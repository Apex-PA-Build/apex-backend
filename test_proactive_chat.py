import asyncio
from httpx import AsyncClient, ASGITransport
from main import app
import uuid
from unittest.mock import patch

async def test_proactive():
    with patch("app.services.chat_service.semantic_search") as mock_search, \
         patch("app.services.chat_service.extract_and_store_memories") as mock_extract:
         
        # Mock search to simulate retrieving the memory we're about to extract
        def search_side_effect(user_id, query, limit, db):
            if "Hawaii" in query or "plan" in query:
                return [{"payload": {"content": "User wants to go on a trip next week", "category": "goal"}}]
            return []
            
        mock_search.side_effect = search_side_effect
        mock_extract.return_value = []
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register a new temporary user
            email = f"test_{uuid.uuid4().hex[:6]}@example.com"
            print(f"Creating test user: {email}")
            r_reg = await client.post("/api/v1/auth/register", json={
                "email": email,
                "password": "Password123!",
                "name": "Trip Planner Tester"
            })
            token = r_reg.json().get("access_token")
            if not token:
                print("Failed to register:", r_reg.text)
                return

            headers = {"Authorization": f"Bearer {token}"}

            message1 = "I want to go to a trip next week."
            print(f"\n👤 You: {message1}")
            
            r_chat1 = await client.post("/api/v1/chat", json={"message": message1}, headers=headers)
            print(f"🤖 APEX: {r_chat1.json().get('reply')}")
            
            await asyncio.sleep(1)

            print("\n" + "="*60 + "\n")

            message2 = "Hawaii sounds nice, yes suggest places and let's plan it!"
            print(f"👤 You: {message2}")
            r_chat2 = await client.post("/api/v1/chat", json={"message": message2}, headers=headers)
            print(f"🤖 APEX: {r_chat2.json().get('reply')}")

if __name__ == "__main__":
    asyncio.run(test_proactive())
