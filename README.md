# APEX — AI Personal Assistant OS

> *"The personal assistant you'd hire if you could afford one — now everyone can."*

APEX is a production-grade FastAPI backend for an AI-powered personal assistant. It acts as a deeply loyal chief-of-staff: it watches your calendar, manages your tasks, listens on calls, remembers everything, and negotiates with other users' APEX agents on your behalf.

---

## Architecture at a Glance

```
FastAPI (main.py) 
  ├── Middleware:   CORS → Logging → Auth (JWT) → Error Handler.
  ├── Routers:      /api/v1/{auth,brief,tasks,goals,calendar,memory,agent,integrations,calls,reminders}
  │                 WebSockets: /api/v1/ws/{brief,call,reminders,agent}
  ├── Services:     LLM (Claude), Memory, Task Intelligence, Calendar Sync,
  │                 Brief Generation, Call Intelligence, PA-to-PA Agent
  ├── DB Layer:     PostgreSQL (SQLAlchemy async) + Qdrant (vector embeddings)
  └── Cache/RT:     Redis (rate limiting, pub/sub, reminder queue)
```

---

## Quick Start

### Prerequisites
- Python 3.14+
- Docker & Docker Compose
- An Anthropic API key

### 1. Clone and configure

```bash
git clone https://github.com/your-org/apex.git
cd apex
cp .env.example .env
# Edit .env and fill in ANTHROPIC_API_KEY, APP_SECRET_KEY, JWT_SECRET_KEY, ENCRYPTION_KEY
```

**Generate a valid ENCRYPTION_KEY:**
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

### 2. Run with Docker Compose

```bash
docker compose up -d
```

Services started:
| Service | Port | Description |
|---|---|---|
| APEX API | 8000 | FastAPI application |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Cache & pub/sub |
| Qdrant | 6333 | Vector store for memory |

### 3. Run database migrations

```bash
docker compose exec app alembic upgrade head
```

### 4. Open the API docs

```
http://localhost:8000/docs
```

---

## Local Development (without Docker)

```bash
# Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Start infrastructure only
docker compose up postgres redis qdrant -d

# Run migrations
alembic upgrade head

# Start the dev server
python main.py
```

---

## Running Tests

```bash
# All tests with coverage
pytest

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Single test file
pytest tests/unit/test_task_service.py -v

# With Docker (full stack)
docker compose -f docker-compose.yml -f docker-compose.test.yml up --abort-on-container-exit
```

---

## API Summary

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register new user |
| `POST` | `/api/v1/auth/login` | Login, get JWT tokens |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `GET` | `/api/v1/auth/me` | Get current user |
| `POST` | `/api/v1/brief/generate` | Generate morning brief |
| `POST` | `/api/v1/brief/mood-checkin` | Submit mood check-in |
| `GET` | `/api/v1/tasks` | List tasks (filter by status) |
| `POST` | `/api/v1/tasks` | Create task |
| `PATCH` | `/api/v1/tasks/{id}` | Update task |
| `DELETE` | `/api/v1/tasks/{id}` | Delete task |
| `GET` | `/api/v1/tasks/focus-now` | The one task to focus on now |
| `POST` | `/api/v1/tasks/bulk-defer` | Defer multiple tasks |
| `POST` | `/api/v1/tasks/classify` | Eisenhower quadrant classification |
| `GET` | `/api/v1/goals` | List goals |
| `POST` | `/api/v1/goals` | Create goal |
| `PATCH` | `/api/v1/goals/{id}` | Update goal |
| `GET` | `/api/v1/goals/{id}/progress` | Goal progress detail |
| `GET` | `/api/v1/goals/weekly-review` | AI weekly review narrative |
| `GET` | `/api/v1/goals/alignment-check` | Task→goal alignment score |
| `GET` | `/api/v1/calendar/today` | Today's schedule + free blocks |
| `POST` | `/api/v1/calendar/events` | Create calendar event |
| `POST` | `/api/v1/calendar/sync` | Sync Google Calendar |
| `POST` | `/api/v1/calendar/suggest-buffer` | Suggest buffer time for event |
| `GET` | `/api/v1/memory` | List user memories |
| `POST` | `/api/v1/memory/search` | Semantic memory search |
| `DELETE` | `/api/v1/memory/{id}` | Delete a memory |
| `DELETE` | `/api/v1/memory` | Wipe all memories |
| `GET` | `/api/v1/agent/messages` | PA inbox (sent + received) |
| `POST` | `/api/v1/agent/propose` | Initiate scheduling/financial negotiation |
| `POST` | `/api/v1/agent/respond` | Accept / decline / counter |
| `POST` | `/api/v1/agent/send` | Send raw agent message |
| `GET` | `/api/v1/integrations` | List connected apps |
| `GET` | `/api/v1/integrations/{provider}/auth-url` | Get OAuth URL |
| `GET` | `/api/v1/integrations/callback/{provider}` | OAuth callback |
| `DELETE` | `/api/v1/integrations/{provider}` | Disconnect integration |
| `POST` | `/api/v1/calls/start` | Start call session |
| `POST` | `/api/v1/calls/{id}/end` | End call + extract summary |
| `GET` | `/api/v1/reminders` | List pending smart reminders |
| `POST` | `/api/v1/reminders/{id}/snooze` | Snooze a reminder |
| `POST` | `/api/v1/reminders/{id}/dismiss` | Dismiss a reminder |

