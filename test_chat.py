import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from jose import jwt

# We read secret from .env or hardcode what we saw in .env
JWT_SECRET_KEY = "5f7ee9ba834befc6aa2a91c8908b0020cc7664e372919068a36ae3de09cf7cda"
JWT_ALGORITHM = "HS256"

def create_access_token(user_id: str):
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    to_encode = {
        "sub": user_id,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

async def main():
    user_id = "677bc557-3108-4327-8515-b544cee480a9"
    token = create_access_token(user_id)
    
    url = "http://localhost:8000/api/v1/chat"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": "I want to plan a trip to north india next week"
    }
    
    print("Hitting Chat Endpoint with fresh token...")
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        
        print("\nStatus Code:", response.status_code)
        try:
            print("Response:", response.json())
        except Exception:
            print("Raw Response:", response.text)

if __name__ == "__main__":
    asyncio.run(main())
