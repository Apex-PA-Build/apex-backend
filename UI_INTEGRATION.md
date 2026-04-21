# APEX — UI Integration Guide (Next.js)

Base URL: `http://localhost:8000/api/v1`
WebSocket Base: `ws://localhost:8000`

All endpoints except login, register, docs, and OAuth callbacks require:
```
Authorization: Bearer <access_token>
```

---

## Token Management

### What you get after login/register
```json
{
  "access_token": "eyJhbGci...",
  "expires_in": 3600,
  "user_id": "uuid-string",
  "email": "user@example.com"
}
```

- `access_token` — Supabase JWT. Valid for **1 hour** (`expires_in: 3600` seconds).
- Store it in `localStorage` or a secure httpOnly cookie.
- When it expires, the API returns `401 {"detail": "Token expired"}` — re-login to get a new token.
- There is no refresh token endpoint on the backend — just call `/auth/login` again with stored credentials or prompt re-login.

---

## 1. Auth

### Register
`POST /auth/register`

**When to use:** New user signup screen.

**Payload:**
```json
{
  "email": "user@example.com",
  "password": "minlength8",
  "name": "Yathish"
}
```

**Response:** `200`
```json
{
  "access_token": "eyJhbGci...",
  "expires_in": 3600,
  "user_id": "3f2a1b...",
  "email": "user@example.com"
}
```

**Errors:**
- `400 {"detail": "User already registered"}` — email already exists
- `400 {"detail": "User created but no session returned..."}` — email confirmation is on in Supabase (disable it)

---

### Login
`POST /auth/login`

**When to use:** Login screen. Also call this to refresh the token when it expires.

