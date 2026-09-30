# Nexora — Enterprise Knowledge Intelligence

Nexora turns a pile of documents into answers you can trust: upload PDFs, Word docs, or Markdown; ask a question in plain language; get back an answer with citations pointing at the exact source passages it came from. It's a clean-room, from-scratch implementation of a production-shaped retrieval-augmented-generation (RAG) system — hybrid retrieval, grounded generation, structured citations, evaluation, and the observability/reliability/security work that separates a demo from something you could actually run.

This repository contains no employer-specific schemas, data, prompts, or source code. Everything here — architecture, code, and sample data — was built independently from generic product requirements.

**Status:** S1–S4 are code-complete and verified locally (backend: 65 tests passing, 1 optional live-DB test skipped; frontend: lint/typecheck/build clean). What's left is manual integration — wiring up real cloud credentials and deploying — described in [Manual integration & deployment](#manual-integration--deployment) below.

## Table of contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [The RAG pipeline](#the-rag-pipeline)
- [Hybrid retrieval and reranking](#hybrid-retrieval-and-reranking)
- [Evaluation](#retrieval-evaluation)
- [Observability, reliability, and security](#observability-reliability-and-security)
- [Demo](#demo)
- [Local setup](#local-setup)
- [Environment variables](#environment-variables)
- [Tests and checks](#tests-and-checks)
- [Implemented vs. deferred](#implemented-vs-deferred)
- [Manual integration & deployment](#manual-integration--deployment)
- [Clean-room and public-data principle](#clean-room-and-public-data-principle)

## What it does

1. **Upload** a document (PDF, DOCX, TXT, or Markdown).
2. Nexora **parses, chunks, and embeds** it, then indexes it for both semantic (vector) and keyword (BM25) search.
3. **Ask a question.** Nexora retrieves the most relevant passages using hybrid search, optionally reranks them, and either returns the raw ranked passages (no LLM required) or asks a language model to answer *using only those passages*.
4. Every answer comes back with **structured citations** — the exact document, page/location, and excerpt each claim is grounded in — built by application code from what was actually retrieved, not parsed out of the model's free-text output.

## Architecture

- **Frontend:** Next.js App Router, TypeScript — a Documents page (upload + ingestion status) and a Knowledge Chat page (retrieval-only and grounded-answer modes).
- **API:** Python, FastAPI, Pydantic Settings, async SQLAlchemy.
- **Database:** PostgreSQL with pgvector; Alembic migrations. The embedding column is fixed at 384 dimensions.
- **Storage:** an `ObjectStorage` protocol with a local-filesystem adapter (default) and an S3 adapter, ready for a production bucket (see [Manual integration & deployment](#manual-integration--deployment)).
- **Generation/embeddings:** independent provider protocols so the LLM and embedding backends can be swapped without touching retrieval or orchestration code. Groq (generation), sentence-transformers (local embeddings), and Gemini (serverless-friendly embeddings) are optional dependencies, not hard requirements.
- **Ingestion worker:** a plain Python process that claims jobs from a durable PostgreSQL queue by polling (`app.workers.run_ingestion`) — no Redis, Celery, or Kafka. An equivalent push-based worker Lambda (`app.workers.lambda_handler`) reuses the identical ingestion logic when a job is delivered by SQS instead.

See [docs/architecture.md](docs/architecture.md) for the full component diagram and the trade-offs behind each layer (ingestion, retrieval, grounding, security, observability, reliability).

## The RAG pipeline

Implemented end to end, exercised by both the automated test suite and the [demo walkthrough](demo/README.md):

```
upload → validate + sanitize → local object storage
       → parse (PDF / DOCX / TXT / Markdown)
       → chunk (deterministic, configurable size/overlap)
       → embed
       → index (pgvector dense + in-process BM25 lexical)

question → dense search + BM25 search → Reciprocal Rank Fusion
         → optional cross-encoder rerank
         → [retrieval-only: return ranked passages]
         → [grounded: assemble context → generate → strip invented citations] → answer + citations
```

Ingestion runs in a separate worker process that claims jobs from PostgreSQL with `FOR UPDATE SKIP LOCKED`; chunk rows and the job's terminal status commit together, so a document can never show `completed` while only partially indexed. The worker also records which step it's on (`parsing` / `chunking` / `embedding` / `indexing`) so the UI can show real progress instead of a generic spinner — this is feedback only, never used to decide correctness. See [Observability, reliability, and security](#observability-reliability-and-security) for what happens when a job fails or a worker crashes mid-job.

## Hybrid retrieval and reranking

Neither pure vector search nor pure keyword search is reliably best on its own, so Nexora runs both and fuses the results:

- **Dense retrieval** — pgvector cosine similarity over chunk embeddings, filtered to the requesting workspace and completed documents in a single SQL statement.
- **Lexical retrieval** — BM25 (via `rank-bm25`) over the same authoritative chunk text, indexed in process memory per workspace and invalidated automatically when a workspace's documents change.
- **Fusion** — Reciprocal Rank Fusion (RRF) combines the two ranked lists: `score = Σ 1/(k + rank)` across whichever lists a chunk appears in, so a passage found by both methods outranks one found by only one. Component scores (dense, BM25, fused) are preserved and shown in both the API response and the UI.
- **Reranking (optional, off by default)** — a cross-encoder can reorder the fused results for higher precision. It's disabled unless `RERANKER_ENABLED=true`, and any failure or missing model falls back to the RRF order rather than breaking the query.

## Retrieval evaluation

`python -m app.evaluation.run` (from `backend/`, no database/network/credentials required) runs the real hybrid retriever against a small, deterministic, synthetic fixture and reports Recall@K and MRR.

> **Recall@3 = 1.000, MRR = 0.900 on the included deterministic 5-query local evaluation fixture.**

This is a regression guard on retrieval mechanics (pinned in `tests/test_evaluation.py`), **not a production benchmark** — the fixture is five short synthetic documents and five queries, and the dense side uses a dependency-free bag-of-words scorer standing in for the real embedding model so the script stays runnable offline. Details and rationale: [docs/architecture.md#evaluation](docs/architecture.md#evaluation).

## Observability, reliability, and security

- **Observability:** structured JSON logs (`structlog`) carry a request ID (HTTP, via middleware) or job ID (ingestion worker) through every nested log line, plus latency, retrieval candidate counts, and — only when a provider actually returns it — model name and token usage. No monitoring/tracing stack was introduced; this is log-based observability sized for the current scope.
- **Reliability:** ingestion jobs retry automatically on transient failure (`MAX_INGESTION_ATTEMPTS`, default 3) before failing permanently, and a job left `processing` by a crashed or killed worker is recovered after `INGESTION_STALE_AFTER_SECONDS` (default 600s) — both as plain conditional SQL updates on the existing job queue, no new infrastructure.
- **Security/grounding:** uploads are content-sniffed against real magic bytes for PDF/DOCX (not just extension/MIME), so a mislabeled file is rejected. Retrieved document text is explicitly framed as **untrusted data, not instructions** in both the prompt and system prompt; structurally, citations are always built by application code from the actual retrieved chunks, never parsed from model output, so injected text in a document cannot fabricate a source or misattribute one. Workspace isolation is enforced in SQL (dense), in the per-workspace lexical cache (BM25), and tested at both layers.

Full detail, including exactly what's logged and why each mechanism is shaped the way it is: [docs/architecture.md](docs/architecture.md).

## Demo

[`demo/`](demo/) contains four small synthetic Markdown documents (generic HR/IT policy text — not real organizational data) and a [walkthrough](demo/README.md) covering upload → ingestion → retrieval → grounded answer → citations, with both UI steps and equivalent `curl` commands.

### Screenshots

Not included in this repository yet. To add them: run through the [demo walkthrough](demo/README.md), capture the Documents page (upload + status) and Knowledge Chat page (a retrieval result and a grounded answer with citations) at both desktop and mobile widths, and drop them in a `docs/screenshots/` folder referenced from here.

## Local setup

Prerequisites: Docker Desktop with Compose (or a local PostgreSQL 16 with pgvector), Node.js 20+, Python 3.11+.

1. Copy `.env.example` to `.env` and replace the local database password.
2. Start PostgreSQL and the API:

   ```powershell
   docker compose up --build
   ```

3. Install the local embedding provider (needed for real ingestion and retrieval):

   ```powershell
   python -m pip install -e "backend[providers]"
   ```

4. Run the ingestion worker in its own terminal:

   ```powershell
   Push-Location backend
   python -m app.workers.run_ingestion
   Pop-Location
   ```

5. Start the frontend:

   ```powershell
   Push-Location frontend
   npm ci
   npm run dev
   Pop-Location
   ```

Open `http://localhost:3000`. Upload a document on the Documents page, wait for status `completed`, then use Knowledge Chat — or skip straight to the [demo walkthrough](demo/README.md) for sample data and example questions. **Retrieval-only mode works without any LLM key**; grounded answers require `GROQ_API_KEY`.

## Environment variables

`.env.example` is the safe starting point. Core: `DATABASE_URL`, `ENVIRONMENT`, `LOG_LEVEL`, `CORS_ORIGINS`, `STORAGE_PROVIDER`, `LOCAL_STORAGE_PATH`, `MAX_UPLOAD_SIZE_BYTES`, `ALLOWED_UPLOAD_MIME_TYPES`. Ingestion/retrieval: `CHUNK_SIZE_CHARS`, `CHUNK_OVERLAP_CHARS`, `DENSE_CANDIDATE_COUNT`, `LEXICAL_CANDIDATE_COUNT`, `DEFAULT_RETRIEVAL_TOP_K`, `RRF_CONSTANT`, `RERANKER_ENABLED`, `RERANKER_MODEL`, `MAX_INGESTION_ATTEMPTS`, `INGESTION_STALE_AFTER_SECONDS`, `INGESTION_QUEUE_URL` (optional SQS queue; unset = local polling worker only). Providers (all optional, unset by default): `S3_BUCKET`/`AWS_REGION`/AWS credential chain, `GROQ_API_KEY`/`GROQ_MODEL`, `EMBEDDING_PROVIDER` (`sentence_transformers` default or `gemini`), `EMBEDDING_MODEL`/`EMBEDDING_DIMENSIONS` (pinned to 384; changing it requires a migration and re-embedding), `GEMINI_API_KEY`/`GEMINI_EMBEDDING_MODEL`. The frontend reads `NEXT_PUBLIC_NEXORA_API` (defaults to `http://localhost:8000/api/v1`).

Keep real secrets in an untracked `.env` or a managed secret store. No credentials are committed — `.env.example` contains only placeholder values.

## Tests and checks

```powershell
python -m pip install -e "backend[dev]"
Push-Location backend
python -m pytest -q
python -m ruff check app tests alembic
Pop-Location
Push-Location frontend
npm ci
npm run lint
npm run build
npm run typecheck
Pop-Location
```

The default suite requires no AWS, S3, Groq, model downloads, or internet access; external providers are replaced with fakes and mocks. `TEST_DATABASE_URL` enables an optional live PostgreSQL connectivity check (also how CI runs it, against a `pgvector/pgvector` service container).

Run `npm run build` before a standalone `npm run typecheck` on a fresh checkout: Next.js 16 generates route types under `.next/types` during `build`/`dev`, and `typecheck` alone will fail with `Cannot find name 'LayoutProps'` until that exists. This is a tooling ordering quirk, not an application bug — CI is ordered this way already.

## Implemented vs. deferred

**Implemented**

- Document upload with extension/MIME/magic-byte validation, size limits, filename sanitization, and storage cleanup on database failure.
- Durable ingestion: PDF/DOCX/TXT/Markdown parsing, deterministic chunking, embedding, retry on transient failure, and recovery of jobs orphaned by a crashed worker.
- Hybrid retrieval (dense + BM25 + RRF) with optional reranking, all workspace-scoped.
- Grounded QA with application-constructed citations and prompt-injection-aware framing of retrieved text.
- A deterministic offline retrieval evaluation fixture.
- Structured request/job telemetry (latency, retrieval counts, provider/token metadata), including per-job ingestion stage for UI progress.
- AWS production-topology **code readiness**: a Mangum Lambda handler for the API, an SQS-triggered worker Lambda reusing the same ingestion logic, an idempotent "claim one specific job" path for at-least-once SQS delivery, S3 storage via the AWS SDK default credential chain, a Gemini embedding provider, and serverless-safe DB pooling — all present in code, none deployed or exercised against real AWS (see [Manual integration & deployment](#manual-integration--deployment)).
- Functional Documents and Knowledge Chat UI with upload/ingestion progress feedback, toasts, skeleton loading states, and a guided "how it works" walkthrough; backend test suite (65 tests), CI (backend + frontend).

**Deferred — requires manual configuration, deliberately out of scope for this phase**

- Authentication and authorization. The development workspace is a convenience, **not** a security boundary — do not expose this API publicly as-is.
- Actually provisioning cloud resources: a real S3 bucket, SQS queue, Lambda functions, API Gateway, IAM roles, a domain, or Supabase project. The code that would use them exists; nothing has been created or deployed.
- A configured Groq or Gemini API key (retrieval-only mode and the local embedding provider need neither).
- Monitoring/tracing infrastructure beyond structured logs, cost monitoring, rate limiting, malware scanning.
- OCR, additional file formats (PPTX, spreadsheets, images), web crawling, structured knowledge briefs, document deletion UI, multi-tenant hardening.

## Manual integration & deployment

Everything above runs locally without any of the following. The target production topology this codebase is *ready* for — not deployed, not configured with real credentials here:

```
Vercel (Next.js frontend)
   → API Gateway → AWS Lambda (FastAPI via Mangum)  [app.main_lambda:handler]
   → Supabase PostgreSQL + pgvector                  [DATABASE_URL]
   → private S3 bucket for uploaded files             [STORAGE_PROVIDER=s3]
   → SQS queue → separate worker Lambda               [app.workers.lambda_handler:handler]
```

To take Nexora further, a person (not this repository) needs to supply and configure:

- **Cloud storage:** a private S3 bucket. Set `STORAGE_PROVIDER=s3`, `S3_BUCKET`, `AWS_REGION`. No access keys belong in configuration in production — `S3StorageProvider` and `SqsJobPublisher` both call `boto3` with no explicit credentials, so they resolve through the AWS SDK's default credential chain (a Lambda execution role's IAM permissions). `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` remain available for non-Lambda/local testing only.
- **A push-based ingestion queue (optional):** an SQS queue, with its URL set as `INGESTION_QUEUE_URL`. When set, each upload publishes the new job's ID to it so the worker Lambda runs immediately; when unset (the default), nothing changes — the local polling worker keeps working exactly as before. SQS delivers at-least-once; `IngestionWorker.process_job` claims a job only if it's still `queued`, so a redelivered message for an already-claimed or finished job is a safe no-op, not a duplicate run.
- **A generation provider:** a Groq API key (`GROQ_API_KEY`) for grounded answers. Retrieval-only mode requires nothing here.
- **An embedding provider for serverless:** set `EMBEDDING_PROVIDER=gemini` and `GEMINI_API_KEY` to avoid bundling sentence-transformers/torch into a Lambda package. Not exercised against a live API in this repository — see [DECISIONS.md](DECISIONS.md).
- **A production database:** a managed PostgreSQL instance with pgvector enabled, reachable via `DATABASE_URL` (Supabase is the intended target; any pgvector-enabled Postgres works). Run `alembic upgrade head` against it. `app/db/session.py` automatically disables connection pooling when it detects a Lambda runtime, which is what a serverless connection model expects.
- **Deployment target:** package and deploy the two Lambda functions per `backend/lambda/README.md` (a manual, tool-agnostic process — no SAM/CDK/Terraform template is included by design), wire up API Gateway and the SQS event source mapping, and deploy the frontend to Vercel with `NEXT_PUBLIC_NEXORA_API` pointed at the API Gateway URL.
- **Authentication/SSO:** none exists yet; the API must sit behind an auth layer (or stay internal-only) before any real user data touches it.

None of the above is provisioned or tested against real AWS in this repository by design — see [DECISIONS.md](DECISIONS.md) for the constraints each session operated under.

## Clean-room and public-data principle

Nexora is independently implemented from generic product requirements. Use only public, licensed, or explicitly authorized material for sample data, fixtures, prompts, or integrations. Do not import private employer data, proprietary prompts, internal schemas, credentials, or implementation artifacts.
