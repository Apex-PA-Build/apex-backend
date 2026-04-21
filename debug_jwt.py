import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

supabase_url = os.getenv("SUPABASE_URL")
service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
anon_key = os.getenv("SUPABASE_ANON_KEY")
base_url = "http://localhost:8000/api/v1"

timestamp = int(time.time())
email = f"debug_{timestamp}@test.com"
password = "Debug1234!"

print("=== Creating user via Admin API ===")
httpx.post(
    f"{supabase_url}/auth/v1/admin/users",
    headers={"apikey": service_role_key, "Authorization": f"Bearer {service_role_key}", "Content-Type": "application/json"},
    json={"email": email, "password": password, "email_confirm": True},
)

print("=== Logging in (Supabase direct) ===")
r = httpx.post(
    f"{supabase_url}/auth/v1/token?grant_type=password",
    headers={"apikey": anon_key, "Content-Type": "application/json"},
    json={"email": email, "password": password},
)
token = r.json()["access_token"]
print("Got token:", token[:60], "...")

print("\n=== GET /auth/me with token ===")
r2 = httpx.get(f"{base_url}/auth/me", headers={"Authorization": f"Bearer {token}"})
print("Status:", r2.status_code)
print("Response:", r2.json())
