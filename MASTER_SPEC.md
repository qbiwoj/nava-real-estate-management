# Nava Real Estate Management — Master Spec

## Context

Demo AI system for a property management administrator who receives 40–60 resident messages/day across email, SMS, and voicemail. The system ingests messages, classifies and groups them into threads, runs an AI agent to decide on actions (draft reply, escalate, no-op), and surfaces everything in a minimal admin UI. The admin can edit agent outputs, approve/correct decisions, and call in for a spoken queue briefing. Agent corrections are stored and fed back as few-shot examples on future runs.

**Not production-ready, but architecturally solid.** Built in focused Claude Code sessions to preserve context.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (async) + PostgreSQL 16 + pgvector |
| ORM / migrations | SQLAlchemy 2.x async + Alembic |
| Agent | Anthropic SDK (direct `tool_use` loop, no framework) |
| Embeddings | OpenAI `text-embedding-3-small` (stored in pgvector) |
| Voice | ElevenLabs inbound briefing webhook |
| Frontend | Vite + React + TypeScript + Tailwind + shadcn/ui + TanStack Query |
| Package manager | uv (already in place, Python 3.14) |
| Dev infra | docker-compose for Postgres + pgvector (no app container) |

---

## Data Model

**`messages`** — channel (email/sms/voicemail), raw_content, transcription, subject, sender_ref (email or phone), sender_type (resident/supplier/board/unknown), transcription_confidence (float, for voicemail), received_at, `embedding vector(1536)`

**`threads`** — category (maintenance/payment/noise_complaint/lease/general/supplier/other), priority (low/medium/high/urgent), status (new/pending_review/replied/resolved/escalated)
_(no resident FK — senders identified by sender_ref on messages only)_

**`thread_messages`** — junction table (thread ↔ message, many-to-many)

**`agent_decisions`** — action (draft_reply/escalate/group_only/no_action), rationale, draft_reply text, model_id, `few_shot_ids UUID[]`, `is_current bool`

**`admin_feedback`** — feedback_type (approved/corrected/overridden), original vs corrected action/draft, correction_note, `embedding vector(1536)` (thread context at correction time)

**`outbound_replies`** — final_body, channel, status (pending/sent/failed), links to feedback record

**`voice_sessions`** — call_sid, briefing_text, threads_covered UUID[]

### Notes from sample data (`data.csv`)
- Sender types include: residents, board/management (`zarzad@...`), supplier/vendor (`biuro@bud-serwis.pl`), new English-speaking tenant
- Related messages pre-annotated in `uwagi` column (e.g. id=11 → id=1, id=12 → id=2, id=16 → id=2+12) — used as ground truth for thread grouping seed
- One voicemail has low transcription confidence (~72%) — agent must handle partial/garbled input gracefully
- One message is in English — agent must handle multilingual content

---

## API Surface (`/api/v1`)

### Webhooks (ingest — mock, no real vendor)
- `POST /webhooks/email` — subject/body/from JSON → 202
- `POST /webhooks/sms` — from/body JSON → 202
- `POST /webhooks/voicemail` — from/transcription/audio_url JSON → 202

### Threads
- `GET /threads` — paginated, filter by status/priority/category
- `GET /threads/{id}` — full detail (messages + current decision + feedback history)
- `POST /threads/{id}/run-agent` — manual agent trigger
- `PATCH /threads/{id}` — admin status/priority override

### Decisions
- `GET /threads/{id}/decisions` — decision history
- `GET /decisions/{id}` — single decision with few_shot_ids

### Feedback
- `POST /threads/{id}/feedback` — approve / correct / override
- `GET /feedback` — list, filterable
- `GET /feedback/similar?thread_id=&top_n=5` — similar past corrections

### Replies
- `POST /threads/{id}/send-reply` — marks reply sent, creates outbound record
- `GET /threads/{id}/replies` — reply history

### Voice
- `POST /voice/inbound` — ElevenLabs webhook → SSML briefing response
- `GET /voice/briefing-text` — plain text version (testing)
- `POST /voice/sessions/{call_sid}/end` — close session

### Admin / Health
- `GET /health`, `GET /health/db`, `GET /admin/stats`

---

## Agent Architecture

### Tools (6)
1. `classify_and_set_category` — sets thread category + priority
2. `group_messages` — pulls additional related messages into the thread
3. `draft_reply` — stores a reply draft in the decision record
4. `escalate` — sets status=escalated, priority=urgent
5. `search_similar_threads` — pgvector ANN search for context enrichment
6. `mark_no_action` — records decision with rationale

### Prompt Structure
```
SYSTEM (assembled at runtime):
  [static]  role + property context block        ← Anthropic cache_control here
  [dynamic] few-shot correction block            ← top-N similar past corrections

USER:
  thread header (id, category hint, resident info)
  all messages in thread, chronological
  "Decide what action to take."
```

