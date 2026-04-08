# APEX API Reference

Base URL: `http://localhost:8000/api/v1`

All protected endpoints require: `Authorization: Bearer <access_token>`

---

## Authentication

### POST /auth/register

Creates a new APEX user account.

**Request:**
```json
{
  "email": "aryan@example.com",
  "name": "Aryan Sharma",
  "password": "SecurePass1",
  "timezone": "Asia/Kolkata"
}
```

**Response `201`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

### POST /auth/login

**Request:**
```json
{ "email": "aryan@example.com", "password": "SecurePass1" }
```

**Response `200`:** Same as register.

**Error `401`:**
```json
{ "error": "auth_error", "message": "Invalid email or password" }
```

---

### POST /auth/refresh

Pass the **refresh token** in the Authorization header.

**Response `200`:** New access + refresh token pair.

---

### GET /auth/me

**Response `200`:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "aryan@example.com",
  "name": "Aryan Sharma",
  "timezone": "Asia/Kolkata",
  "preferences": {},
  "is_active": true,
  "created_at": "2025-01-15T09:00:00Z"
}
```

---

## Brief

### POST /brief/generate

Generates today's morning brief. Pulls from calendar, tasks, goals, memory, and PA-to-PA inbox.

**Response `200`:**
```json
{
  "date": "2025-01-15",
  "greeting": "Good morning, Aryan.",
  "narrative": "You have a dense day — 4 meetings including the 10am with Priya who tends to run late. Your most important task is the pitch deck, and it's not on your schedule yet. Rohan's APEX flagged a pending settlement.",
  "schedule_blocks": [
    {
      "start_at": "2025-01-15T10:00:00+05:30",
      "end_at": "2025-01-15T11:00:00+05:30",
      "title": "Sync with Priya",
      "type": "meeting",
      "risk": "Attendee tends to run late",
      "suggestion": "Buffer 15 mins after"
    }
  ],
  "focus_recommendation": "Block 2–4pm for the pitch deck — it's your most important Q2 item.",
  "risks": [
    {
      "description": "310 minutes of meetings today — very little focus time.",
      "severity": "high",
      "mitigation": "Consider declining the 3pm status call."
    }
  ],
  "pending_agent_items": ["financial_settle: Rohan owes ₹2400"],
  "mood_checkin_prompt": "You have a big presentation tomorrow — how are you feeling about it today?",
  "generated_at": "2025-01-15T07:30:00Z"
}
```

---

### POST /brief/mood-checkin

Records mood for adaptive prioritization.

**Request:**
```json
{ "mood": "tired", "note": "Didn't sleep well, big day ahead" }
```

**Response `204`:** No content.

**Valid moods:** `great` | `good` | `okay` | `tired` | `stressed` | `overwhelmed`

---

## Tasks

### GET /tasks

Query params: `status` (pending|in_progress|done|deferred|cancelled), `limit` (1–200), `offset`.

**Response `200`:** Array of Task objects.

### POST /tasks

**Request:**
```json
{
  "title": "Finalize pitch deck",
  "description": "Slides for Series A presentation",
  "priority": "critical",
  "due_at": "2025-01-16T09:00:00Z",
  "goal_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

**Response `201`:** Task object with `id`, `eisenhower_quadrant`, timestamps.

### GET /tasks/focus-now

**Response `200`:**
```json
{
  "task": { "id": "...", "title": "Finalize pitch deck", "priority": "critical", "...": "..." },
  "reason": "Q1 — urgent and important. Due in 18 hours.",
  "alternatives": [{ "...": "..." }, { "...": "..." }]
}
```

### POST /tasks/classify

Classifies tasks into Eisenhower quadrants using Claude + heuristic fallback.

**Request:**
```json
{ "task_ids": ["uuid1", "uuid2", "uuid3"] }
```

**Response `200`:**
```json
{ "results": { "uuid1": 1, "uuid2": 2, "uuid3": 4 } }
```

Quadrants: `1`=Urgent+Important (do now), `2`=Not urgent+Important (schedule), `3`=Urgent+Not important (delegate), `4`=Neither (eliminate).

### POST /tasks/bulk-defer

**Request:**
```json
{
  "task_ids": ["uuid1", "uuid2"],
  "defer_to": "2025-01-20T09:00:00Z"
}
```

**Response `200`:** `{ "deferred": 2 }`

---

## Goals

### POST /goals

**Request:**
```json
{
  "title": "Ship product by June",
  "category": "work",
  "target_date": "2025-06-30T00:00:00Z",
  "check_in_schedule": "weekly"
}
```

### GET /goals/{id}/progress

**Response `200`:**
```json
{
  "goal": { "...": "..." },
  "linked_tasks_total": 12,
  "linked_tasks_done": 5,
  "days_remaining": 165,
  "on_track": true,
  "weekly_actions_this_week": 3,
  "suggestion": "'Ship product by June' is on track. Keep going."
}
```

### GET /goals/weekly-review

**Response `200`:**
```json
{
  "week_label": "Week of January 13",
  "goals_reviewed": [...],
  "off_course": ["Exercise 4x a week"],
  "wins": ["3 tasks done toward 'Ship product by June'"],
  "narrative": "Solid progress on the product this week. Exercise slipped — only 1 session. Tomorrow's calendar has a 7am gap that could fix that.",
  "recommended_focus": "Exercise 4x a week"
}
```

### GET /goals/alignment-check

**Response `200`:**
```json
{
  "aligned_pct": 62.5,
  "unlinked_tasks": 6,
  "suggestion": "6 tasks aren't linked to any goal. Want me to review them?",
  "goal_gaps": []
}
```

---

## Calendar

### GET /calendar/today

**Response `200`:**
```json
{
  "date": "2025-01-15",
  "events": [...],
  "free_blocks": [
    { "start": "2025-01-15T12:00:00+05:30", "end": "2025-01-15T14:00:00+05:30" }
  ],
  "total_meeting_minutes": 180,
  "deep_work_available_minutes": 120
}
```

### POST /calendar/sync

Triggers a Google Calendar sync. Requires Google integration to be connected.

**Response `200`:**
```json
{
  "provider": "google",
  "events_synced": 8,
  "conflicts_detected": 1,
  "last_synced_at": "2025-01-15T07:30:00Z"
}
```

---

## Memory

### GET /memory

Returns all stored memories with category breakdown.

**Response `200`:**
```json
{
  "items": [
    { "id": "...", "content": "Prefers morning focus blocks", "category": "preference", "source": "conversation", "created_at": "..." },
    { "id": "...", "content": "Rohan owes money from last Friday dinner", "category": "relationship", "source": "call", "created_at": "..." }
  ],
  "total": 24,
  "categories": { "preference": 8, "relationship": 6, "fact": 5, "pattern": 3, "decision": 2 }
}
```

### POST /memory/search

Semantic search over user's memory using vector similarity.

**Request:**
```json
{ "query": "what do I know about Priya?", "limit": 5 }
```

**Response `200`:**
```json
[
  { "id": "...", "content": "Priya tends to run 10-15 mins late to meetings", "category": "relationship", "score": 0.923 },
  { "id": "...", "content": "Priya prefers decisions via Slack, not email", "category": "preference", "score": 0.871 }
]
```

### DELETE /memory

Wipes **all** memories permanently (both PostgreSQL + Qdrant). Irreversible.

**Response `200`:** `{ "deleted": 24, "message": "All 24 memories have been erased." }`

---

## Agent (PA-to-PA)

### POST /agent/propose

Initiates a negotiation with another APEX user.

**Request (scheduling):**
```json
{
  "to_user_id": "other-user-uuid",
  "proposal_type": "scheduling",
  "slots": [
    { "start": "2025-01-17T18:00:00Z", "end": "2025-01-17T19:00:00Z" },
    { "start": "2025-01-18T10:00:00Z", "end": "2025-01-18T11:00:00Z" }
  ],
  "note": "Aryan wants to catch up about the Q2 roadmap"
}
```

**Request (financial):**
```json
{
  "to_user_id": "rohan-uuid",
  "proposal_type": "financial",
  "amount": 2400,
  "currency": "INR",
  "note": "From last Friday dinner at Toit"
}
```

**Response `201`:** AgentMessage object with `status: "pending"`.

### POST /agent/respond

**Request:**
```json
{
  "message_id": "msg-uuid",
  "decision": "accept"
}
```

Or counter-propose:
```json
{
  "message_id": "msg-uuid",
  "decision": "counter",
  "counter_content": {
    "slots": [{ "start": "2025-01-19T11:00:00Z", "end": "2025-01-19T12:00:00Z" }]
  },
  "note": "The earlier slots don't work — how about Sunday?"
}
```

**Valid decisions:** `accept` | `decline` | `counter`

---

## Integrations

### GET /integrations/{provider}/auth-url

**Supported providers:** `google` | `slack` | `notion`

**Response `200`:**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&scope=...",
  "provider": "google"
}
```

Redirect the user to `auth_url`. After consent, Google redirects to `/api/v1/integrations/callback/google`.

---

## Calls

### POST /calls/start

**Response `201`:**
```json
{
  "session_id": "abc-123-uuid",
  "message": "Call session started. Connect to WS /ws/call."
}
```

### POST /calls/{session_id}/end

Ends the session, runs transcript extraction, creates tasks, stores memories.

**Response `200`:**
```json
{
  "session_id": "abc-123-uuid",
  "summary": "Discussed Q2 hiring plan with Karan. Agreed on 3 eng roles by March.",
  "decisions": ["Hire 3 engineers by March", "Meera owns JD creation"],
  "action_items": [
    { "owner": "me", "action": "Send Meera the JD template", "due_date_hint": "by EOD" }
  ],
  "follow_ups": ["Check on budget approval with finance"],
  "people_mentioned": ["Karan", "Meera"],
  "tasks_created": ["task-uuid-1"],
  "ended_at": "2025-01-15T11:30:00Z"
}
```

---

## WebSocket Protocol

### Authentication

All WS connections authenticate via query param or first message:

```
wss://api.apex.ai/api/v1/ws/brief?token=<jwt>
```

Or send as first message:
```json
{ "token": "eyJhbGci..." }
```

### WS /ws/brief — Streaming brief

Server streams text chunks then:
```json
{ "event": "done" }
```

### WS /ws/call — Live transcript

After auth, send session init:
```json
{ "session_id": "abc-123" }
```

Then stream transcript chunks:
```json
{ "text": "So I was thinking we should move the launch to..." }
```

Server confirms each:
```json
{ "event": "chunk_received", "total_chunks": 14 }
```

### WS /ws/reminders — Push nudges

Server pushes whenever a reminder fires:
```json
{
  "id": "reminder-uuid",
  "content": "You said you'd decide on the vendor by EOD. It's 6pm.",
  "trigger_type": "deadline",
  "status": "pending"
}
```

### WS /ws/agent — PA-to-PA events

Server pushes on new messages or status changes:
```json
{
  "event": "new_agent_message",
  "message_id": "msg-uuid",
  "from_user_id": "rohan-uuid",
  "message_type": "financial_settle"
}
```

---

## Error Format

All errors follow this structure:

```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "detail": { "optional": "structured context" }
}
```

| HTTP Status | Error Code | Meaning |
|---|---|---|
| 401 | `auth_error` | Missing/invalid/expired JWT |
| 403 | `forbidden` | Authenticated but not authorized |
| 404 | `not_found` | Resource doesn't exist |
| 409 | `conflict` | Duplicate resource (e.g. email) |
| 422 | `validation_error` | Request body failed Pydantic validation |
| 429 | `rate_limit_exceeded` | Too many requests |
| 502 | `integration_error` | Upstream OAuth/calendar API failed |
| 503 | `llm_error` | Anthropic API unavailable |
| 500 | `internal_error` | Unexpected server error |

---

## Rate Limits

Default: **60 requests/minute** per user. Burst: 20.

Response headers on every request:
```
X-Request-ID: <uuid>
```

On limit breach `429`:
```json
{ "error": "rate_limit_exceeded", "message": "Rate limit exceeded: 60 requests per 60s" }
```
