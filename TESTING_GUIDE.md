# APEX — Testing Guide

End-to-end tests covering all 78 tools, streaming, session memory, and error handling.

---

## Setup

```bash
# 1. Start the server
uvicorn main:app --reload --port 8000

# 2. Export your JWT (Supabase Dashboard → Authentication → Users → click user → copy JWT)
export JWT="your-supabase-jwt-here"
export BASE="http://localhost:8000/api/v1"
```

---

## Level 1 — Server Alive (30 seconds)

```bash
curl http://localhost:8000/
curl http://localhost:8000/health
open http://localhost:8000/docs
```

**Expected:**
```json
{"service": "APEX", "status": "running", "version": "1.0.0"}
{"status": "ok"}
```

---

## Level 2 — Auth & Profile

```bash
curl -H "Authorization: Bearer $JWT" $BASE/auth/me

curl -X PATCH $BASE/auth/me \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"name": "Yathish", "timezone": "Asia/Kolkata"}'

curl -X POST $BASE/auth/mood \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"mood": "focused"}'
```

---

## Level 3 — Tasks + Goals (CRUD)

```bash
# Create task
curl -X POST $BASE/tasks \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"title": "Prepare Q3 investor deck", "priority": "high", "energy_required": "high"}'

# Create goal
curl -X POST $BASE/goals \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"title": "Launch APEX MVP", "category": "work", "target_date": "2025-09-01"}'

# Focus recommendation
curl -H "Authorization: Bearer $JWT" $BASE/tasks/focus
```

---

## Level 4 — Reminders

```bash
# Create reminder (set remind_at 2 minutes from now)
curl -X POST $BASE/reminders \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"title": "Test reminder", "body": "Is this working?", "type": "time", "remind_at": "2025-07-15T10:02:00Z"}'

export REMINDER_ID="uuid-from-response"

# List
curl -H "Authorization: Bearer $JWT" "$BASE/reminders?status=pending"

# Snooze
curl -X POST $BASE/reminders/$REMINDER_ID/snooze \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"minutes": 10}'

# Dismiss all
curl -X POST -H "Authorization: Bearer $JWT" $BASE/reminders/dismiss-all
```

---

## Level 5 — Memory (Semantic Search)

```bash
# Store
curl -X POST $BASE/memory \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"content": "Yathish prefers deep work before 11am, no meetings before 9am", "category": "preference"}'

# Semantic search — different wording, should still match
curl -X POST $BASE/memory/search \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"query": "when does the user like to focus?", "limit": 5}'
```

**If the search returns the stored memory — Voyage AI + pgvector is working.**

---

## Level 6 — Streaming Chat (SSE)

```bash
curl -s -N -X POST "$BASE/chat/stream" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "Give me a full morning brief — weather in Bangalore, todays schedule, top goal progress, and what to focus on first"}' \
  --no-buffer
```

**Expected output (SSE events):**
```
data: {"type":"status","message":"Checking your calendar..."}
data: {"type":"status","message":"Reviewing your goals..."}
data: {"type":"text","content":"Good morning! Here's your brief..."}
data: {"type":"text","content":" The weather in Bangalore today is..."}
data: {"type":"done"}
```

---

## Level 7 — Chat: Session Memory (Context Carry-Over)

Send these in the **same session_id** — APEX must remember context between turns.

```bash
SESSION="session-test-$(date +%s)"

# Turn 1 — create a goal
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Create a goal: Launch APEX beta by June 30\", \"session_id\": \"$SESSION\"}" | jq .reply

# Turn 2 — update it (tests: APEX must know WHICH goal from turn 1)
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Update that goal to 40% complete\", \"session_id\": \"$SESSION\"}" | jq .reply

# Turn 3 — update again using "it" (tests deep context retention)
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"I just finished the streaming feature, bump it to 60%\", \"session_id\": \"$SESSION\"}" | jq .reply
```

**Pass criteria:** Turn 2 and 3 must update the correct goal without asking "which goal?" again.

---

## Level 8 — Chat: Multi-Tool in One Message

```bash
# APEX should call log_expense 3 times from one sentence
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "I spent 850 on groceries, 200 on an Uber, and 1200 on dinner with a client today"}' | jq '{reply: .reply, tools: .tools_used}'

# Should call time_zone_convert + get_weather + create_calendar_event
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "My team in New York wants to meet at 3pm their time tomorrow. What time is that for me in Bangalore, whats the weather there, and block that meeting in my calendar"}' | jq '{reply: .reply, tools: .tools_used}'
```

**Check `tools_used` in response** — multiple tools should appear.

---

## Level 9 — Calendar: Create → Extend → Complete

