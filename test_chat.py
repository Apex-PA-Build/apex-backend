import httpx
import uuid
import json

base_url = "http://localhost:8000/api/v1"
with httpx.Client(base_url=base_url, timeout=30.0) as client:
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    r_reg = client.post("/auth/register", json={
        "email": email,
        "password": "Password123!",
        "name": "Chatbot Tester"
    })
    token = r_reg.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Seed memory
    text = "Yesterday, I told Sarah that I really love blueberry muffins, but I absolutely hate chocolate cake."
    print("🧠 Seeding memory...")
    r_brain = client.post("/tasks/brain-dump", json={"text": text}, headers=headers)
    print("Brain dump status:", r_brain.status_code)
    
    # 2. Chat API
    print("🗣️ Asking chat...")
    r_chat = client.post("/chat", json={"message": "What kind of desserts do I like?"}, headers=headers)
    print("Chat status:", r_chat.status_code)
    try:
        print(json.dumps(r_chat.json(), indent=2))
    except:
        print(r_chat.text)
