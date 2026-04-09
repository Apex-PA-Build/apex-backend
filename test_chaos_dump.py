import httpx
import uuid
import json

text = """Iok so tomorrow I need to wake up early like 6?? no 5:30 actually because gym but I didn’t sleep early today so maybe skip gym?? but no I already paid for trainer 😭

also email Rahul about the design thing WAIT what design thing?? oh yeah landing page v2, but I haven’t finished it lol

groceries:
- milk
- eggs
- something healthy?? idk maybe salad stuff
also check if I still have rice

CALL MOM (important don’t forget again like last time omg)

idea: what if app automatically groups thoughts like this?? (note this for later)

also taxes?? when is deadline?? shit

meeting at 11 or 12?? I think 11 but not sure check calendar

why is my room so messy I should clean it but also I won’t

water plants (they’re dying again)

also random but what if I move to another city lol

ok focus: presentation slides not done AT ALL
deadline?? tomorrow?? day after??

also drink water"""

base_url = "http://localhost:8000/api/v1"
with httpx.Client(base_url=base_url, timeout=45.0) as client:
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    r_reg = client.post("/auth/register", json={
        "email": email,
        "password": "Password123!",
        "name": "Chaos Tester"
    })

    if r_reg.status_code not in (200, 201):
        print(f"Register failed: {r_reg.text}")
        exit(1)

    token = r_reg.json().get("access_token")

    r_brain = client.post("/tasks/brain-dump", json={
        "text": text
    }, headers={"Authorization": f"Bearer {token}"})

    print(json.dumps(r_brain.json(), indent=2))