```bash
SESSION="cal-$(date +%s)"

# Step 1: Create
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Schedule a deep work block tomorrow 10am to 12pm called Project Review\", \"session_id\": \"$SESSION\"}" | jq .reply

# Step 2: Extend (fuzzy title match must work)
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Extend the Project Review by 30 minutes\", \"session_id\": \"$SESSION\"}" | jq .reply

# Step 3: Complete
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"I just finished the Project Review, mark it done\", \"session_id\": \"$SESSION\"}" | jq .reply
```

**Pass criteria:** Step 2 must update `end_at` of existing event (not create a new one). Step 3 must set status to completed and dismiss the follow-up reminder.

---

## Level 10 — Finance Flow

```bash
SESSION="finance-$(date +%s)"

# Log expenses
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"I spent 850 on groceries, 200 on Uber, and 1200 on dinner with a client today\", \"session_id\": \"$SESSION\"}" | jq .reply

# Add subscription
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Track my Netflix subscription at 649 rupees per month\", \"session_id\": \"$SESSION\"}" | jq .reply

# Track money owed
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Rahul owes me 500 rupees for the Uber last week\", \"session_id\": \"$SESSION\"}" | jq .reply

# Get spending summary
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"How much have I spent this week and what do people owe me?\", \"session_id\": \"$SESSION\"}" | jq .reply
```

---

## Level 11 — Habits: Create → Log → Streaks

```bash
SESSION="habit-$(date +%s)"

# Create 3 habits
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Create habits for: daily meditation (target 10 minutes), running (target 30 minutes), reading (target 20 pages)\", \"session_id\": \"$SESSION\"}" | jq .reply

# Log all three from one message
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Done for today — meditated 15 minutes, ran 5km in 35 minutes, read 22 pages\", \"session_id\": \"$SESSION\"}" | jq .reply

# Check streaks
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Show me my habit streaks\", \"session_id\": \"$SESSION\"}" | jq .reply
```

**Pass criteria:** Log turn must call `log_habit` 3 times (one per habit) from a single sentence.

---

## Level 12 — Project + Notes + Lists (Linked Flow)

```bash
SESSION="project-$(date +%s)"

# Create project
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Create a project called APEX Launch with deadline May 15th, status in_progress\", \"session_id\": \"$SESSION\"}" | jq .reply

# Create note for the project
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Note titled APEX Launch: Need to finish streaming, fix calendar bugs, and deploy before May 15\", \"session_id\": \"$SESSION\"}" | jq .reply

# Create a checklist
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Create APEX Launch checklist with: streaming endpoint, calendar fix, deploy script, user testing\", \"session_id\": \"$SESSION\"}" | jq .reply

# Full status pull
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Show me everything about the APEX Launch project — status, notes, and checklist\", \"session_id\": \"$SESSION\"}" | jq .reply
```

---

## Level 13 — Routines: Create → Run

```bash
SESSION="routine-$(date +%s)"

# Create
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Create a morning routine: 1) Drink water 2) 10 min meditation 3) Review todays calendar 4) Pick top 3 tasks 5) Start deep work\", \"session_id\": \"$SESSION\"}" | jq .reply

# Run it
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Run my morning routine\", \"session_id\": \"$SESSION\"}" | jq .reply
```

---

## Level 14 — Daily Summary + Workload Check

```bash
SESSION="workload-$(date +%s)"

# Stack the plate with tasks
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"I need to finish the API docs, review 3 PRs, call the client, prep the demo, and submit tax docs — all by tomorrow\", \"session_id\": \"$SESSION\"}" | jq .reply

# Reality check
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Check my workload and tell me honestly if this is doable\", \"session_id\": \"$SESSION\"}" | jq .reply

# Full summary
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "Give me todays full summary"}' | jq .reply
```

---

## Level 15 — Decision Support

```bash
# Multi-option comparison
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "Help me decide: Option A - take freelance project (more money, less time), Option B - focus on APEX launch (more impact, zero income for 2 months), Option C - do both part time (balanced but risky)"}' | jq .reply

# Pros and cons
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "Give me pros and cons of moving from Bangalore to Hyderabad for work"}' | jq .reply

# Deadline countdown
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "How many days do I have left until my APEX launch deadline and am I on track?"}' | jq .reply
```

---

## Level 16 — Health + Journal + Wins

```bash
SESSION="health-$(date +%s)"

# Log health data
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Logged: slept 7.5 hours, drank 2.5 litres of water, had oats for breakfast\", \"session_id\": \"$SESSION\"}" | jq .reply

# Log a workout
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Just finished a 45 minute chest and shoulder workout\", \"session_id\": \"$SESSION\"}" | jq .reply

# Journal + win
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Journal: Finally cracked the streaming issue after 3 hours. Worth it. Also log a win — fixed the APEX streaming bug!\", \"session_id\": \"$SESSION\"}" | jq .reply

# Summary
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Show me my health summary and recent wins\", \"session_id\": \"$SESSION\"}" | jq .reply
```

---

## Level 17 — People / Relationships