**Payload:**
```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Response:** Same as register.

**Errors:**
- `401 {"detail": "Invalid email or password"}`

---

### Get Profile
`GET /auth/me`

**When to use:** On app load after login. Use to get `user_id` for WebSocket connection and display user name.

**Response:**
```json
{
  "id": "3f2a1b...",
  "name": "Yathish",
  "timezone": "Asia/Kolkata",
  "mood_today": null,
  "preferences": {},
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

`mood_today` values: `"energetic"` | `"focused"` | `"good"` | `"tired"` | `"stressed"` | `null`

---

### Update Profile
`PATCH /auth/me`

**When to use:** Settings screen — update name, timezone.

**Payload (all optional):**
```json
{
  "name": "Yathish",
  "timezone": "Asia/Kolkata",
  "preferences": {}
}
```

**Response:** Full profile object (same as GET /auth/me).

---

### Mood Check-in
`POST /auth/mood`

**When to use:** Morning check-in screen or when user sets mood.

**Payload:**
```json
{
  "mood": "focused"
}
```

Allowed values: `"energetic"` | `"focused"` | `"good"` | `"tired"` | `"stressed"`

**Response:**
```json
{
  "message": "Got it — you're feeling focused. I'll factor that into your day."
}
```

---

## 2. Chat

### Send Message
`POST /chat`

**When to use:** Main chat screen. APEX processes message, runs tools internally, and returns final reply.

**Payload:**
```json
{
  "message": "Add a task to call mom tomorrow",
  "session_id": "main"
}
```

- `session_id` — arbitrary string you choose. Use the same string to maintain conversation context (APEX remembers prior turns within the session). Use a new string for a fresh conversation.

**Response:**
```json
{
  "reply": "Done — added 'Call mom' to your tasks for tomorrow.",
  "tools_used": ["create_task"]
}
```

- `tools_used` — list of tools APEX invoked internally (useful for showing activity indicators).

**Possible tools_used values:**
`create_task` | `get_tasks` | `update_task` | `search_memories` | `store_memory` | `get_today_schedule` | `create_calendar_event` | `get_goals` | `create_goal` | `create_reminder` | `send_agent_message`

---

## 3. WebSockets

Two separate WebSocket endpoints. Connect both on app load.

### `/ws/chat` — Streaming Chat

**When to use:** Chat screen where you want text to stream word-by-word instead of waiting for the full reply.

**Protocol:**
```
1. Connect to: ws://localhost:8000/ws/chat
2. Send:  {"token": "<access_token>"}
3. Receive: {"type": "connected", "user_id": "..."}
4. Send:  {"message": "your message here"}
5. Receive stream of events (see below)
6. Repeat from step 4
```

**Event types you receive:**
```json
{"type": "chunk", "content": "Done —"}
{"type": "chunk", "content": " added"}
{"type": "tool_status", "name": "create_task", "message": "Adding that to your tasks..."}
{"type": "tool_result", "name": "create_task", "result": {...}}
{"type": "done"}
{"type": "error", "message": "Something went wrong"}
```

**How to use in UI:**
- On `chunk` → append `content` to current chat bubble
- On `tool_status` → show a small inline status below the bubble ("Adding that to your tasks...")
- On `done` → finalize the bubble, enable input again

---

### `/ws/events` — Server-Push Notifications

**When to use:** Connect once on app load. Receives reminders and agent messages pushed from server even when user is not actively chatting.

**Protocol:**
```
1. Connect to: ws://localhost:8000/ws/events
2. Send:  {"token": "<access_token>"}
3. Receive: {"type": "connected", "user_id": "..."}
4. Send ping every 30s: {"type": "ping"}
5. Receive pong: {"type": "pong"}
6. Server pushes events anytime
```

**Event types you receive:**
```json
{
  "event": "reminder_fired",
  "reminder": {
    "id": "uuid",
    "title": "Call CA about taxes",
    "body": "Before Friday deadline",
    "type": "time",
    "remind_at": "2025-01-20T10:00:00Z",
    "status": "fired"
  }
}
```

**Auto-reconnect:** If WebSocket closes, reconnect after 3 seconds.

---

## 4. Morning Brief

### Generate Brief
`POST /brief/generate`

**When to use:** When user opens the app in the morning (dashboard load). Cache the result for the session — don't regenerate on every navigation.

**No payload needed.**

**Response:**
```json
{
  "greeting": "Good morning Yathish — you've got a packed day but the Memory API sprint ends today.",
  "narrative": "Your morning is meeting-heavy with 3 back-to-back calls until noon...",
  "focus_recommendation": "Block 2-4pm for the Memory API — that's your only deep work window today.",
  "risks": [
    "Overlap between 10am standup and 10:15am client call",
    "CA tax deadline is Friday — no slot booked yet"
  ],
  "quick_wins": [
    "Reply to Ravi's Slack (2 min)",
    "Mark yesterday's PR task as done"
  ],
  "mood_prompt": "You've got the demo Friday — how are you feeling about where the Memory API is right now?"
}
```

---

## 5. Tasks

### List Tasks
`GET /tasks?status=pending&limit=50&offset=0`

**When to use:** Tasks screen, dashboard pending task count.

Query params (all optional):
- `status`: `"pending"` | `"in_progress"` | `"done"` | `"deferred"` | `"cancelled"`
- `limit`: max 200, default 50
- `offset`: for pagination

**Response:** Array of task objects:
```json
[
  {
    "id": "uuid",
    "title": "Fix Memory API",
    "description": "60% complete, blocking demo",
    "status": "in_progress",
    "priority": "critical",
    "eisenhower_quadrant": 1,
    "energy_required": "high",
    "due_at": "2025-01-24T17:00:00Z",
    "goal_id": null,
    "created_at": "2025-01-19T09:00:00Z",
    "updated_at": "2025-01-19T09:00:00Z"
  }
]
```

- `priority`: `"low"` | `"medium"` | `"high"` | `"critical"`
- `status`: `"pending"` | `"in_progress"` | `"done"` | `"deferred"` | `"cancelled"`
- `eisenhower_quadrant`: `1` (urgent+important) | `2` (not urgent+important) | `3` (urgent+not important) | `4` (neither) | `null`
- `energy_required`: `"low"` | `"medium"` | `"high"` | `null`

---

### Create Task
`POST /tasks`

**When to use:** Manual task creation form. Note: APEX also creates tasks automatically via chat.

**Payload:**
```json
{
  "title": "Fix mobile crash",
  "description": "Crashes on iOS 17 during onboarding",
  "priority": "high",
  "due_at": "2025-01-24T17:00:00Z",
  "goal_id": null,
  "energy_required": "high"
}
```

Only `title` is required. All others optional.

**Response:** Single task object (same shape as list items). Status `201`.

---

### Update Task
`PATCH /tasks/{task_id}`

**When to use:** Checkbox to mark done, drag-and-drop status change, edit task.

**Payload (all optional, send only what changed):**
```json
{
  "status": "done",
  "priority": "critical",
  "title": "Updated title",
  "due_at": "2025-01-25T17:00:00Z"
}
```

**Response:** Updated task object.

---

### Delete Task
`DELETE /tasks/{task_id}`

**Response:**
```json
{"message": "Task deleted"}
```

---

### Get Focus Task
`GET /tasks/focus?energy=high`

**When to use:** "What should I work on right now?" feature. Returns single best task.

Query: `energy` optional — `"low"` | `"medium"` | `"high"`

**Response:** Single task object or `null`.

---

### Brain Dump
`POST /tasks/brain-dump`

**When to use:** Quick capture screen where user dumps a wall of text and APEX extracts + creates tasks.

**Payload:**
```json
{
  "text": "need to fix the login bug, call ravi about funding, review PR from sarah, pay rent"
}
```

**Response:** Array of created task objects.

---

### Replan Day
`POST /tasks/replan`

**When to use:** "Something came up, help me replan" button.

**Payload:**
```json
{
  "reason": "Got a customer demo request for Wednesday",
  "available_minutes": 240
}
```

**Response:** Array of reprioritized task objects.

---

## 6. Goals

### List Goals
`GET /goals?status=active`

Query: `status` optional — `"active"` | `"paused"` | `"completed"` | `"abandoned"`

**Response:**
```json
[
  {
    "id": "uuid",
    "title": "Launch APEX v1",
    "description": "Ship the MVP by end of month",
    "category": "work",
    "status": "active",
    "progress_pct": 60,
    "target_date": "2025-01-31",
    "check_in_schedule": "weekly",
    "created_at": "...",
    "updated_at": "..."
  }
]
```

- `category`: `"work"` | `"health"` | `"finance"` | `"personal"` | `"learning"`
- `check_in_schedule`: `"daily"` | `"weekly"` | `"monthly"`

---

### Create Goal
`POST /goals`

**Payload:**
```json
{
  "title": "Ship APEX MVP",
  "category": "work",
  "target_date": "2025-01-31",
  "description": "Full product with UI connected"
}
```

Only `title` and `category` required.

**Response:** Single goal object. Status `201`.

---

### Update Goal
`PATCH /goals/{goal_id}`

**Payload (all optional):**
```json
{
  "status": "completed",
  "progress_pct": 100,
  "title": "New title"
}
```

---

### Weekly Review
`GET /goals/review`

**When to use:** Weekly review screen. AI-generated honest reflection.

**Response:**
```json
{
  "narrative": "Solid week overall — you shipped the embedding migration but the mobile crash is still open...",
  "on_track": ["Ship APEX MVP"],
  "behind": ["Get fit by March"],
  "recommendations": [
    "Block Monday morning for the mobile crash fix",
    "Schedule the CA tax call this week — it's overdue"
  ],
  "wins": ["Completed Memory API", "Connected Google Calendar"]
}
```

---

### Alignment Check
`GET /goals/alignment`

**When to use:** Show user how their current tasks align to their stated goals.

**Response:**
```json
{
  "aligned_tasks": [...],
  "unaligned_tasks": [...],
  "missing_coverage": ["health goal has no active tasks"]
}
```

---

## 7. Calendar

### Today's Schedule
`GET /calendar/today`

**When to use:** Dashboard calendar view, morning brief context, anywhere showing today.

**Response:**
```json
{
  "events": [
    {
      "id": "uuid",
      "title": "Standup",
      "description": null,
      "location": null,
      "start_at": "2025-01-20T09:00:00Z",
      "end_at": "2025-01-20T09:30:00Z",
      "attendees": ["ravi@example.com"],
      "source": "google",
      "is_cancelled": false
    }
  ],
  "free_blocks": [
    {
      "start": "2025-01-20T14:00:00Z",
      "end": "2025-01-20T16:00:00Z",
      "duration_minutes": 120
    }
  ],
  "total_meeting_minutes": 90,
  "deep_work_available": true,
  "conflicts": []
}
```

---

### Create Calendar Event
`POST /calendar/events`

**When to use:** Manual event creation. Also pushes to Google Calendar if connected.

**Payload:**
```json
{
  "title": "Customer Demo",
  "start_at": "2025-01-22T14:00:00Z",
  "end_at": "2025-01-22T15:00:00Z",
  "description": "Demo of Memory API to potential customer",
  "location": "Zoom",
  "attendees": ["customer@company.com"]
}
```

`title`, `start_at`, `end_at` required. Others optional.

**Response:** Created event object. Status `201`.

---

### Sync Google Calendar
`POST /calendar/sync/google`

**When to use:** "Sync" button in calendar screen. Pulls next 30 days of events from Google into Supabase.

**Response:**
```json
{
  "synced": 14,
  "provider": "google"
}
```

**Error if not connected:**
```json
{"detail": "Google Calendar not connected. Connect it in Settings."}
```

---

## 8. Reminders

### List Reminders
`GET /reminders?status=pending`

Query: `status` optional — `"pending"` | `"snoozed"` | `"dismissed"` | `"fired"`

**Response:**
```json
[
  {
    "id": "uuid",
    "title": "CA Tax Call",
    "body": "Must do before Friday deadline",
    "type": "deadline",
    "remind_at": "2025-01-21T09:00:00Z",
    "status": "pending",
    "snoozed_until": null,
    "created_at": "..."
  }
]
```

- `type`: `"time"` | `"deadline"` | `"relationship"`

---

### Create Reminder
`POST /reminders`

**Payload:**
```json
{
  "title": "Call CA about taxes",
  "body": "Before Friday deadline",
  "remind_at": "2025-01-21T09:00:00Z",
  "type": "deadline"
}
```

`title` and `remind_at` required.

**Response:** Created reminder object. Status `201`.

---

### Snooze Reminder
`POST /reminders/{reminder_id}/snooze`

**Payload:**
```json
{
  "minutes": 30
}
```

**Response:** Updated reminder object with new `remind_at`.

---

### Dismiss Reminder
`POST /reminders/{reminder_id}/dismiss`

**Response:**
```json
{"message": "Reminder dismissed"}
```

---

## 9. Memory

### List Memories
`GET /memory?category=preference&limit=50`

**When to use:** Settings screen "What APEX knows about you".

Query: `category` optional — `"preference"` | `"relationship"` | `"pattern"` | `"fact"` | `"decision"` | `"commitment"`

**Response:**
```json
[
  {
    "id": "uuid",
    "content": "Prefers deep work blocks in the afternoon",
    "category": "preference",
    "source": "conversation",
    "created_at": "..."
  }
]
```

---

### Search Memory
`POST /memory/search`

**When to use:** Debug/search screen, or to test if memory is working.

**Payload:**
```json
{
  "query": "what does the user prefer about work hours",
  "limit": 8
}
```

**Response:**
```json
[
  {
    "id": "uuid",
    "content": "Prefers deep work in afternoon 2-4pm",
    "category": "preference",
    "source": "conversation",
    "similarity": 0.87,
    "created_at": "..."
  }
]
```

---

### Add Memory Manually
`POST /memory`

**When to use:** "Tell APEX something" screen where user explicitly teaches APEX a fact.

**Payload:**
```json
{
  "content": "I prefer async communication over meetings",
  "category": "preference"
}
```

**Response:** Created memory object. Status `201`.

---

### Delete Memory
`DELETE /memory/{memory_id}`

**Response:**
```json
{"message": "Memory deleted"}
```

---

## 10. Integrations (Google Calendar)

### Get OAuth URL
`GET /integrations/google/auth-url`

**When to use:** Settings screen "Connect Google Calendar" button. Open the returned URL in a new tab.

**Response:**
```json
{
  "url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "provider": "google"
}
```

After user grants permission, Google redirects to:
`http://localhost:8000/api/v1/integrations/callback/google`
which then redirects to:
`http://localhost:3000/settings?connected=google`

Detect `?connected=google` in your settings page and show success state.

---

### List Connected Integrations
`GET /integrations`

**Response:**
```json
[
  {
    "provider": "google",
    "is_active": true,
    "scope": "https://www.googleapis.com/auth/calendar ...",
    "external_user_id": null,
    "expires_at": "2025-01-20T11:00:00Z",
    "created_at": "..."
  }
]
```

---

### Disconnect Integration
`DELETE /integrations/google`

**Response:**
```json
{"message": "google disconnected"}
```

---

## 11. Calls (Call Recording Feature)

### Start Call Session
`POST /calls/start?title=Customer+Demo+Call`

**Response:** Status `201`
```json
{
  "session_id": "uuid",
  "started_at": "2025-01-20T14:00:00Z"
}
```

---

### Add Transcript Chunk
`POST /calls/{session_id}/transcript`

**When to use:** Send speech-to-text output in real time during call.

**Payload:**
```json
{
  "text": "So the demo will cover memory search and task creation..."
}
```

**Response:**
```json
{"status": "ok"}
```

---

### End Call + Get Summary
`POST /calls/{session_id}/end`

**When to use:** When call ends. APEX analyses full transcript and returns structured summary.

**Response:**
```json
{
  "session_id": "uuid",
  "summary": "Customer confirmed interest in the Memory API. Demo scheduled for next week.",
  "action_items": [
    {
      "title": "Send product one-pager",
      "owner": "me",
      "due_date": "2025-01-22"
    }
  ],
  "decisions": ["Move forward with paid pilot if demo goes well"],
  "people_mentioned": ["Arjun (customer)", "Ravi"],
  "follow_ups": ["Send pricing deck", "Book follow-up call"],
  "key_dates": ["Demo next Wednesday", "Decision by Feb 1"],
  "tasks_created": 2
}
```

---

## Error Handling

All errors follow this shape:
```json
{"detail": "Human readable message"}
```

| Status | Meaning | What to do |
|--------|---------|------------|
| `401` | Token missing or expired | Re-login |
| `403` | Not authorized | Check user permissions |
| `404` | Resource not found | Show not found state |
| `422` | Invalid payload | Fix request body |
| `429` | Rate limited (60 req/min) | Show "slow down" message |
| `500` | Server error | Show generic error, retry |

---

## App Load Sequence

```
1. Check localStorage for apex_token
2. If no token → redirect to /login
3. If token → GET /auth/me
   - If 401 → token expired → redirect to /login
   - If success → store profile, get user_id
4. Connect ws://localhost:8000/ws/events (send token, keep alive with ping)
5. POST /brief/generate → show on dashboard
6. GET /calendar/today → show schedule
7. GET /tasks?status=pending → show task list
8. Ready
```

---

## Session ID Strategy for Chat

```
"main"          → default persistent conversation (remembers last 10 exchanges)
"brief-session" → separate context for brief interactions
"onboarding"    → separate for first-time setup
```

Use the same `session_id` string across messages to maintain context. Use a different string to start fresh. APEX keeps last 20 messages (10 exchanges) per session in memory.
