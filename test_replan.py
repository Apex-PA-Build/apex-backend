import httpx
import uuid
import json

base_url = "http://localhost:8000/api/v1"
with httpx.Client(base_url=base_url, timeout=30.0) as client:
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    r_reg = client.post("/auth/register", json={
        "email": email,
        "password": "Password123!",
        "name": "Test User"
    })

    if r_reg.status_code not in (200, 201):
        print(f"Register failed: {r_reg.text}")
        exit(1)

    token = r_reg.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create tasks
    print("🧠 Dumping tasks...")
    client.post("/tasks/brain-dump", json={
        "text": "Finish the pitch deck today. Also read 10 pages of my book. Do the laundry."
    }, headers=headers)

    # 2. Replan the day
    print("🔄 Testing replan-day...")
    r_replan = client.post("/tasks/replan-day", json={
        "context": "I'm experiencing a massive crash and have a huge migraine. I can't look at screens anymore today."
    }, headers=headers)

    print(json.dumps(r_replan.json(), indent=2))
