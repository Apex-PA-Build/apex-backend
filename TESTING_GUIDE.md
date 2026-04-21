# APEX — Testing Guide

How to verify every part of the backend is working, from a 30-second smoke test to full end-to-end flows.

---

## Prerequisites

```bash
# 1. Start the server
uvicorn main:app --reload --port 8000

# 2. In another terminal, export your test JWT (get this from Supabase)
# Supabase Dashboard → Authentication → Users → click a user → copy JWT
export JWT="your-supabase-jwt-here"
export BASE="http://localhost:8000/api/v1"
```

---

## Level 1 — Is the server alive? (30 seconds)

```bash
# Root ping — no auth needed
curl http://localhost:8000/

# Health check — no auth needed
curl http://localhost:8000/health

# Swagger UI — open in browser
open http://localhost:8000/docs
```

**Expected:**
```json
{"service": "APEX", "status": "running", "version": "1.0.0"}
{"status": "ok"}
```
If `/docs` shows the Swagger page with all routes listed — the server is fully up.

---

## Level 2 — Auth & Profile

```bash
# Get your profile (tests JWT verification + Supabase connection)
curl -H "Authorization: Bearer $JWT" $BASE/auth/me

# Update your name
curl -X PATCH $BASE/auth/me \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"name": "Alex", "timezone": "America/New_York"}'

# Set mood
curl -X POST $BASE/auth/mood \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"mood": "focused"}'
```

**What this tests:** JWT verification, Supabase read/write, profile auto-creation on first login.

**Expected on GET /auth/me:**
```json
{
  "id": "your-user-uuid",
  "name": "Alex",
  "timezone": "America/New_York",
  "mood_today": "focused",
  "preferences": {},
  "created_at": "..."
}
```

---

## Level 3 — Tasks (full CRUD + AI features)

```bash
# Create a task (also triggers Eisenhower classification in background)
curl -X POST $BASE/tasks \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Prepare Q3 investor deck",
    "priority": "high",
    "energy_required": "high",
    "due_at": "2025-07-15T17:00:00Z"
  }'

# Save the task ID from the response
export TASK_ID="uuid-from-response"

# List all tasks
curl -H "Authorization: Bearer $JWT" "$BASE/tasks?status=pending"

# Get single task
curl -H "Authorization: Bearer $JWT" $BASE/tasks/$TASK_ID

# Update task status
curl -X PATCH $BASE/tasks/$TASK_ID \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress"}'

# Focus Now — which task should I work on?
curl -H "Authorization: Bearer $JWT" "$BASE/tasks/focus"
curl -H "Authorization: Bearer $JWT" "$BASE/tasks/focus?energy=high"

# Brain Dump — paste a wall of text, get tasks back
curl -X POST $BASE/tasks/brain-dump \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"text": "Call Sarah about the contract, finish slide deck before Friday, renew gym membership, review Jons PR"}'

# Replan day
curl -X POST $BASE/tasks/replan \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"reason": "I have a bad headache", "available_minutes": 60}'

# Delete task
curl -X DELETE -H "Authorization: Bearer $JWT" $BASE/tasks/$TASK_ID
```

**After creating a task, wait ~3 seconds then GET it again.** The `eisenhower_quadrant` field should now be `1`, `2`, `3`, or `4` — this confirms Claude Haiku is running and Anthropic API key is valid.

---

## Level 4 — Goals

```bash
# Create a goal
curl -X POST $BASE/goals \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Launch APEX MVP",
    "category": "work",
    "target_date": "2025-09-01",
    "check_in_schedule": "weekly"
  }'

export GOAL_ID="uuid-from-response"

# List goals
curl -H "Authorization: Bearer $JWT" $BASE/goals

# Recalculate progress
curl -X POST -H "Authorization: Bearer $JWT" $BASE/goals/$GOAL_ID/recalculate

# Weekly review (uses Claude Opus — tests expensive model)
curl -H "Authorization: Bearer $JWT" $BASE/goals/review

# Alignment check
curl -H "Authorization: Bearer $JWT" $BASE/goals/alignment
```

---

## Level 5 — Calendar

```bash
# Today's schedule with free blocks
curl -H "Authorization: Bearer $JWT" $BASE/calendar/today

# Create an event
curl -X POST $BASE/calendar/events \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Deep Work Block",
    "start_at": "2025-07-15T09:00:00Z",
    "end_at": "2025-07-15T11:00:00Z"
  }'
```

