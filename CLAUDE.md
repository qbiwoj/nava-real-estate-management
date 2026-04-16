# Nava Real Estate Management — Claude Code Context

Property management AI demo. An administrator receives 40–60 messages/day (email, SMS, voicemail) from residents. The system ingests them, groups related messages into threads, runs an AI agent to classify and act (draft reply, escalate, no-op), and surfaces everything in a minimal admin UI with a human feedback loop and voice briefing capability.

Full spec: `MASTER_SPEC.md`. Sample data: `data.csv` (16 real messages in Polish/English).

---

## Running the Project

```bash
# Infrastructure
docker-compose up -d                        # Postgres 16 + pgvector

# Backend
cp .env.example .env                        # fill in keys
uv run alembic upgrade head                 # run migrations
uvicorn app.main:app --reload               # API on :8000

# Seed demo data
uv run python -m app.seed                   # loads data.csv + feedback corrections

# Tests
uv run pytest --tb=short -q

# Frontend
cd frontend && npm install && npm run dev   # UI on :5173
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@localhost:5432/nava` |
| `TEST_DATABASE_URL` | Separate DB for pytest (e.g. `nava_test`) |
| `ANTHROPIC_API_KEY` | Claude API — used by agent + voice briefing |
| `OPENAI_API_KEY` | Embeddings (`text-embedding-3-small`) |
| `ELEVENLABS_API_KEY` | Voice inbound webhook |
| `THREAD_SIMILARITY_THRESHOLD` | pgvector cosine distance cutoff for grouping (default `0.25`) |
| `TOP_N_FEW_SHOT` | How many past corrections to inject (default `5`) |

---

## Architecture in One Page

```
webhook POST (email / SMS / voicemail)
  → app/services/ingestion.py
      parse + detect sender_type (resident / supplier / board / unknown)
      pgvector similarity → find_or_create_thread (threshold from config)
  → FastAPI BackgroundTask: app/tasks/agent_runner.py
      → app/services/agent.py: assemble_system_prompt()
            [static]  role + property context  ← cache_control here
            [dynamic] top-N similar corrections from admin_feedback
         run_agent(): while stop_reason != "end_turn" loop
            tools dispatched → app/services/tools.py
      → persist agent_decisions, thread.status = pending_review

Admin reviews in UI → approves or corrects
  → app/services/feedback.py: submit_feedback()
      persist admin_feedback + generate + store embedding
      (next agent run on similar thread picks this up as few-shot)
```

---

## Data Model (tables)

| Table | Key fields |
|---|---|
| `messages` | channel, raw_content, transcription, subject, sender_ref, sender_type, transcription_confidence, received_at, `embedding vector(1536)` |
| `threads` | category, priority, status — no resident FK |
| `thread_messages` | junction: thread ↔ message |
| `agent_decisions` | action, rationale, draft_reply, model_id, `few_shot_ids UUID[]`, `is_current bool` |
| `admin_feedback` | feedback_type, original/corrected action+draft, correction_note, `embedding vector(1536)` |
| `outbound_replies` | final_body, channel, status |
| `voice_sessions` | call_sid, briefing_text, threads_covered |

**Enums**
- `channel`: email / sms / voicemail
- `sender_type`: resident / supplier / board / unknown
- `category`: maintenance / payment / noise_complaint / lease / general / supplier / other
- `priority`: low / medium / high / urgent
- `status`: new / pending_review / replied / resolved / escalated
- `action`: draft_reply / escalate / group_only / no_action
- `feedback_type`: approved / corrected / overridden

---

## Directory Layout