**WebSocket Endpoints:**

| Endpoint | Description |
|---|---|
| `WS /api/v1/ws/brief` | Stream morning brief token-by-token |
| `WS /api/v1/ws/call` | Live call transcript feed |
| `WS /api/v1/ws/reminders` | Push smart reminders in real-time |
| `WS /api/v1/ws/agent` | PA-to-PA live negotiation events |

---

## Environment Variables

See `.env.example` for the full list. Required variables:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg) |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `JWT_SECRET_KEY` | Secret for signing JWTs |
| `APP_SECRET_KEY` | General app secret |
| `ENCRYPTION_KEY` | Fernet key for encrypting OAuth tokens |
| `REDIS_URL` | Redis connection string |
| `QDRANT_URL` | Qdrant vector store URL |

---

## Project Structure

```
apex/
├── main.py                   # App factory + entry point
├── alembic/                  # DB migrations
│   ├── env.py
│   └── versions/
├── app/
│   ├── core/                 # Config, logging, security, cache, rate limiting
│   ├── db/                   # SQLAlchemy engine, Qdrant client
│   ├── models/               # ORM models (User, Task, Goal, Memory, ...)
│   ├── schemas/              # Pydantic v2 request/response schemas
│   ├── services/             # Business logic (LLM, brief, tasks, agent, ...)
│   ├── routers/              # FastAPI route handlers
│   ├── middleware/           # Auth, logging, CORS, error handling
│   └── utils/                # Helpers: encryption, datetime, pagination, prompts
├── tests/
│   ├── unit/                 # Service-level tests (mocked DB + LLM)
│   └── integration/          # Full API tests via httpx AsyncClient
├── docs/
│   ├── api_overview.md       # Detailed API reference
│   └── architecture.md       # System design documentation
├── Dockerfile
├── docker-compose.yml
├── docker-compose.test.yml
├── pyproject.toml
└── .env.example
```

---

## Key Design Decisions

**Async everywhere** — SQLAlchemy async engine, asyncpg driver, aioredis, httpx async client. Zero blocking I/O.

**LLM via tenacity retry** — All Anthropic API calls retry up to 3× with exponential backoff. LLM errors are surfaced as `503 LLMError`, not 500s.

**Encrypted OAuth tokens** — All integration access/refresh tokens are AES-256-GCM encrypted (Fernet) before hitting the database. The raw token never touches the ORM.

**Memory = two stores** — PostgreSQL stores metadata + soft-delete flag. Qdrant stores the embedding for semantic search. Both are updated atomically per memory item.

**PA-to-PA via Redis pub/sub** — When agent A sends a message to agent B, a Redis `PUBLISH` fires immediately. Agent B's WebSocket listener picks it up and pushes to the client in under 100ms.

**Rate limiting is sliding window** — A Lua script atomically checks and increments a Redis sorted set. No race conditions. Per-user and per-endpoint limits are independent.

---

## Deployment

### Production checklist
- [ ] Set `APP_ENV=production` — disables `/docs`, enables JSON logging
- [ ] Use a secrets manager for `ANTHROPIC_API_KEY`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY`
- [ ] Set `CORS_ORIGINS` to your actual frontend domain
- [ ] Configure PostgreSQL with connection pooling (PgBouncer recommended)
- [ ] Set Redis `maxmemory-policy allkeys-lru` for cache eviction
- [ ] Enable HTTPS via reverse proxy (nginx / Caddy)
- [ ] Set `APP_WORKERS` to `(2 × CPU cores) + 1`

### Scaling
- Stateless app tier → horizontal scaling behind a load balancer
- Redis pub/sub works across multiple app instances (WebSocket events broadcast correctly)
- Qdrant supports distributed mode for large memory collections
- Background tasks (reminder scheduling, calendar sync) → move to Celery + Redis broker for production

---

## Contributing

```bash
# Lint
ruff check . --fix

# Type check
mypy app/

# Format
ruff format .

# Run tests
pytest --tb=short
```

All PRs require passing lint, type checks, and 80%+ test coverage.