**Expected on /calendar/today:**
```json
{
  "events": [...],
  "free_blocks": [...],
  "total_meeting_minutes": 0,
  "deep_work_available": true,
  "conflicts": []
}
```

---

## Level 6 — Memory (tests Voyage AI + pgvector)

```bash
# Store a memory manually
curl -X POST $BASE/memory \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"content": "Alex prefers deep work in the morning before 11am", "category": "preference"}'

# List memories
curl -H "Authorization: Bearer $JWT" $BASE/memory

# Semantic search — finds relevant memories even with different wording
curl -X POST $BASE/memory/search \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"query": "when does the user like to focus?", "limit": 5}'
```

**The search test is the most important one here.** The query `"when does the user like to focus?"` should return the memory about morning deep work even though the wording is different. This confirms:
- Voyage AI embedding API is working
- pgvector `match_memories` RPC is installed in Supabase
- Similarity score should be > 0.7

---

## Level 7 — Daily Brief (Claude Opus)

```bash
curl -X POST $BASE/brief/generate \
  -H "Authorization: Bearer $JWT"
```

This call takes 5-15 seconds — Claude Opus is doing real synthesis. Expected response:
```json
{
  "greeting": "Good morning, Alex...",
  "narrative": "...",
  "focus_recommendation": "...",
  "risks": ["..."],
  "quick_wins": ["..."],
  "mood_prompt": "..."
}
```

If this works, your full AI pipeline (Supabase data fetch → Claude Opus → structured JSON response) is confirmed end-to-end.

---

## Level 8 — Chat (the main AI brain)

```bash
# Simple question
curl -X POST $BASE/chat \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "What should I focus on right now?"}'

# Action that triggers tools
curl -X POST $BASE/chat \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "Add a task to review the API docs with high priority"}'

# Multi-tool action
curl -X POST $BASE/chat \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a goal to ship APEX by September and add 3 tasks for this week to get started"}'
```

**Check the `tools_used` field in the response.** For the last message you should see `["create_goal", "create_task", "create_task", "create_task"]` — confirming the agentic loop with multiple tool rounds is working.

---

## Level 9 — Reminders

```bash
# Create a reminder (set it 2 minutes from now to test delivery)
curl -X POST $BASE/reminders \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test reminder",
    "body": "This is a test",
    "type": "time",
    "remind_at": "2025-07-15T10:02:00Z"
  }'

export REMINDER_ID="uuid-from-response"

# List reminders
curl -H "Authorization: Bearer $JWT" "$BASE/reminders?status=pending"

# Snooze
curl -X POST $BASE/reminders/$REMINDER_ID/snooze \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"minutes": 10}'

# Dismiss
curl -X POST -H "Authorization: Bearer $JWT" $BASE/reminders/$REMINDER_ID/dismiss
```

---

## Level 10 — Call Intelligence

```bash
# Start a call session
curl -X POST "$BASE/calls/start?title=Q3+Planning+Call" \
  -H "Authorization: Bearer $JWT"

export SESSION_ID="uuid-from-response"

# Add transcript chunks (do this a few times)
curl -X POST $BASE/calls/$SESSION_ID/transcript \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"text": "Okay team, lets align on Q3 targets. Revenue goal is 2 million."}'

curl -X POST $BASE/calls/$SESSION_ID/transcript \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"text": "Sarah, can you own the forecast by next Friday? John, please update the roadmap."}'

# End session — triggers AI analysis (takes ~5-10s)
curl -X POST $BASE/calls/$SESSION_ID/end \
  -H "Authorization: Bearer $JWT"
```

**Expected:** A full summary with `action_items`, `decisions`, `people_mentioned`, and `tasks_created > 0`. The tasks should appear in your task list automatically.

---

## Level 11 — WebSocket Chat (streaming)

Use this Python script to test the streaming WebSocket:

```python
# test_websocket.py
import asyncio
import json
import websockets

JWT = "your-supabase-jwt-here"

async def test_chat():
    uri = "ws://localhost:8000/api/v1/ws/chat"
    async with websockets.connect(uri) as ws:
        # Step 1: Auth handshake
        await ws.send(json.dumps({"token": JWT}))
        response = await ws.recv()
        print("Auth:", response)

        # Step 2: Send a message
        await ws.send(json.dumps({"message": "What are my top 3 tasks right now?"}))

        # Step 3: Stream events
        while True:
            event = json.loads(await ws.recv())
            print(f"[{event['type']}]", event.get("content", event.get("name", "")))
            if event["type"] == "done":
                break

asyncio.run(test_chat())
```

