# Inverse

Adversarial legal research platform. Given a legal question, Inverse doesn't just find authority supporting a proposition — it researches everything capable of defeating it: opposition, distinctions, limitations, reversals, comparative doctrine, and the inverse proposition itself.

See [docs/architecture.md](docs/architecture.md) for the full design (schema, retrieval, agent orchestration, ingestion, MVP scope, roadmap).

## Repo layout

```
apps/
  api/        FastAPI backend — HTTP surface over research/, agents/, retrieval/
  web/        Next.js research workspace UI
agents/       LangGraph orchestrator + individual research agents
ingestion/    Source fetch -> parse -> extract -> embed -> index pipelines
retrieval/    Hybrid (keyword + vector + citation graph) retrieval toolkit
ranking/      Deterministic legal authority ranking + fact/legal similarity scoring
knowledge/    Postgres schema (SQLAlchemy models) + Alembic migrations
research/     Structured research-answer schema and session state
evaluation/   Gold-standard QA set + eval harness (citation precision/recall, similarity accuracy)
```

## MVP scope

US federal + a handful of pilot states. Sources: CourtListener (case law, `eyecite`/`courts-db` for citation extraction and court hierarchy), GovInfo (US Code, CFR, Federal Register), Congress.gov (legislative history), and user-uploaded documents. LLM + embeddings: OpenAI. See `docs/architecture.md` §7 for exact in/out-of-scope modes.

## Local development

Prerequisites: Python 3.11+, Node 20+, Docker (for Postgres + OpenSearch).

```bash
cp .env.example .env   # fill in OPENAI_API_KEY, COURTLISTENER_TOKEN, GOVINFO_API_KEY
docker compose up -d   # postgres + opensearch

pip install -e ".[dev]"
alembic -c knowledge/alembic.ini upgrade head
uvicorn apps.api.app.main:app --reload --port 8000

cd apps/web
npm install
npm run dev
```
