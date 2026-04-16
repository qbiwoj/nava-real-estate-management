# Nava Real Estate Management

AI-powered property management demo. An administrator receives 40–60 messages/day (email, SMS, voicemail) from residents. The system ingests them, groups related messages into threads, runs an AI agent to classify and act (draft reply, escalate, no-op), and surfaces everything in a minimal admin UI with a human feedback loop and voice briefing capability.

## Prerequisites

- Docker
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 18+
- API keys: `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`

## Quick Start

```bash
# 1. Clone and configure
git clone <repo-url>
cd nava-real-estate-management
cp .env.example .env
# Edit .env — fill in ANTHROPIC_API_KEY and OPENAI_API_KEY
```

Then run everything with one command:

```bash
docker-compose up -d && uv run alembic upgrade head && uv run python -m app.seed && uvicorn app.main:app --reload &
cd frontend && npm install && npm run dev
```

The admin UI will be available at **http://localhost:5173** with 16 pre-seeded resident messages already grouped into threads and processed by the agent.

---

## What each step does

| Step | What happens |
|---|---|
| `docker-compose up -d` | Starts Postgres 16 with pgvector on port 5432 |
| `uv run alembic upgrade head` | Creates all tables and enums |
| `uv run python -m app.seed` | Loads 16 real messages from `data.csv`, groups them into threads, runs the AI agent on each |
| `uvicorn app.main:app --reload` | Backend API on port 8000 |
| `npm install && npm run dev` | Frontend on port 5173 |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+asyncpg://nava:nava@localhost:5432/nava` (matches docker-compose defaults) |
| `ANTHROPIC_API_KEY` | yes | Claude API — agent decisions + voice briefing |
| `OPENAI_API_KEY` | yes | Embeddings for thread grouping and few-shot feedback |
| `ELEVENLABS_API_KEY` | no | Voice inbound webhook (optional) |

---

## Architecture

```
webhook POST (email / SMS / voicemail)
  → ingestion: parse + detect sender, pgvector similarity → find or create thread
  → background task: AI agent classifies, drafts reply, or escalates
  → admin reviews in UI → approves or corrects
  → correction embedding stored → improves future agent runs (few-shot feedback loop)
```

**Stack**: FastAPI · PostgreSQL 16 + pgvector · SQLAlchemy async · Alembic · Claude (Anthropic) · OpenAI embeddings · Vite + React + TypeScript + Tailwind

---

## API

Base URL: `http://localhost:8000/api/v1`

```
GET  /threads                    # paginated thread list (filter by status/priority/category)
GET  /threads/{id}               # full detail: messages + agent decision + feedback history
POST /threads/{id}/run-agent     # manually re-run the agent
POST /threads/{id}/feedback      # approve / correct / override agent decision
POST /threads/{id}/send-reply    # mark reply as sent
GET  /admin/stats                # counts by status, priority, category + avg latency
GET  /health                     # liveness check
```

---

## Running Tests

```bash
# Requires TEST_DATABASE_URL in .env pointing to a separate DB
uv run pytest --tb=short -q
```