```bash
pip install websockets
python test_websocket.py
```

**Expected output:**
```
[connected] 
[tool_status] get_tasks
[tool_done] get_tasks
[chunk] Based on your tasks, here are...
[chunk] your top 3 priorities...
[done]
```

---

## Level 12 — Events WebSocket (reminders push)

```python
# test_events_ws.py
import asyncio
import json
import websockets

JWT = "your-supabase-jwt-here"

async def listen_events():
    uri = "ws://localhost:8000/api/v1/ws/events"
    async with websockets.connect(uri) as ws:
        # Auth
        await ws.send(json.dumps({"token": JWT}))
        print("Auth:", await ws.recv())

        print("Listening for events... (create a reminder due soon to test)")
        
        # Keepalive + listen
        while True:
            try:
                event = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                print("EVENT RECEIVED:", event)
            except asyncio.TimeoutError:
                # Send ping to keep alive
                await ws.send(json.dumps({"type": "ping"}))
                pong = await ws.recv()
                print("Keepalive:", pong)

asyncio.run(listen_events())
```

To trigger a real event, create a reminder with `remind_at` set 1-2 minutes from now while this script is running. The APScheduler checks every 5 minutes so you may need to wait.

---

## Level 13 — Error Handling Tests

```bash
# 401 — no token
curl $BASE/tasks
# Expected: {"detail": "Missing authorization header"}

# 401 — bad token
curl -H "Authorization: Bearer bad-token" $BASE/tasks
# Expected: {"detail": "Invalid token"}

# 404 — task not found
curl -H "Authorization: Bearer $JWT" $BASE/tasks/00000000-0000-0000-0000-000000000000
# Expected: {"detail": "Task not found"}

# 422 — missing required field
curl -X POST $BASE/tasks \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{}'
# Expected: 422 Unprocessable Entity with field validation errors

# 429 — rate limit (fire 65 requests fast)
for i in $(seq 1 65); do curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $JWT" $BASE/health; done
# Expected: first 60 return 200, then 429
```

---

## Quick Diagnostic Checklist

Run these in order when something is broken:

| Test | Command | If it fails |
|------|---------|-------------|
| Server up | `curl localhost:8000/health` | Restart uvicorn |
| Supabase connected | `curl -H "Auth: Bearer $JWT" $BASE/auth/me` | Check SUPABASE_URL + ANON_KEY in .env |
| JWT valid | Same as above, look for 401 | Get fresh JWT from Supabase dashboard |
| Anthropic working | Create a task, wait 3s, GET it — check `eisenhower_quadrant` | Check ANTHROPIC_API_KEY in .env |
| Voyage AI working | POST to `/memory/search` | Check VOYAGE_API_KEY in .env |
| pgvector installed | Same as above, look for RPC error | Run `supabase/schema.sql` in Supabase SQL Editor |
| Redis working | Check server logs on startup for `redis_connected` | Run `brew services start redis` |
| Reminders firing | Check server logs every 5 min for `_check_and_fire_reminders` | Redis or scheduler issue |

---

## Using Swagger UI (no curl needed)

1. Open `http://localhost:8000/docs`
2. Click **Authorize** (top right)
3. Enter: `Bearer your-jwt-here`
4. Click any endpoint → **Try it out** → **Execute**

Every endpoint can be tested interactively this way. The request/response schema is shown automatically.

---

## What a Fully Working System Looks Like

```
✓ GET /health                    → {"status": "ok"}
✓ GET /auth/me                   → profile object (Supabase connected)
✓ POST /tasks                    → task created
✓ GET /tasks/{id} after 3s       → eisenhower_quadrant set (Claude Haiku working)
✓ POST /memory/search            → results with similarity score (Voyage AI + pgvector working)
✓ POST /brief/generate           → full brief object (Claude Opus working)
✓ POST /chat with action message → reply + tools_used list (agentic loop working)
✓ WS /ws/chat                    → streaming chunks (WebSocket + streaming working)
✓ Server logs show:
    apex_starting
    supabase_connected
    redis_connected
    scheduler_started
    apex_ready
```