### Few-Shot Injection
1. At agent invocation: embed all message content in the thread
2. `SELECT ... FROM admin_feedback ORDER BY embedding <=> $1 LIMIT $N` (pgvector cosine)
3. Filter to `corrected` and `overridden` only
4. Inject as natural-language correction examples into system prompt
5. Record used `feedback.id` values in `agent_decisions.few_shot_ids` for auditability

### Ingestion → Agent Flow
```
webhook POST
  → ingest_message (parse, normalize, detect sender_type)
  → find_or_create_thread (pgvector similarity, threshold 0.25)
  → BackgroundTask: run_agent_on_thread
      → assemble_system_prompt (few-shot inject)
      → Claude agentic loop (tool_use until end_turn)
      → persist agent_decisions, update thread.status = pending_review
```

---

## Directory Layout

```
app/
  main.py          # FastAPI app factory + lifespan
  config.py        # pydantic-settings (DATABASE_URL, ANTHROPIC_API_KEY, etc.)
  database.py      # async engine, session factory, Base
  models/          # SQLAlchemy ORM (one file per table)
  schemas/         # Pydantic request/response schemas
  routers/         # FastAPI routers (webhooks, threads, decisions, feedback, replies, voice, admin)
  services/
    ingestion.py   # parse, sender_type detection, thread grouping
    agent.py       # prompt assembly, agentic loop, decision persist
    tools.py       # all 6 tool implementations
    embeddings.py  # generate + similarity search
    feedback.py    # store feedback embedding, retrieve similar corrections
    voice.py       # briefing generation + SSML formatting
  tasks/
    agent_runner.py  # BackgroundTask wrapper
  seed.py          # demo data script
tests/             # pytest, mirrors app/ structure
frontend/          # Vite + React + TS + Tailwind + shadcn
  src/
    pages/         # QueuePage, ThreadPage
    components/    # ThreadList, ThreadDetail, AgentDecisionPanel, DraftEditor, FeedbackControls
    hooks/         # useThreads, useThread (TanStack Query, 30s poll)
    lib/           # api.ts (typed fetch client), types.ts
```

---

## Session Breakdown

### Session 1 — Foundation: DB, Models, Migrations
**Goal**: Working database layer, nothing else.

- `uv add` all backend deps: `fastapi[standard] uvicorn sqlalchemy[asyncio] asyncpg alembic pgvector pydantic-settings anthropic openai pytest pytest-asyncio httpx factory-boy python-dotenv`
- `app/config.py` — pydantic-settings reading from `.env`
- `app/database.py` — async engine + session
- All 6 ORM models in `app/models/` (messages, threads, thread_messages, agent_decisions, admin_feedback, outbound_replies, voice_sessions)
- Alembic configured for async + `CREATE EXTENSION IF NOT EXISTS vector`
- First migration: all tables
- `app/main.py` — minimal app factory, `/health` endpoint
- `tests/conftest.py` — test DB fixtures, factory-boy model factories
- `tests/test_models.py` — create/query/FK/enum tests for each model

**Done when**: `pytest tests/test_models.py` green, `/health` returns 200.

---

### Session 2 — Ingestion Pipeline: Webhooks + Thread Grouping
**Goal**: End-to-end webhook → persisted thread.

- Pydantic schemas for all 3 webhook payloads
- `app/services/embeddings.py` — `generate_embedding(text)` (mockable)
- `app/services/ingestion.py` — parse/normalize, detect sender_type, pgvector thread-grouping (threshold from config)
- `app/routers/webhooks.py` — 3 POST endpoints, each → `ingest_message` → 202
- `tests/test_webhooks.py` — route tests (mock embeddings)
- `tests/test_ingestion.py` — unit tests for grouping logic: same sender + near-duplicate topic → grouped; unrelated → new thread; supplier message → `sender_type=supplier`

**Done when**: POST to `/webhooks/email` creates a message + thread in test DB.

---

### Session 3 — Agent Core: Tools, Prompt Assembly, Decision Persistence
**Goal**: Claude processes a thread and stores a decision. No UI, no real API calls.

- `app/services/tools.py` — all 6 tool implementations + Anthropic tool schemas
- `app/services/feedback.py` — `retrieve_similar_corrections` (pgvector similarity on admin_feedback)
- `app/services/agent.py` — `assemble_system_prompt` (few-shot inject), `run_agent` (agentic loop)
- `app/routers/threads.py` — `POST /threads/{id}/run-agent`
- `app/routers/decisions.py` — 2 GET endpoints
- `tests/test_agent.py` — mock `anthropic.messages.create`; assert: tools passed correctly, tool dispatch calls service functions, decision persisted, few_shot_ids recorded, correction appears in injected prompt

**Key**: Use Anthropic `cache_control` on the static system prompt prefix.

