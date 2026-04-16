# Nava Real Estate Management

Demo systemu zarządzania nieruchomościami opartego na AI. Administrator otrzymuje 40–60 wiadomości dziennie (email, SMS, voicemail) od mieszkańców. System je pobiera, grupuje powiązane wiadomości w wątki, uruchamia agenta AI do klasyfikacji i działania (szkic odpowiedzi, eskalacja, brak akcji), i wyświetla wszystko w prostym panelu admina z pętlą feedbacku i możliwością briefingu głosowego.

## Wymagania

- Docker
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 18+
- Klucze API: `ANTHROPIC_API_KEY` i `OPENAI_API_KEY`

## Szybki start

```bash
# 1. Sklonuj i skonfiguruj
git clone <repo-url>
cd nava-real-estate-management
cp .env.example .env
# Uzupełnij .env — wpisz ANTHROPIC_API_KEY i OPENAI_API_KEY
```

Następnie uruchom wszystko jedną komendą:

```bash
docker-compose up -d && uv run alembic upgrade head && uv run python -m app.seed && uvicorn app.main:app --reload &
cd frontend && npm install && npm run dev
```

Panel admina będzie dostępny pod adresem **http://localhost:5173** z 16 wstępnie załadowanymi wiadomościami od mieszkańców, pogrupowanymi w wątki i przetworzonymi przez agenta.

---

## Co robi każdy krok

| Krok | Co się dzieje |
|---|---|
| `docker-compose up -d` | Uruchamia Postgres 16 z pgvector na porcie 5432 |
| `uv run alembic upgrade head` | Tworzy wszystkie tabele i enumy |
| `uv run python -m app.seed` | Ładuje 16 wiadomości z `data.csv`, grupuje je w wątki i uruchamia agenta AI na każdym |
| `uvicorn app.main:app --reload` | Backend API na porcie 8000 |
| `npm install && npm run dev` | Frontend na porcie 5173 |

---

## Zmienne środowiskowe

| Zmienna | Wymagana | Opis |
|---|---|---|
| `DATABASE_URL` | tak | `postgresql+asyncpg://nava:nava@localhost:5432/nava` (domyślne wartości z docker-compose) |
| `ANTHROPIC_API_KEY` | tak | Claude API — decyzje agenta i briefing głosowy |
| `OPENAI_API_KEY` | tak | Embeddingi do grupowania wątków i few-shot feedback |
| `ELEVENLABS_API_KEY` | nie | Voice inbound webhook (opcjonalne) |

---

## Architektura

```
webhook POST (email / SMS / voicemail)
  → ingestion: parsowanie + wykrycie nadawcy, pgvector similarity → znajdź lub utwórz wątek
  → background task: agent AI klasyfikuje, szkicuje odpowiedź lub eskaluje
  → admin przegląda w UI → zatwierdza lub koryguje
  → embedding korekty zapisany → poprawia przyszłe uruchomienia agenta (few-shot feedback loop)
```

**Stack**: FastAPI · PostgreSQL 16 + pgvector · SQLAlchemy async · Alembic · Claude (Anthropic) · OpenAI embeddings · Vite + React + TypeScript + Tailwind

---

## API

Base URL: `http://localhost:8000/api/v1`

```
GET  /threads                    # lista wątków z paginacją (filtr: status/priority/category)
GET  /threads/{id}               # szczegóły: wiadomości + decyzja agenta + historia feedbacku
POST /threads/{id}/run-agent     # ręczne uruchomienie agenta
POST /threads/{id}/feedback      # zatwierdź / koryguj / nadpisz decyzję agenta
POST /threads/{id}/send-reply    # oznacz odpowiedź jako wysłaną
GET  /admin/stats                # liczniki wg statusu, priorytetu, kategorii + średnie opóźnienie
GET  /health                     # liveness check
```

---

## Testy

```bash
# Wymaga TEST_DATABASE_URL w .env wskazującego na osobną bazę danych
uv run pytest --tb=short -q
```
