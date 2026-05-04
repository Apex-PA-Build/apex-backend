# APEX — Swagger Test Guide

Open `http://localhost:8000/docs` → Click **Authorize** → paste your JWT → use the JSON bodies below.

All chat tests go to: **POST /api/v1/chat**  
Streaming tests go to: **POST /api/v1/chat/stream**

---

## 1. Server Check

**GET /health** — no body needed, just hit Execute.

**GET /auth/me** — no body needed.

---

## 2. Auth — Update Profile

**PATCH /api/v1/auth/me**
```json
{
  "name": "Yathish",
  "timezone": "Asia/Kolkata"
}
```

**POST /api/v1/auth/mood**
```json
{
  "mood": "focused"
}
```

---

## 3. Tasks — Create

**POST /api/v1/tasks**
```json
{
  "title": "Prepare Q3 investor deck",
  "priority": "high",
  "energy_required": "high"
}
```

---

## 4. Goals — Create

**POST /api/v1/goals**
```json
{
  "title": "Launch APEX MVP",
  "category": "work",
  "target_date": "2025-09-01"
}
```

---

## 5. Reminders — Create

**POST /api/v1/reminders**
```json
{
  "title": "Test reminder",
  "body": "Is the reminder system working?",
  "type": "time",
  "remind_at": "2025-07-15T10:02:00Z"
}
```

**POST /api/v1/reminders/dismiss-all** — no body needed.

---

## 6. Memory — Store + Search

**POST /api/v1/memory**
```json
{
  "content": "Yathish prefers deep work before 11am, no meetings before 9am",
  "category": "preference"
}
```

**POST /api/v1/memory/search**
```json
{
  "query": "when does the user like to focus?",
  "limit": 5
}
```

> The search uses different wording from what was stored. If it returns the memory — Voyage AI + pgvector is working.

---

## 7. Session Memory — Goal Update (3 turns, same session_id)

Run these one after another with the **same session_id**. APEX must remember context without asking again.

**Turn 1 — Create goal**
```json
{
  "message": "Create a goal: Launch APEX beta by June 30",
  "session_id": "goal-test-1"
}
```

**Turn 2 — Update it (says "that goal", not repeating name)**
```json
{
  "message": "Update that goal to 40% complete",
  "session_id": "goal-test-1"
}
```

**Turn 3 — Update again using "it"**
```json
{
  "message": "I just finished the streaming feature, bump it to 60%",
  "session_id": "goal-test-1"
}
```

> **Pass:** Turns 2 and 3 must update the correct goal without APEX asking "which goal?"

---

## 8. Multi-Tool in One Message — 3 Expenses

**POST /api/v1/chat**
```json
{
  "message": "I spent 850 on groceries, 200 on an Uber, and 1200 on dinner with a client today"
}
```

> Check `tools_used` in response — should show `log_expense` called 3 times.

---

## 9. Multi-Tool in One Message — Timezone + Weather + Calendar

**POST /api/v1/chat**
```json
{
  "message": "My team in New York wants to meet at 3pm their time tomorrow. What time is that for me in Bangalore, whats the weather there, and block that meeting in my calendar"
}
```

> Check `tools_used` — should show `time_zone_convert`, `get_weather`, `create_calendar_event`.

---

## 10. Calendar — Create → Extend → Complete (3 turns, same session_id)

**Turn 1 — Create**
```json
{
  "message": "Schedule a deep work block tomorrow 10am to 12pm called Project Review",
  "session_id": "cal-test-1"
}
```

**Turn 2 — Extend (must update same event, not create new)**
```json
{
  "message": "Extend the Project Review by 30 minutes",
  "session_id": "cal-test-1"
}
```

**Turn 3 — Mark done**
```json
{
  "message": "I just finished the Project Review, mark it done",
  "session_id": "cal-test-1"
}
```

> **Pass:** Turn 2 must extend `end_at` on the existing event. A new event being created = fail.

---

## 11. Finance — Full Flow