**Done when**: `pytest tests/test_agent.py` green with zero real Anthropic calls.

---

### Session 4 — Feedback Loop + Reply Sending
**Goal**: Admin can approve/correct decisions; corrections affect future agent runs.

- `app/services/feedback.py` (complete) — `submit_feedback` persists record + generates + stores embedding atomically
- `app/routers/feedback.py` — 3 endpoints
- `app/routers/replies.py` — send-reply + reply history
- `app/routers/threads.py` (complete) — list (paginated/filtered), detail, PATCH
- Integration test: webhook → ingest → agent (mocked) → submit correction → agent on similar thread (mocked) → assert correction string appears in assembled prompt
- `tests/test_feedback.py`

**Done when**: Full feedback cycle passes in tests.

---

### Session 5 — Voice Briefing + Frontend UI
**Goal**: Demo-ready UI and voice endpoint.

**Voice (backend)**:
- `app/services/voice.py` — `generate_queue_briefing` (Claude, non-agentic) + SSML formatter
- `app/routers/voice.py` — 3 voice endpoints
- `tests/test_voice.py`

**Frontend**:
- Vite + React + TS scaffold in `frontend/`
- Tailwind + shadcn/ui configured
- `api.ts` — typed fetch client for all needed endpoints
- **QueuePage** (`/`) — thread table: priority badge, category, sender_ref, status, message preview, updated_at. Click → ThreadPage.
- **ThreadPage** (`/threads/:id`) — left: message list (channel icon + timestamp). Right: AgentDecisionPanel (action + rationale, collapsible), DraftEditor (pre-filled textarea), FeedbackControls (Approve / Override + note), Send Reply button.
- 30-second polling via TanStack Query
- FastAPI CORS: `localhost:5173`

**Done when**: UI shows thread queue, open thread, approve/override agent draft, send reply.

---

### Session 6 — Seed Data, Polish, Demo Hardening
**Goal**: Everything needed for a 10-minute live demo without surprises.

- `app/seed.py` — loads all 16 messages from `data.csv` with correct groupings (using `uwagi` annotations), plus 5 pre-built `admin_feedback` correction records with embeddings, threads in mixed statuses
- Structured JSON logging on every agent run (thread_id, action, few_shot_count, model_id, latency_ms)
- `GET /admin/stats` — counts by status/priority/category + avg agent latency
- Global exception handler → RFC 7807 `application/problem+json`
- Rate limit on webhooks (simple token bucket, 100 req/min)
- `docker-compose.yml` — Postgres 16 + pgvector (no app container)
- `CLAUDE.md` — how to run, env vars, how to add a new agent tool, how few-shot pipeline works
- `README.md` — 10-minute demo script

**Done when**: `docker-compose up -d && uv run python -m app.seed && uvicorn app.main:app` → fully seeded, demo-ready. All tests green.

---

## Sequencing

```
Session 1 (DB)
    │
Session 2 (ingestion)
    │
Session 3 (agent core)
    │
Session 4 (feedback)
    │         │
Session 5   Session 5
(voice)     (frontend)
    │         │
    └────┬────┘
    Session 6 (polish)
```

Sessions 5-voice and 5-frontend can be split or done in sequence — voice only needs Sessions 1–3.

---

## Key Decisions

- **pgvector not a separate vector DB** — message volume (40–60/day) and correction corpus are tiny; one DB keeps infra minimal
- **Direct Anthropic SDK agentic loop, no framework** — 30 lines of `while stop_reason != "end_turn"`, fully transparent for a demo
- **Prompt caching on static prefix** — avoids billing the role + property context block on every agent call
- **FastAPI BackgroundTasks not Celery** — sufficient at demo scale; `run_agent_on_thread` is a pure async fn that can be moved to a queue later without changes
- **Few-shot over fine-tuning** — no model training required; corrections are live from the first feedback submission

---

## Verification (end-to-end)

1. `docker-compose up -d` → Postgres with pgvector running
2. `uv run alembic upgrade head` → all tables created
3. `uv run python -m app.seed` → demo data populated
4. `uvicorn app.main:app --reload` → backend running on :8000
5. `curl -X POST localhost:8000/api/v1/webhooks/sms -d '{"from":"+15551234567","body":"My heater is broken"}'` → 202, thread created
6. `curl -X POST localhost:8000/api/v1/threads/{id}/run-agent` → agent processes, decision stored
7. `GET /api/v1/threads/{id}` → shows action + draft reply
8. `POST /api/v1/threads/{id}/feedback` with correction → feedback stored with embedding
9. Run agent on a new similar thread → assert correction appears in decision's few_shot_ids
10. `curl -X POST localhost:8000/api/v1/voice/inbound` → SSML briefing returned
11. `cd frontend && npm run dev` → UI at localhost:5173 showing queue + full thread flow
12. `pytest --tb=short -q` → all green