```bash
SESSION="people-$(date +%s)"

# Add person note
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Note about Rahul: He's a senior engineer at Flipkart, we met at JSConf 2024, interested in collaborating on APEX\", \"session_id\": \"$SESSION\"}" | jq .reply

# Add birthday
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Rahul's birthday is March 15\", \"session_id\": \"$SESSION\"}" | jq .reply

# Log interaction
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Had coffee with Rahul today, discussed potential partnership on APEX\", \"session_id\": \"$SESSION\"}" | jq .reply

# Check upcoming birthdays
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Who has a birthday coming up in the next 30 days?\", \"session_id\": \"$SESSION\"}" | jq .reply
```

---

## Level 18 — Learning + Books

```bash
SESSION="learning-$(date +%s)"

# Add book
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Add Deep Work by Cal Newport to my reading list\", \"session_id\": \"$SESSION\"}" | jq .reply

# Log learning
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Just learned about pgvector indexing — HNSW index is faster for approximate search, IVFFlat is better for exact. Save this.\", \"session_id\": \"$SESSION\"}" | jq .reply

# Get reading list
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"What books are on my reading list?\", \"session_id\": \"$SESSION\"}" | jq .reply
```

---

## Level 19 — Utilities

```bash
# Calculate
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 18% GST on 47500 rupees?"}' | jq .reply

# Timezone convert
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "Convert 3pm New York time to Bangalore time"}' | jq .reply

# Weather
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "Whats the weather like in Bangalore right now?"}' | jq .reply

# Drafting
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "Draft a WhatsApp message to my client Priya saying I need 2 more days on the feature, professional but friendly tone"}' | jq .reply
```

---

## Level 20 — Error Handling (Should Not Crash)

```bash
# Non-existent list — should return empty, not 500
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me my unicorn list"}' | jq .reply

# Extend event that does not exist
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "Extend my dentist appointment by 1 hour"}' | jq .reply

# Bad math expression
curl -s -X POST "$BASE/chat" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "Calculate: drop table users"}' | jq .reply

# Missing required fields
curl -X POST $BASE/tasks \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{}' | jq .
# Expected: 422 with validation errors, not 500

# Expired / bad token
curl -H "Authorization: Bearer bad-token" $BASE/tasks | jq .
# Expected: 401
```

---

## Supabase Realtime — Notification Test

After setting up Realtime on the `reminders` table in Supabase:

1. Open Supabase Table Editor → `reminders` table in a browser tab
2. Create a reminder with `remind_at` = now + 1 minute via chat:
   ```bash
   curl -s -X POST "$BASE/chat" \
     -H "Authorization: Bearer $JWT" \
     -H "Content-Type: application/json" \
     -d '{"message": "Remind me to drink water in 1 minute"}' | jq .reply
   ```
3. Watch the server logs — you should see `_check_and_fire_reminders` fire and update `status` to `fired`
4. In Supabase Table Editor, the row's `status` column should change to `fired` in real-time
5. On the UI side, the Supabase Realtime subscription should receive that row update and trigger the notification

---

## Quick Diagnostic Checklist

| Test | Command | If it fails |
|------|---------|-------------|
| Server up | `curl localhost:8000/health` | Restart uvicorn |
| Supabase connected | `curl -H "Authorization: Bearer $JWT" $BASE/auth/me` | Check SUPABASE_URL + ANON_KEY in .env |
| JWT valid | Same, look for 401 | Get fresh JWT from Supabase dashboard |
| Anthropic API | Create task, wait 3s, GET it — check `eisenhower_quadrant` | Check ANTHROPIC_API_KEY in .env |
| Voyage AI + pgvector | POST `/memory/search` | Check VOYAGE_API_KEY, run schema.sql |
| New tables exist | Chat: "add milk to grocery list" | Run `supabase/schema_v2.sql` in SQL Editor |
| Streaming works | `curl -N POST /chat/stream` — SSE events flow | Check for errors in server logs |
| Reminders firing | Server logs every 30s for `_check_and_fire_reminders` | Check APScheduler started |

---

## What Full Success Looks Like

```
✓ GET  /health                         → {"status": "ok"}
✓ GET  /auth/me                        → profile object
✓ POST /chat (multi-tool message)      → tools_used has 3+ entries
✓ POST /chat/stream                    → SSE events stream in real time
✓ POST /chat (session turn 2)          → APEX remembers turn 1 context
✓ POST /memory/search                  → semantic match found (Voyage AI working)
✓ Calendar create → extend → complete  → same event updated, not duplicated
✓ Habit log from one sentence          → log_habit called 3 times
✓ Expense log from one sentence        → log_expense called 3 times
✓ Routine run                          → returns steps array
✓ Supabase reminder status → "fired"   → Realtime pushes update to UI
✓ Server logs show:
    apex_starting
    supabase_connected
    scheduler_started
    apex_ready
```