**Step 1 — Log 3 expenses**
```json
{
  "message": "I spent 850 on groceries, 200 on Uber, and 1200 on dinner with a client today",
  "session_id": "finance-test-1"
}
```

**Step 2 — Track subscription**
```json
{
  "message": "Track my Netflix subscription at 649 rupees per month",
  "session_id": "finance-test-1"
}
```

**Step 3 — Track money owed**
```json
{
  "message": "Rahul owes me 500 rupees for the Uber last week",
  "session_id": "finance-test-1"
}
```

**Step 4 — Summary**
```json
{
  "message": "How much have I spent this week and what do people owe me?",
  "session_id": "finance-test-1"
}
```

---

## 12. Habits — Create → Log → Streaks

**Step 1 — Create 3 habits**
```json
{
  "message": "Create habits for: daily meditation (target 10 minutes), running (target 30 minutes), reading (target 20 pages)",
  "session_id": "habit-test-1"
}
```

**Step 2 — Log all three from one sentence**
```json
{
  "message": "Done for today — meditated 15 minutes, ran 5km in 35 minutes, read 22 pages",
  "session_id": "habit-test-1"
}
```

**Step 3 — Check streaks**
```json
{
  "message": "Show me my habit streaks",
  "session_id": "habit-test-1"
}
```

> **Pass:** Step 2 must call `log_habit` 3 times from one sentence.

---

## 13. Project + Notes + Lists — Linked Flow

**Step 1 — Create project**
```json
{
  "message": "Create a project called APEX Launch with deadline May 15th, status in_progress",
  "session_id": "project-test-1"
}
```

**Step 2 — Create a note**
```json
{
  "message": "Note titled APEX Launch Notes: Need to finish streaming, fix calendar bugs, and deploy before May 15",
  "session_id": "project-test-1"
}
```

**Step 3 — Create checklist**
```json
{
  "message": "Create APEX Launch checklist with: streaming endpoint, calendar fix, deploy script, user testing",
  "session_id": "project-test-1"
}
```

**Step 4 — Pull everything**
```json
{
  "message": "Show me everything about APEX Launch — project status, notes, and checklist",
  "session_id": "project-test-1"
}
```

---

## 14. Routines — Create → Run

**Step 1 — Create**
```json
{
  "message": "Create a morning routine: 1) Drink water 2) 10 min meditation 3) Review todays calendar 4) Pick top 3 tasks 5) Start deep work",
  "session_id": "routine-test-1"
}
```

**Step 2 — Run it**
```json
{
  "message": "Run my morning routine",
  "session_id": "routine-test-1"
}
```

---

## 15. Workload Check

**Step 1 — Add tasks**
```json
{
  "message": "I need to finish the API docs, review 3 PRs, call the client, prep the demo, and submit tax docs — all by tomorrow",
  "session_id": "workload-test-1"
}
```

**Step 2 — Reality check**
```json
{
  "message": "Check my workload and tell me honestly if this is doable",
  "session_id": "workload-test-1"
}
```

---

## 16. Daily Summary

**POST /api/v1/chat**
```json
{
  "message": "Give me a full daily summary — tasks, goals, calendar, habits and tell me where I should focus today"
}
```

---

## 17. Decision Support

**Compare options**
```json
{
  "message": "Help me decide: Option A - take freelance project (more money, less time), Option B - focus on APEX launch (more impact, zero income for 2 months), Option C - do both part time (balanced but risky)"
}
```

**Pros and cons**
```json
{
  "message": "Give me pros and cons of moving from Bangalore to Hyderabad for work"
}
```

**Deadline countdown**
```json
{
  "message": "How many days do I have left until my APEX launch deadline and am I on track?"
}
```

---

## 18. Health + Journal + Wins

**Step 1 — Log health**
```json
{
  "message": "Logged: slept 7.5 hours, drank 2.5 litres of water, had oats for breakfast",
  "session_id": "health-test-1"
}
```

**Step 2 — Log workout**
```json
{
  "message": "Just finished a 45 minute chest and shoulder workout",
  "session_id": "health-test-1"
}
```

