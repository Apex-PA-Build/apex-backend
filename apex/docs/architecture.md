# APEX System Architecture

## Overview

APEX is built as a **single-tenant multi-user async API** where each user has a logically isolated AI agent. The system is stateless at the API layer (horizontal scaling) with state in PostgreSQL, Redis, and Qdrant.

```
Client (Web/Mobile PWA)
    │
    │  HTTPS / WSS
    ▼
┌─────────────────────────────────────────────────────┐
│  FastAPI Application (main.py)                      │
│                                                     │
│  Middleware Stack (ordered outer → inner):          │
│    CORS → Logging + Request ID → Auth (JWT) →       │
│    Error Handler                                    │
│                                                     │
│  Routers (/api/v1/):                               │
│    auth  brief  tasks  goals  calendar  memory      │
│    agent  integrations  calls  reminders  ws        │
│                                                     │
│  Services Layer:                                    │
│    LLM ── Memory ── Task ── Goal ── Calendar        │
│    Brief ── Call ── Agent ── Integration            │
│    Reminder ── Notification                         │
└──────────┬──────────────────────┬───────────────────┘
           │                      │
    ┌──────▼──────┐       ┌───────▼────────┐
    │ PostgreSQL  │       │     Redis       │
    │             │       │                 │
    │ users       │       │ Rate limiting   │
    │ tasks       │       │ Session cache   │
    │ goals       │       │ Reminders queue │
    │ calendar    │       │ Pub/Sub:        │
    │ memories    │       │  agent:<uid>    │
    │ integrations│       │  reminders:<uid>│
    │ agent_msgs  │       └─────────────────┘
    └──────┬──────┘
           │
    ┌──────▼──────┐       ┌─────────────────┐
    │   Qdrant    │       │  Anthropic API  │
    │             │       │                 │
    │ apex_memory │       │ claude-sonnet   │
    │ (vectors)   │       │ (LLM reasoning) │
    └─────────────┘       └─────────────────┘
```

---

## Layer-by-Layer Design

### 1. Middleware Layer

Requests flow through four middleware in order:

**CORS** — Permissive in dev (`*`), allowlist in production. Credentials enabled for cookie-based auth fallback.

**LoggingMiddleware** — Binds a `request_id` (UUID) into structlog context. Every log line emitted during the request automatically includes `request_id`, `user_id`, `method`, `path`. Skips `/health`.

**AuthMiddleware** — Extracts JWT from `Authorization: Bearer` header. Decodes and validates. Injects `request.state.user_id`. Public paths and WebSocket upgrades are bypassed (WebSockets authenticate in-handler via first message or query param).

**Error Handler** — Catches `APEXError` subclasses and maps them to structured JSON HTTP responses. Catches all other `Exception` as 500. Logs with full stack trace.

---

### 2. Router Layer

Routers are thin — they only:
- Extract `user_id` from `request.state`
- Call a service method
- Serialize the response with a Pydantic schema

No business logic lives in routers.

---

### 3. Service Layer

This is where APEX's intelligence lives.

#### LLM Service (`llm_service.py`)
- Wraps `anthropic.AsyncAnthropic`
- Three primitives: `chat()`, `stream_chat()`, `extract_json()`, `classify_single()`
- All calls retry 3× with exponential backoff via `tenacity`
- `stream_chat()` yields token chunks for WebSocket streaming

#### Memory Service (`memory_service.py`)
Two-store architecture:
```
Text → Claude (extract entities) → PostgreSQL (metadata) + Qdrant (embedding)
Query → embed query → Qdrant similarity search → PostgreSQL join (for timestamps/category)
```
Every significant user interaction (call transcripts, conversations, task creation) runs through `extract_and_store_memories()` asynchronously.

#### Task Service (`task_service.py`)
Intelligence stack for tasks:
```
Task list → detect_overload() → pick_focus_task() → Eisenhower classification
```
- `classify_tasks_eisenhower()` calls Claude with `build_classification_prompt()`, falls back to `heuristic_quadrant()` on LLM failure
- `pick_focus_task()` sorts by: quadrant priority → urgency score → due date proximity

#### Brief Service (`brief_service.py`)
Aggregates context from 4 sources in sequence:
```
calendar → tasks → memories → agent inbox → Claude (narrative) → Claude (focus) → Claude (mood prompt)
```
Three separate Claude calls produce: narrative, focus recommendation, mood check-in question. This keeps each prompt focused and avoids token bloat.

#### Call Service (`call_service.py`)
In-memory session store (upgrade to Redis for multi-instance):
```
start_call_session() → WebSocket streams chunks → append_transcript_chunk()
→ end_call_session() → Claude extract_json() → create_task() × N → extract_and_store_memories()
```

#### Agent Service (`agent_service.py`)
PA-to-PA protocol:
```
User A proposes → AgentMessage(status=pending) + Redis PUBLISH(agent:user_b)
User B's WS listener receives → surfaces in UI
User B accepts/declines/counters → status update + Redis PUBLISH(agent:user_a)
```
Full audit trail: every message and response is a row in `agent_messages`. Users can always inspect what their agent said.

---

### 4. Database Layer

#### PostgreSQL Schema

