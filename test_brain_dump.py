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

    r_brain = client.post("/tasks/brain-dump", json={
        "text": "I really need to finish the pitch deck today. Oh, and I have to call mom sometime this weekend. Getting groceries is also super important since the fridge is empty."
    }, headers={"Authorization": f"Bearer {token}"})

    print(json.dumps(r_brain.json(), indent=2))
