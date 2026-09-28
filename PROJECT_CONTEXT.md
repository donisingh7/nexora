# Project Context

## Product

Nexora is an independently built enterprise knowledge intelligence foundation. The repository is generic and clean-room: use only public, licensed, or explicitly authorized data, and do not introduce employer-specific schemas, terminology, prompts, source, or credentials.

## Current stack

- `frontend/`: Next.js App Router, TypeScript, React, lucide-react.
- `backend/`: Python 3.11+, FastAPI, Pydantic Settings, async SQLAlchemy, asyncpg, Alembic, pgvector.
- Storage adapters: local filesystem default and optional S3.
- Provider protocols: text generation, embeddings, and retrieval. Groq and sentence-transformers adapters are optional dependencies.
- PostgreSQL is the authoritative store. The initial embedding column is fixed at 384 dimensions.

## Existing contracts (after S3)

- Health endpoints at `/health`, `/ready`, and `/api/v1` aliases.
- Document APIs: `POST /api/v1/documents` (upload), `GET /api/v1/documents`, `GET /api/v1/documents/{id}`.
- Query APIs: `POST /api/v1/query/retrieve` (no LLM key needed), `POST /api/v1/query/answer`.
- Development workspace: `GET /api/v1/workspaces/development`.
- Workspace, User, Document, DocumentChunk, IngestionJob models in `backend/app/models/`.
- `DatabaseIngestionJobQueue` claims jobs using PostgreSQL `FOR UPDATE SKIP LOCKED`; finalization is conditional on `processing` and updates document status in the same transaction.
- `IngestionWorker` (`backend/app/services/ingestion.py`) runs via `python -m app.workers.run_ingestion`.
- Retrieval in `backend/app/retrieval/`: `dense.py` (pgvector), `lexical.py` (BM25), `hybrid.py` (RRF), `reranking.py` (optional, off by default).
- `KnowledgeQueryService` (`backend/app/services/knowledge_query.py`) orchestrates retrieval → context → generation → citations. Retrieved excerpts are framed as untrusted data in both the prompt and system prompt; citations are built only from actually-retrieved candidates, never from model output.
- Provider protocols in `backend/app/providers/`. Groq and sentence-transformers are optional `providers` extras.
- Authentication is not implemented. The development workspace is not an authorization boundary.
- Ingestion jobs retry on transient failure (`MAX_INGESTION_ATTEMPTS`, default 3) before failing permanently, and stale `processing` jobs (crashed worker) are recovered after `INGESTION_STALE_AFTER_SECONDS` (default 600s) — both in `backend/app/services/ingestion_jobs.py` / `ingestion.py`.
- Structured JSON logging (`structlog`) carries a request ID (HTTP, via middleware in `backend/app/main.py`) or job ID (ingestion worker) through contextvars, plus latency, retrieval counts, and provider/token metadata when available.
- Upload validation sniffs content against real magic bytes for PDF/DOCX, not just extension/MIME, in `backend/app/services/documents.py`.
- `backend/app/evaluation/` runs a deterministic, offline Recall@K/MRR check over a small fixture via `python -m app.evaluation.run` (from `backend/`).

## Local commands

- Backend install: `python -m pip install -e "backend[dev]"`
- Provider dependencies for real embeddings: `python -m pip install -e "backend[providers]"`
- Backend tests/lint from `backend/`: `python -m pytest -q`, `python -m ruff check app tests alembic`
- Ingestion worker from `backend/`: `python -m app.workers.run_ingestion`
- Retrieval evaluation from `backend/` (offline, no credentials): `python -m app.evaluation.run`
- Frontend from `frontend/`: `npm ci`, `npm run dev`, `npm run lint`, `npm run typecheck`, `npm run build`
- Local database stack: copy `.env.example` to `.env`, then `docker compose up --build`.

## Demo assets

`demo/sample-documents/` holds four small synthetic Markdown policy documents (generic HR/IT content, not real organizational data) with a walkthrough in `demo/README.md` covering upload → ingestion → retrieval → grounded answer → citations, including equivalent `curl` commands.

Keep this document aligned with the current implementation, not future claims.