```
users ──────────────────────────────────────────────────────┐
  │                                                          │
  ├── tasks (goal_id FK → goals, parent_task_id self-ref)   │
  │                                                          │
  ├── goals                                                  │
  │                                                          │
  ├── calendar_events                                        │
  │                                                          │
  ├── memories (soft delete, embedding_id → Qdrant point)   │
  │                                                          │
  ├── integrations (encrypted tokens)                        │
  │                                                          │
  └── agent_messages (from_user_id + to_user_id → users)   ◄┘
```

All UUIDs (PostgreSQL native UUID type). All timestamps are `TIMESTAMPTZ`. JSONB for flexible fields (preferences, attendees, agent message content).

#### Qdrant Vector Store

Single collection: `apex_memory`
- Vector size: 1536 (text-embedding-3-small compatible)
- Distance: Cosine similarity
- Payload per point: `{ user_id, content, category }`
- All searches are filtered by `user_id` — strict tenant isolation

---

### 5. Real-Time Architecture

```
Redis Pub/Sub Channels:
  reminders:<user_id>   ← reminder_service publishes nudges
  agent:<user_id>       ← agent_service publishes PA-to-PA events

WebSocket Handlers:
  /ws/reminders → subscribe(reminders:<uid>) → forward to client
  /ws/agent     → subscribe(agent:<uid>)     → forward to client
  /ws/brief     → stream_chat() token chunks → forward to client
  /ws/call      → receive chunks → append_transcript_chunk()
```

`ConnectionManager` (notification_service.py) tracks all active WebSocket connections per user. Supports multiple tabs/devices — each `user_id` maps to a list of WebSocket instances.

On disconnect, dead sockets are pruned from the list. If all connections for a user close, the entry is removed.

---

### 6. Security Design

**Authentication** — Stateless JWT. Access token (30 min), refresh token (30 days). Both carry `type` claim to prevent token type confusion attacks.

**OAuth token storage** — Integration tokens are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) before storing in PostgreSQL. The `ENCRYPTION_KEY` env var is the only key — rotate it to invalidate all stored tokens.

**Rate limiting** — Sliding window via Lua script in Redis. Atomic check-and-increment. Per-user + per-path. Protects LLM endpoints (expensive) and financial endpoints (sensitive).

**Input validation** — Pydantic v2 validates all request bodies with strict types. Field-level validators enforce password strength, status enums, quadrant ranges.

**Agent message authorization** — `respond_to_message()` checks `msg.to_user_id == user_id` before allowing a response. Users cannot respond to messages sent to someone else.

**Memory privacy** — All Qdrant searches include a `user_id` filter. Cross-user memory leakage is architecturally impossible via the API. Users can wipe all their memories via `DELETE /memory`.

---

### 7. Integration Pattern

All third-party OAuth integrations follow the same pattern:

```
1. GET /integrations/{provider}/auth-url
   → Returns redirect URL with state="{user_id}:{provider}"

2. User redirected → consents → provider redirects to /integrations/callback/{provider}?code=...&state=...

3. Server: exchange code → access_token + refresh_token
           → encrypt(access_token) → store in integrations table
           → encrypt(refresh_token) → store in integrations table

4. Any service needing the token calls get_access_token(provider, user_id, db)
   → decrypt(integration.access_token_enc)
   → use in upstream API call
```

Token refresh is the caller's responsibility (not yet automated — production TODO).

---

### 8. Scaling Considerations

| Concern | Current | Production Path |
|---|---|---|
| API tier | Single instance | Horizontal (stateless, Redis for shared state) |
| DB connections | SQLAlchemy pool (10+20) | PgBouncer connection pooler |
| Background work | In-request | Celery + Redis broker |
| Call sessions | In-memory dict | Redis hash (multi-instance safe) |
| WebSocket events | Redis pub/sub | Already multi-instance safe |
| Embeddings | Stub (zero vector) | OpenAI text-embedding-3-small or Voyage |
| Vector search | Single Qdrant node | Qdrant distributed cluster |
| LLM | Direct API calls | Prompt caching + request batching |

---

### 9. Dependency Flow (No Circular Dependencies)

```
config ← (no deps)
exceptions ← (no deps)
utils/* ← config, exceptions
db/session ← config
db/vector_store ← config
models/* ← db/base
schemas/* ← models/*
core/cache ← config
core/security ← config
core/rate_limit ← cache
services/llm_service ← config, cache
services/memory_service ← vector_store, llm_service, models/memory
services/task_service ← db/session, llm_service, utils/task_helpers
services/goal_service ← task_service, llm_service
services/integration_service ← models/integration, security, utils/encryption
services/calendar_service ← integration_service, db/session
services/call_service ← llm_service, task_service, memory_service
services/agent_service ← models/agent_message, llm_service, cache
services/brief_service ← agent_service, calendar_service, task_service, memory_service, llm_service
services/reminder_service ← cache, memory_service
services/notification_service ← (no service deps — pure WebSocket manager)
routers/* ← services/*, schemas/*, db/session, core/exceptions
middleware/* ← core/security, core/logging, core/exceptions
main ← routers/*, middleware/*, core/events
```
