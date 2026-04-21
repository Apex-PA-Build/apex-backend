# APEX Backend — API Reference

**Base URL:** `http://localhost:8000/api/v1`  
**Swagger UI:** `http://localhost:8000/docs`  
**Auth:** All endpoints (except `/auth/*`, `/docs`, `/openapi.json`, `/ws/*` initial handshake) require `Authorization: Bearer <supabase_jwt>`.

---

## Table of Contents

1. [Authentication & Profile](#1-authentication--profile)
2. [Tasks](#2-tasks)
3. [Goals](#3-goals)
4. [Calendar](#4-calendar)
5. [Memory](#5-memory)
6. [Daily Brief](#6-daily-brief)
7. [Chat (AI Brain)](#7-chat-ai-brain)
8. [Agent Messaging](#8-agent-messaging)
9. [Call Intelligence](#9-call-intelligence)
10. [Reminders](#10-reminders)
11. [Integrations](#11-integrations)
12. [WebSockets](#12-websockets)
13. [Error Reference](#13-error-reference)
14. [Architecture Overview](#14-architecture-overview)

---

## 1. Authentication & Profile

**Prefix:** `/api/v1/auth`

Authentication is handled entirely by **Supabase Auth**. You do not call sign-in/sign-up through this backend — use the Supabase client SDK in your frontend. Once you have a Supabase JWT, pass it in the `Authorization: Bearer` header on every request.

These endpoints manage the user's profile stored in the `profiles` table.

---

### `GET /auth/me`
**What it does:** Returns the authenticated user's profile. If no profile exists yet (first login), it auto-creates one.

**When to use:** On app load to populate the user's name, timezone, mood, and preferences.

**Request:**
```
GET /api/v1/auth/me
Authorization: Bearer <jwt>
```

**Response `200`:**
```json
{
  "id": "uuid",
  "name": "Alex Johnson",
  "timezone": "UTC",
  "mood_today": "energetic",
  "preferences": {},
  "created_at": "2025-01-15T09:00:00Z"
}
```

---

### `PATCH /auth/me`
**What it does:** Updates the user's profile fields. Only provided fields are updated (PATCH semantics).

**When to use:** When the user changes their name, timezone, or preferences in settings.

**Request body:**
```json
{
  "name": "Alex Johnson",
  "timezone": "America/New_York",
  "preferences": { "theme": "dark", "work_start": "09:00" }
}
```

**Response `200`:** Same as `GET /auth/me`.

---

### `POST /auth/mood`
**What it does:** Logs the user's current mood for today, persisted in the `profiles` table. Used by the AI to adjust tone, task recommendations, and energy filtering.

**When to use:** Morning mood check-in, or whenever the user manually reports how they feel.

**Mood values:** `energetic` | `focused` | `good` | `tired` | `stressed`

**Request body:**
```json
{ "mood": "focused" }
```

**Response `200`:**
```json
{ "message": "Mood set to 'focused'. Adjusting your day accordingly." }
```

---

## 2. Tasks

**Prefix:** `/api/v1/tasks`

Core task management. Tasks have a priority, optional due date, energy level, and are automatically classified into an **Eisenhower quadrant** (1=urgent+important, 2=not urgent+important, 3=urgent+not important, 4=neither) by Claude Haiku in the background immediately after creation.

**Status values:** `pending` | `in_progress` | `done` | `deferred` | `cancelled`  
**Priority values:** `low` | `medium` | `high` | `critical`  
**Energy values:** `low` | `medium` | `high`

---

### `GET /tasks`
**What it does:** Lists all tasks for the user, newest first.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | — | Filter by status |
| `limit` | int | 50 | Max results (≤200) |
| `offset` | int | 0 | Pagination offset |

**Example:**
```
GET /api/v1/tasks?status=pending&limit=20
```

**Response `200`:** Array of task objects.

---

### `POST /tasks`
**What it does:** Creates a task. Immediately triggers a background Claude Haiku call to classify the task into an Eisenhower quadrant and write it back.

**When to use:** Any time the user explicitly creates a task.

**Request body:**
```json
{
  "title": "Prepare Q3 investor deck",
  "description": "Cover financial summary, product roadmap, team updates",
  "priority": "high",
  "energy_required": "high",
  "due_at": "2025-07-15T17:00:00Z",
  "goal_id": "uuid-of-linked-goal",
  "parent_task_id": null
}
```
Only `title` is required.

**Response `201`:** Full task object with `eisenhower_quadrant` populated shortly after (async).

---

### `GET /tasks/{task_id}`
**What it does:** Fetches a single task. Returns 403 if the task belongs to a different user.

---

### `PATCH /tasks/{task_id}`
**What it does:** Updates any task field. Only supplied fields are changed.

**Request body:**
```json
{
  "status": "done",
  "priority": "critical"
}
```

---

### `DELETE /tasks/{task_id}`
**What it does:** Permanently deletes the task.

**Response `200`:** `{ "message": "Task deleted" }`

---

### `GET /tasks/focus`
**What it does:** Returns the **single most important task** to work on right now, scored by priority + Eisenhower quadrant + urgency (hours until due). This is the "what should I do next?" endpoint.

**When to use:** The main focus panel in the UI, or when the user asks "what should I work on?"

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `energy` | string | Filter to tasks matching `low`/`medium`/`high` energy. Falls back to all tasks if none match. |

**Example:**
```
GET /api/v1/tasks/focus?energy=low
```

**Response `200`:** Single task object, or `null` if no tasks exist.

**Scoring algorithm:**
```
score = priority_score + eisenhower_score + urgency_score
urgency: 3 if due < 4h, 2 if due < 24h, 1 otherwise
```

---

### `POST /tasks/brain-dump`
**What it does:** Accepts free-form text and uses Claude to parse it into up to **10 discrete tasks**, each with a title, priority, and description. All parsed tasks are immediately created.

**When to use:** When the user wants to offload everything from their head at once — "brain dump mode."

**Request body:**
```json
{
  "text": "I need to call Sarah about the contract, finish the slide deck before Friday, renew my gym membership, review John's PR, book flights for the Austin conference, and email the vendor about the delay."
}
```

**Response `201`:** Array of created task objects (up to 10).

**How it works:**
1. Sends text to Claude Sonnet with structured JSON extraction prompt.
2. Parses each item's title, priority, and description.
3. Calls `create_task` for each one (which also triggers Eisenhower classification).

---

### `POST /tasks/replan`
**What it does:** Given a disruption (e.g., "I have a migraine", "meeting ran 3 hours late"), compassionately reschedules today's pending tasks. Defers low-priority tasks and keeps the must-dos.

**When to use:** When something unexpected happens and the user needs to reset their day.

**Request body:**
```json
{
  "reason": "I'm not feeling well, have a headache",
  "available_minutes": 90
}
```

**Response `200`:** Array of tasks that remain scheduled for today (deferred tasks are updated to `status: deferred`).

**How it works:**
1. Fetches all pending tasks.
2. Sends to Claude Sonnet with context about available time.
3. Claude returns `keep_today` and `defer` arrays.
4. Deferred tasks are updated in the DB.
5. Returns the remaining tasks.

---

## 3. Goals

**Prefix:** `/api/v1/goals`

Long-term goals that tasks can be linked to. Each goal tracks progress percentage. The AI can check alignment between daily tasks and goals.

**Category values:** `work` | `health` | `finance` | `personal` | `learning`  
**Status values:** `active` | `completed` | `abandoned`  
**Check-in schedule:** `daily` | `weekly` | `monthly`

---

### `GET /goals`
**What it does:** Lists all goals.

**Query params:** `status` (optional filter)

---

### `POST /goals`
**What it does:** Creates a new goal.

**Request body:**
```json
{
  "title": "Launch APEX MVP",
  "description": "Ship the first version with core features",
  "category": "work",
  "target_date": "2025-09-01",
  "check_in_schedule": "weekly"
}
```

**Response `201`:** Full goal object with `progress_pct: 0`.

---

### `GET /goals/{goal_id}`
**What it does:** Fetches a single goal.

---

### `PATCH /goals/{goal_id}`
**What it does:** Updates goal fields.

---

### `DELETE /goals/{goal_id}`
**What it does:** Marks goal as `abandoned` (soft delete).

---

### `POST /goals/{goal_id}/recalculate`
**What it does:** Recalculates the goal's `progress_pct` based on how many linked tasks are completed.

**When to use:** After bulk task updates, or on a weekly review.

**Formula:** `progress_pct = (done_tasks / total_linked_tasks) * 100`

**Response `200`:**
```json
{ "goal_id": "uuid", "progress_pct": 42 }
```

---

### `GET /goals/review`
**What it does:** Generates a **weekly review** using Claude. Reviews progress across all active goals, celebrates wins, surfaces blockers, and suggests next actions.

**When to use:** Weekly retrospective feature in the UI.

**Response `200`:** AI-generated review object (structure depends on LLM output).

---

### `GET /goals/alignment`
**What it does:** Checks whether today's pending tasks **actually map to any active goals**. Surfaces misalignment — e.g., you have 20 tasks but none connect to your stated goals.

**When to use:** As a periodic reality check. Great for the morning brief or weekly review UI.

---

## 4. Calendar

**Prefix:** `/api/v1/calendar`

Manages calendar events and computes schedule intelligence (free blocks, conflict detection, deep work windows).

---

### `GET /calendar/today`
**What it does:** Returns today's full schedule with computed intelligence.

**When to use:** Morning brief, daily view, or any "what's my day look like?" query.

**Response `200`:**
```json
{
  "events": [
    {
      "id": "uuid",
      "title": "Team standup",
      "start_at": "2025-07-15T09:00:00Z",
      "end_at": "2025-07-15T09:30:00Z",
      "location": null,
      "attendees": ["sarah@co.com"],
      "source": "google",
      "buffer_before": 5,
      "is_cancelled": false
    }
  ],
  "free_blocks": [
    {
      "start_at": "2025-07-15T09:30:00Z",
      "end_at": "2025-07-15T11:00:00Z",
      "duration_minutes": 90
    }
  ],
  "total_meeting_minutes": 90,
  "deep_work_available": true,
  "conflicts": []
}
```

**How it works:** Queries today's events from the DB, sorts by start time, computes gaps (free blocks ≥30 min), detects overlaps, and flags whether ≥2 hours of unbroken time exists for deep work.

---

### `POST /calendar/events`
**What it does:** Manually creates a calendar event.

**Request body:**
```json
{
  "title": "1:1 with Sarah",
  "description": "Quarterly check-in",
  "location": "Zoom",
  "start_at": "2025-07-15T14:00:00Z",
  "end_at": "2025-07-15T14:30:00Z",
  "attendees": ["sarah@company.com"]
}
```

**Response `201`:** Full event object.

---

### `POST /calendar/sync/google`
**What it does:** Syncs events from Google Calendar for the current user. Requires the Google integration to be connected first (see [Integrations](#11-integrations)).

**When to use:** On login, on demand, or on a background schedule.

**Response `200`:** Summary of synced events.

---

## 5. Memory

**Prefix:** `/api/v1/memory`

APEX's long-term semantic memory system. Memories are stored as text + a 512-dimensional Voyage AI embedding in Supabase pgvector. Claude automatically extracts and stores memories from conversations. Users can also manually store and search memories.

**Category values:** `preference` | `relationship` | `pattern` | `fact` | `decision` | `commitment`

---

### `GET /memory`
**What it does:** Lists stored memories, optionally filtered by category.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `category` | string | — | Filter by category |
| `limit` | int | 50 | Max results (≤200) |

---

### `POST /memory`
**What it does:** Manually stores a memory with a category. The content is embedded using Voyage AI and stored in pgvector.

**When to use:** When the user explicitly tells APEX something to remember ("Remember I prefer morning meetings").

**Request body:**
```json
{
  "content": "Prefers deep work in the morning before 11am",
  "category": "preference"
}
```

**Response `201`:** Memory object with ID.

---

### `POST /memory/search`
**What it does:** Performs **semantic similarity search** over stored memories using pgvector cosine distance. Returns the most contextually relevant memories for a query.

**When to use:** Used internally by the AI brain before each chat response. Can also be used by the UI to show "what does APEX remember about X?"

**Request body:**
```json
{
  "query": "how does the user like to structure their mornings?",
  "limit": 5
}
```

**Response `200`:**
```json
[
  {
    "id": "uuid",
    "content": "Prefers deep work in the morning before 11am",
    "category": "preference",
    "source": "user_explicit",
    "similarity": 0.94,
    "created_at": "2025-07-01T08:00:00Z"
  }
]
```

**How it works:**
1. Embeds the query text using Voyage AI (`voyage-3-lite`, 512 dims).
2. Calls the `match_memories` RPC function in Supabase.
3. pgvector returns memories ordered by cosine similarity.

---

### `DELETE /memory/{memory_id}`
**What it does:** Permanently deletes a stored memory.

---

## 6. Daily Brief

**Prefix:** `/api/v1/brief`

The morning intelligence report — APEX's flagship feature. A personalized, context-aware briefing that synthesizes tasks, calendar, goals, and memories into a narrative.

---

### `POST /brief/generate`
**What it does:** Generates a full daily brief using Claude Opus. Synthesizes today's calendar events, pending high-priority tasks, active goals, and recent memories into a narrative briefing with focus recommendations.

**When to use:** Every morning on app load, or when the user asks "What's my day look like?"

**How it works:**
1. Fetches today's schedule (calendar events + free blocks).
2. Fetches top pending tasks (priority: critical/high).
3. Fetches active goals.
4. Searches memories for relevant context.
5. Sends all of this to Claude Opus with a structured prompt.
6. Returns structured brief.

**Response `200`:**
```json
{
  "greeting": "Good morning, Alex. You've got a focused day ahead.",
  "narrative": "You have 3 meetings totalling 2 hours, leaving a solid 3-hour deep work block from 10am–1pm. Your top priority — the investor deck — is due Friday, making today the ideal day to make serious progress on it.",
  "focus_recommendation": "Block 10am–1pm for the investor deck. Everything else can wait.",
  "risks": [
    "The 2pm call has no prep time blocked",
    "3 tasks are past their due date"
  ],
  "quick_wins": [
    "Renew gym membership (5 min)",
    "Reply to vendor email (10 min)"
  ],
  "mood_prompt": "How are you feeling this morning? Your energy level will help me prioritize."
}
```

---

### `POST /brief/mood`
**What it does:** Identical to `POST /auth/mood` — logs today's mood. Duplicated here for convenience so the mood check-in can live in the brief flow.

**Request body:** `{ "mood": "tired" }`

---

## 7. Chat (AI Brain)

**Prefix:** `/api/v1/chat`

The core conversational AI interface. Claude acts as a personal chief-of-staff with access to 11 tools covering tasks, calendar, memory, goals, reminders, and agent messaging. The AI maintains context via semantic memory retrieval.

**Available Claude tools:** `create_task`, `get_tasks`, `update_task`, `search_memories`, `store_memory`, `get_today_schedule`, `create_calendar_event`, `get_goals`, `create_goal`, `create_reminder`, `send_agent_message`

---

### `POST /chat`
**What it does:** Sends a message to APEX and receives a complete response. Runs a full **agentic loop** — Claude may call multiple tools internally (up to 5 rounds) before returning the final answer.

**When to use:** Simple one-off queries, automated flows, testing. For real-time streaming responses use the WebSocket endpoint.

**Request body:**
```json
{
  "message": "Schedule a 30-minute deep work block tomorrow morning for the investor deck and remind me to prep tonight at 9pm"
}
```

**Response `200`:**
```json
{
  "reply": "Done! I've blocked 9:00–9:30am tomorrow for the investor deck and set a reminder for tonight at 9pm to help you prep. Want me to also move any conflicting tasks?",
  "tools_used": ["create_calendar_event", "create_reminder"]
}
```

**How it works:**
1. Retrieves relevant memories via semantic search.
2. Calls Claude Sonnet with the full system prompt + user message + tool definitions.
3. Claude decides which tools to call.
4. Backend executes each tool call and feeds results back.
5. Continues up to 5 rounds until Claude returns a final text response.
6. Extracts new facts from the conversation and stores them as memories (async).

---

## 8. Agent Messaging

**Prefix:** `/api/v1/agent`

PA-to-PA (Personal Assistant to Personal Assistant) messaging. Allows APEX agents of different users to negotiate on behalf of their users — e.g., scheduling meetings, settling shared expenses, sending follow-up nudges.

**Message types:** `scheduling_request` | `financial_settle` | `follow_up_nudge`  
**Status values:** `pending` | `accepted` | `declined` | `negotiating`

---

### `GET /agent`
**What it does:** Retrieves agent messages from the inbox or sent folder.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `direction` | string | `inbox` | `inbox` or `sent` |

**Response `200`:** Array of agent message objects.

---

### `POST /agent/propose`
**What it does:** Sends an agent message to another user's APEX. Stored in DB and delivered via Redis pub/sub to the recipient's WebSocket connection in real time.

**When to use:** When your APEX needs to coordinate with someone else's APEX — e.g., "Schedule a meeting with Sarah's PA."

**Request body:**
```json
{
  "to_user_id": "uuid-of-recipient",
  "message_type": "scheduling_request",
  "content": {
    "proposed_times": ["2025-07-16T14:00:00Z", "2025-07-17T10:00:00Z"],
    "duration_minutes": 30,
    "topic": "Q3 planning sync"
  }
}
```

**Response `201`:** The created agent message.

---

### `POST /agent/{message_id}/respond`
**What it does:** Responds to an incoming agent message — accept, decline, or counter-propose.

**Request body:**
```json
{
  "status": "negotiating",
  "counter_content": {
    "proposed_times": ["2025-07-18T15:00:00Z"],
    "note": "The earlier slots don't work — how about Thursday?"
  }
}
```

**Response `200`:** Updated agent message.

---

## 9. Call Intelligence

**Prefix:** `/api/v1/calls`

Live call transcription and AI-powered post-call analysis. Stream transcript chunks during a call, then end the session to receive a full summary with action items, decisions, and automatically created tasks.

---

### `POST /calls/start`
**What it does:** Starts a new call session. Returns a `session_id` to use for all subsequent transcript chunks.

**When to use:** When the user begins a meeting or phone call.

**Query params:** `title` (optional string)

**Response `201`:**
```json
{
  "session_id": "uuid",
  "started_at": "2025-07-15T14:00:00Z"
}
```

---

### `POST /calls/{session_id}/transcript`
**What it does:** Appends a chunk of transcript text to the session. Call this repeatedly as the transcription streams in (e.g., every few seconds from a speech-to-text provider).

**Request body:**
```json
{ "text": "...okay so let's align on the Q3 targets. Sarah, can you own the revenue forecast?" }
```

**Response `200`:** `{ "status": "ok" }`

---

### `POST /calls/{session_id}/end`
**What it does:** Ends the call session and triggers **AI analysis** via Claude Sonnet. Extracts action items, decisions, people mentioned, follow-ups, and key dates. Automatically creates tasks for each action item.

**When to use:** When the meeting ends.

**Response `200`:**
```json
{
  "session_id": "uuid",
  "summary": "Q3 planning sync with the leadership team. Agreed to increase revenue target by 15%. Sarah to own the forecast, John to handle the product roadmap update.",
  "action_items": [
    { "title": "Prepare revenue forecast", "owner": "Sarah", "due_date": "2025-07-22" },
    { "title": "Update product roadmap", "owner": "John", "due_date": "2025-07-22" }
  ],
  "decisions": ["Increase Q3 revenue target by 15%", "Weekly syncs moved to Tuesdays"],
  "people_mentioned": ["Sarah", "John", "Marcus"],
  "follow_ups": ["Send meeting notes to all attendees", "Book follow-up for July 25"],
  "key_dates": ["2025-07-22 — forecast deadline", "2025-07-25 — follow-up"],
  "tasks_created": 2
}
```

---

### `GET /calls/{session_id}`
**What it does:** Fetches an existing call session record including the full transcript and analysis.

---

## 10. Reminders

**Prefix:** `/api/v1/reminders`

Time-based reminders with multiple trigger types. The scheduler checks for due reminders every 5 minutes and delivers them via WebSocket push.

**Type values:** `time` | `location` | `deadline` | `inactivity` | `relationship`  
**Status values:** `pending` | `fired` | `snoozed` | `dismissed`

---

### `GET /reminders`
**What it does:** Lists reminders, optionally filtered by status.

**Query params:** `status` (optional)

---

### `POST /reminders`
**What it does:** Creates a reminder.

**When to use:** Any time the user says "remind me to..." or when the AI creates one via the `create_reminder` tool during chat.

**Request body:**
```json
{
  "title": "Prepare for investor call",
  "body": "Review the deck, check financials, prepare questions",
  "type": "time",
  "remind_at": "2025-07-15T20:00:00Z",
  "metadata": { "linked_task_id": "uuid" }
}
```

**Response `201`:** Reminder object.

**Delivery:** When the reminder fires, it's pushed to the user's WebSocket (`/ws/events`) as:
```json
{
  "type": "reminder",
  "reminder_id": "uuid",
  "title": "Prepare for investor call",
  "body": "Review the deck, check financials, prepare questions"
}
```

---

### `POST /reminders/{reminder_id}/snooze`
**What it does:** Snoozes a reminder by N minutes. Updates `remind_at` and resets status to `pending`.

**Request body:** `{ "minutes": 30 }`

---

### `POST /reminders/{reminder_id}/dismiss`
**What it does:** Marks a reminder as `dismissed`. It will not fire again.

**Response `200`:** `{ "message": "Reminder dismissed" }`

---

## 11. Integrations

**Prefix:** `/api/v1/integrations`

OAuth 2.0 integration management for connecting external services. Supported providers: `google`, `slack`, `notion`, `zoom`.

OAuth tokens are encrypted at rest using Fernet symmetric encryption before storage in the `integrations` table.

---

### `GET /integrations`
**What it does:** Lists all connected integrations for the user.

**Response `200`:**
```json
[
  {
    "id": "uuid",
    "provider": "google",
    "status": "active",
    "scopes": ["calendar.readonly", "gmail.readonly"],
    "connected_at": "2025-07-01T08:00:00Z"
  }
]
```

---

### `GET /integrations/{provider}/auth-url`
**What it does:** Generates an OAuth authorization URL for the specified provider. The user is redirected to this URL to grant permissions.

**Providers:** `google` | `slack` | `notion` | `zoom`

**Response `200`:**
```json
{
  "url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=...&state=<user_id>",
  "provider": "google"
}
```

**Flow:**
1. Frontend calls this endpoint to get the URL.
2. User is redirected to the provider's consent screen.
3. Provider redirects back to `/api/v1/integrations/callback/{provider}?code=...&state=<user_id>`.
4. Backend exchanges the code for tokens, encrypts them, and stores in DB.
5. User is redirected to `http://localhost:3000/settings?connected=google`.

---

### `GET /integrations/callback/{provider}` *(public — no auth)*
**What it does:** OAuth callback endpoint. Called by the provider after the user grants permissions. Exchanges the authorization code for access/refresh tokens and stores them.

This endpoint does **not** require authentication — it's called by the OAuth provider's redirect.

---

### `DELETE /integrations/{provider}`
**What it does:** Disconnects an integration. Deletes or marks the stored tokens as inactive.

**Response `200`:** `{ "message": "google disconnected" }`

---

## 12. WebSockets

Two persistent WebSocket connections power real-time features. Both use a first-message JWT handshake — no HTTP auth header is used for WebSockets.

---

### `WS /api/v1/ws/chat`
**What it does:** Streaming version of the chat endpoint. Streams Claude's response token-by-token with tool execution status updates in between. Use this for the main chat UI.

**Protocol:**

**Step 1 — Auth handshake (client → server):**
```json
{ "token": "<supabase_jwt>" }
```

**Step 2 — Server confirms:**
```json
{ "type": "connected", "user_id": "uuid" }
```

**Step 3 — Send a message (client → server):**
```json
{ "message": "What should I focus on this afternoon?" }
```

**Step 4 — Server streams events:**

| Event type | When | Payload |
|------------|------|---------|
| `chunk` | Text streaming | `{ "type": "chunk", "text": "Based on your..." }` |
| `tool_status` | Tool starting | `{ "type": "tool_status", "tool": "get_tasks", "status": "running" }` |
| `tool_done` | Tool finished | `{ "type": "tool_done", "tool": "get_tasks" }` |
| `tool_result` | Tool output | `{ "type": "tool_result", "tool": "get_tasks", "result": {...} }` |
| `done` | Response complete | `{ "type": "done", "tools_used": ["get_tasks"] }` |
| `error` | Error occurred | `{ "type": "error", "message": "Something went wrong" }` |

**Step 5:** Repeat from Step 3 for the next message. The connection stays open.

**Error codes:**
- `4001` — Auth timeout (10 seconds to send token)
- `4003` — Invalid/expired JWT

---

### `WS /api/v1/ws/events`
**What it does:** Server-push channel for reminders, agent messages, and system notifications. Keep this connection open in the background on the client.

**Protocol:**

**Step 1 — Auth handshake (same as above):**
```json
{ "token": "<supabase_jwt>" }
```

**Step 2 — Server confirms:**
```json
{ "type": "connected", "user_id": "uuid" }
```

**Step 3 — Server pushes events as they occur:**

**Reminder fired:**
```json
{
  "type": "reminder",
  "reminder_id": "uuid",
  "title": "Call Mom",
  "body": "It's been 2 weeks"
}
```

**Agent message received:**
```json
{
  "type": "agent_message",
  "from_user_id": "uuid",
  "message_type": "scheduling_request",
  "content": { "proposed_times": [...] }
}
```

**Step 4 — Keepalive (client → server every 30s):**
```json
{ "type": "ping" }
```
Server responds: `{ "type": "pong" }`

---

## 13. Error Reference

All errors return standard JSON:
```json
{ "detail": "Human-readable error message" }
```

| Status | Meaning | Common cause |
|--------|---------|--------------|
| `400` | Bad Request | Invalid input fields |
| `401` | Unauthorized | Missing or expired JWT |
| `403` | Forbidden | Accessing another user's resource |
| `404` | Not Found | Resource doesn't exist |
| `409` | Conflict | Duplicate resource |
| `422` | Unprocessable Entity | Schema validation error (Pydantic) |
| `429` | Too Many Requests | Rate limit exceeded (60 req/min default) |
| `500` | Internal Server Error | Unhandled exception |

**Rate limit headers on 429:**
```
Retry-After: 60
```

---

## 14. Architecture Overview

```
Frontend (React)
     │
     ├── HTTP  ──────────────► FastAPI (main.py)
     │                              │
     └── WebSocket ─────────────────┤
                                    │
                         ┌──────────┼──────────────┐
                         │          │               │
                    Supabase    Anthropic        Redis
                    (Postgres   (Claude API)   (Rate limiting
                    + pgvector  Opus/Sonnet/   + pub/sub
                    + Auth)     Haiku)         notifications)
                         │
                    Voyage AI
                    (Embeddings
                    voyage-3-lite
                    512-dim)
```

**Model routing:**
| Use case | Model |
|----------|-------|
| Daily brief, complex reasoning | Claude Opus (`claude-opus-4-7`) |
| Chat, call extraction, replan | Claude Sonnet (`claude-sonnet-4-6`) |
| Eisenhower classification, memory extraction | Claude Haiku (`claude-haiku-4-5-20251001`) |

**Background jobs (APScheduler):**
| Job | Schedule | What it does |
|-----|----------|--------------|
| `_check_and_fire_reminders` | Every 5 minutes | Finds due reminders, pushes via WebSocket |
| `_reset_daily_moods` | Daily at midnight UTC | Clears `mood_today` on all profiles |

**Memory pipeline:**
```
User message / conversation
         │
         ▼
Claude Haiku extracts facts
         │
         ▼
Voyage AI embeds (512-dim vector)
         │
         ▼
Supabase pgvector stores
         │
         ▼
Semantic search at chat time
(top-k cosine similarity via match_memories RPC)
```