**Step 3 — Journal + win**
```json
{
  "message": "Journal: Finally cracked the streaming issue after 3 hours. Worth it. Also log a win — fixed the APEX streaming bug!",
  "session_id": "health-test-1"
}
```

**Step 4 — Summary**
```json
{
  "message": "Show me my health summary and recent wins",
  "session_id": "health-test-1"
}
```

---

## 19. People / Relationships

**Step 1 — Add person note**
```json
{
  "message": "Note about Rahul: He's a senior engineer at Flipkart, we met at JSConf 2024, interested in collaborating on APEX",
  "session_id": "people-test-1"
}
```

**Step 2 — Add birthday**
```json
{
  "message": "Rahul's birthday is March 15",
  "session_id": "people-test-1"
}
```

**Step 3 — Log interaction**
```json
{
  "message": "Had coffee with Rahul today, discussed potential partnership on APEX",
  "session_id": "people-test-1"
}
```

**Step 4 — Upcoming birthdays**
```json
{
  "message": "Who has a birthday coming up in the next 30 days?",
  "session_id": "people-test-1"
}
```

---

## 20. Learning + Books

**Add book**
```json
{
  "message": "Add Deep Work by Cal Newport to my reading list",
  "session_id": "learning-test-1"
}
```

**Log a learning**
```json
{
  "message": "Just learned: HNSW index is faster for approximate vector search, IVFFlat is better for exact. Save this.",
  "session_id": "learning-test-1"
}
```

**Get reading list**
```json
{
  "message": "What books are on my reading list?",
  "session_id": "learning-test-1"
}
```

---

## 21. Utilities

**Calculate with GST**
```json
{
  "message": "What is 18% GST on 47500 rupees?"
}
```

**Timezone convert**
```json
{
  "message": "Convert 3pm New York time to Bangalore time"
}
```

**Weather**
```json
{
  "message": "Whats the weather like in Bangalore right now?"
}
```

**Draft message**
```json
{
  "message": "Draft a WhatsApp message to my client Priya saying I need 2 more days on the feature, professional but friendly tone"
}
```

**Draft email**
```json
{
  "message": "Draft an email to my manager saying I completed the streaming feature and it is ready for review"
}
```

---

## 22. Streaming — POST /api/v1/chat/stream

**Morning brief (tests multiple tools streaming live)**
```json
{
  "message": "Give me a full morning brief — weather in Bangalore, todays schedule, top goal progress, and what to focus on first"
}
```

> In Swagger you will see raw SSE text like:
> ```
> data: {"type":"status","message":"Checking your calendar..."}
> data: {"type":"text","content":"Good morning!..."}
> data: {"type":"done"}
> ```

---

## 23. Error Handling — Should Never Crash

These must return a helpful message, not a 500 error.

**Non-existent list**
```json
{
  "message": "Show me my unicorn list"
}
```

**Extend event that does not exist**
```json
{
  "message": "Extend my dentist appointment by 1 hour"
}
```

**Bad math (injection attempt — should be blocked)**
```json
{
  "message": "Calculate: drop table users"
}
```

**Vague request — APEX should ask for clarification**
```json
{
  "message": "Update it"
}
```

---

## Quick Checklist

| What to check | Where | Pass condition |
|---|---|---|
| Server running | GET /health | `{"status": "ok"}` |
| Auth working | GET /auth/me | Returns profile |
| Tools firing | POST /chat (any action) | `tools_used` array is not empty |
| Multi-tool | Test 8 (3 expenses) | `log_expense` appears 3 times in `tools_used` |
| Session memory | Test 7 (3 turns) | Turn 2 and 3 update correctly |
| Calendar extend | Test 10 | No duplicate event created |
| Streaming | POST /chat/stream | SSE lines appear, ends with `done` |
| New tables exist | Test 11 (finance) | No DB error — means schema_v2.sql was run |
| Realtime working | Create reminder, wait 30s | Status changes to `fired` in Supabase Table Editor |