```
app/
  main.py              # FastAPI app factory + lifespan
  config.py            # pydantic-settings
  database.py          # async engine, AsyncSession, Base
  models/              # SQLAlchemy ORM — one file per table
  schemas/             # Pydantic request/response schemas
  routers/             # webhooks, threads, decisions, feedback, replies, voice, admin
  services/
    ingestion.py       # parse, sender_type, pgvector thread grouping
    agent.py           # prompt assembly, agentic loop, decision persist
    tools.py           # 6 tool implementations + Anthropic schemas
    embeddings.py      # generate_embedding(), similarity search
    feedback.py        # submit_feedback(), retrieve_similar_corrections()
    voice.py           # generate_queue_briefing(), SSML formatter
  tasks/
    agent_runner.py    # BackgroundTask wrapper for run_agent()
  seed.py              # loads data.csv → DB with correct thread groupings
tests/                 # mirrors app/ — conftest.py has DB fixtures + factories
frontend/              # Vite + React + TS + Tailwind + shadcn/ui
  src/
    pages/             # QueuePage (/), ThreadPage (/threads/:id)
    components/        # ThreadList, AgentDecisionPanel, DraftEditor, FeedbackControls
    hooks/             # useThreads, useThread (TanStack Query, 30s poll)
    lib/               # api.ts (typed fetch), types.ts
```

---

## API Routes (`/api/v1`)

```
POST /webhooks/email|sms|voicemail          → 202, triggers ingestion + agent
GET  /threads                               → paginated list (filter: status/priority/category)
GET  /threads/{id}                          → full detail: messages + decision + feedback history
POST /threads/{id}/run-agent               → manual agent trigger
PATCH /threads/{id}                         → admin override status/priority
GET  /threads/{id}/decisions               → decision history
GET  /decisions/{id}                        → single decision + few_shot_ids used
POST /threads/{id}/feedback                → approve / correct / override
GET  /feedback/similar?thread_id=&top_n=5 → similar past corrections
POST /threads/{id}/send-reply              → mark reply sent
POST /voice/inbound                         → ElevenLabs webhook → SSML briefing
GET  /voice/briefing-text                  → plain text briefing (testing)
GET  /health                               → liveness
GET  /admin/stats                          → counts by status/priority/category + avg latency
```

---

## Agent Tools

All tools are async functions in `app/services/tools.py` taking `(session, thread_id, **kwargs)` and returning a dict back to the model.

| Tool | Effect |
|---|---|
| `classify_and_set_category` | Sets `threads.category` + `threads.priority` |
| `group_messages` | Adds message IDs into the current thread |
| `draft_reply` | Stores draft in `agent_decisions.draft_reply` |
| `escalate` | Sets status=escalated, priority=urgent |
| `search_similar_threads` | pgvector ANN on `messages.embedding`, returns context |
| `mark_no_action` | Records decision with rationale, no reply |

**Adding a new tool**: implement the async function in `tools.py`, add its Anthropic schema dict to the `TOOLS` list in `agent.py`, write tests in `tests/test_agent.py` mocking the Anthropic response.

---

## Few-Shot Feedback Pipeline

How admin corrections improve future agent runs:

1. Admin submits correction via `POST /threads/{id}/feedback`
2. `submit_feedback()` persists the record and immediately generates + stores an embedding of the thread context
3. On the next agent invocation for any thread, `retrieve_similar_corrections()` runs:
   ```sql
   SELECT * FROM admin_feedback
   WHERE feedback_type IN ('corrected', 'overridden')
   ORDER BY embedding <=> $current_thread_embedding
   LIMIT $TOP_N_FEW_SHOT
   ```
4. Results are formatted as natural-language examples and injected into the system prompt's dynamic block
5. The IDs used are stored in `agent_decisions.few_shot_ids` for auditability

---

## Development Conventions

- **TDD**: write a failing test first, then implement. Tests live in `tests/` mirroring `app/`.
- **No real external calls in tests**: mock `anthropic.messages.create` and `generate_embedding()`.
- **One behavior per commit**: conventional commits (`feat:`, `fix:`, `test:`, `refactor:`).
- **Async everywhere**: all DB access uses `AsyncSession`; no sync SQLAlchemy calls.
- **Pydantic for all I/O**: request bodies and response shapes are always typed schemas.
- **Prompt caching**: the static system prompt prefix (role + property context) must always use `cache_control` to avoid re-billing on every agent call.

---

## Session Progress

Update this section at the start/end of each build session.

| Session | Scope | Status |
|---|---|---|
| 1 | DB, models, migrations | done |
| 2 | Ingestion, webhooks, thread grouping | done |
| 3 | Agent core, tools, prompt assembly | done |
| 4 | Feedback loop, reply sending | not started |
| 5 | Voice briefing + frontend UI | not started |
| 6 | Seed data, polish, demo hardening | not started |
