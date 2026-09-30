# Build Status

## Completed sessions

### ND-02 — Production-Demo UX + AWS Readiness

Two-part pass on top of the working S1–S4 implementation: stronger first-time-user feedback in the existing UI, and AWS production-topology code readiness (Lambda, SQS, S3, Gemini, Supabase-safe pooling). No RAG architecture changes, no UI redesign, no AWS resources created, no real credentials used.

**Delivered — UX**

- **Landing page** now leads with the exact flow (`Upload → Index → Ask → Verify citations`) in both the hero graphic (now 4 steps, not 3) and a new "How Nexora works" guided section, plus a primary CTA ("Upload your first document") straight into the Documents page.
- **Real ingestion progress, not a spinner:** `IngestionJob.stage` (`parsing`/`chunking`/`embedding`/`indexing`), written by the worker at each real step, shown on the document's status pill. No fake percentages anywhere.
- **Toasts** (`ToastProvider` in `layout.tsx`) for upload success/error and query error, alongside the existing inline errors.
- **Skeleton loading rows** for the initial document-list fetch, replacing a plain "Loading…" line.
- **Chat UX:** duplicate-submit guard on the question form, a reveal animation on the answer/source panels, and a "New here? Upload a document first" link for first-time visitors with nothing indexed yet.
- **Empty-state copy tightened** ("No documents yet — upload one above to get started") so a new visitor knows the next action without reading further.
- Subtle hover/entrance motion on buttons, document rows, source cards, and foundation rows - all covered by the existing global `prefers-reduced-motion` rule in `globals.css` (no new guards needed).

**Delivered — AWS readiness (code/config only)**

- **API Lambda:** `app/main_lambda.py` (`Mangum(app)`), wrapping the identical FastAPI app used locally - no route changes.
- **Worker Lambda:** `app/workers/lambda_handler.py`, an SQS event handler that calls a new `IngestionWorker.process_job(job_id)` - the same ingestion pipeline as the local poller (`process_next`), refactored to share one `_process_claimed_job` implementation.
- **SQS idempotency:** `DatabaseIngestionJobQueue.claim_job(job_id)` only claims a still-`queued` job; a redelivered SQS message for an already-claimed/finished job is a logged no-op, not a duplicate run or a silent failure.
- **Producer side:** `DocumentService.upload` publishes the new job's ID via an injected `IngestionJobPublisher` - `NoopJobPublisher` by default (unchanged local behavior), `SqsJobPublisher` when `INGESTION_QUEUE_URL` is set. A publish failure is logged loudly and never blocks the upload response.
- **S3 and SQS credentials:** both use the AWS SDK default credential chain when no explicit keys are configured - a Lambda execution role in production, never a committed key.
- **Gemini embedding provider:** `GeminiEmbeddingProvider` (`EMBEDDING_PROVIDER=gemini`), `output_dimensionality=384` to match the pinned vector column. Not exercised against a live API - flagged as such in code, docs, and here.
- **Serverless-safe DB pooling:** `app/db/session.py` switches to `NullPool` when `AWS_LAMBDA_FUNCTION_NAME` is present; local/dev pooling is unchanged.
- **Migration:** `0002_ingestion_stage` adds the nullable `ingestion_jobs.stage` column.
- **Minimal Lambda packaging:** `backend/lambda/requirements.txt` + `backend/lambda/README.md` - no SAM/CDK/Terraform/Serverless-Framework template, by design.
- **Docs:** README's "Manual integration & deployment" now names the concrete topology and exactly what a person must still provision; `docs/architecture.md` gained an "AWS production topology" section with its own diagram, kept separate from the primary local-implementation diagram.

**Tests:** 5 new backend tests (SQS idempotent `process_job`, Gemini provider key-required check, embedding-factory dispatch, upload→publisher wiring), plus the existing ingestion-worker stage assertions extended.

**Verification (last run)**

- Backend: 65 passed, 1 skipped. Ruff: clean. Alembic `upgrade head --sql` (offline) generates valid DDL for the new `stage` column.
- Frontend: lint clean, production build succeeded (4 routes), typecheck clean; smoke-tested via a local dev server (`/`, `/library`, `/chat` all return 200, new landing-page copy confirmed present in the rendered HTML).

**Could not be validated in this environment**

- The Lambda handlers, SQS publish/consume path, Gemini embedding calls, and Supabase `NullPool` behavior are none of them exercised against real AWS/Gemini/Supabase - by design, no credentials were available or used. Verified via unit tests against fakes/compiled SQL and local reasoning about the SDK/runtime contracts, not a live run.
- No screenshots of the new UX states were captured (same limitation as S4 - no browser-capture capability in this environment).

### S4 — Portfolio Polish / Deployment Readiness

Documentation, demo assets, and hygiene pass on top of the working S1–S3 implementation. No product features, architecture, or working UI behavior changed — only docs, a demo data package, portfolio-facing copy, and CI.

**Delivered in S4**

- **README rewritten** for a technical reader: what Nexora solves, architecture, the RAG pipeline, hybrid retrieval/RRF/reranking, evaluation (labeled as a fixture regression guard, not a production benchmark), observability/reliability/security summary, a table of contents, an explicit implemented-vs-deferred split, and a new "Manual integration & deployment" section listing exactly what a person still needs to configure (cloud storage, Groq key, production DB, deployment target, auth).
- **`docs/architecture.md` cleaned:** the "Current state" heading and the Mermaid diagram's "not implemented" bucket were stale — they still listed evaluation/observability as not-yet-built after S3 delivered both. Fixed to reflect current state; no architectural changes.
- **Demo package added:** `demo/sample-documents/` (four small synthetic HR/IT policy documents, not real organizational data) plus `demo/README.md`, a walkthrough of upload → ingestion → retrieval → grounded answer → citations with both UI steps and equivalent `curl` commands.
- **Portfolio-facing UI copy fixed** (text only, no layout/redesign): stale internal sprint labels ("Phase 1 foundation", "S2 · Functional MVP", "Foundation mode") replaced with accurate, audience-appropriate copy in `AppShell.tsx` and `app/page.tsx`.
- **CI fixed:** the frontend job ran `npm run typecheck` with no prior build step, which fails on a clean checkout (`Cannot find name 'LayoutProps'` — Next.js 16 generates route types during `build`/`dev`, not `typecheck`). Added a `npm run build` step before `typecheck` in `.github/workflows/ci.yml`.
- **Hygiene pass:** repo-wide scan for secrets, employer/internal terminology, and stale claims; fixed a leftover "Phase 1 foundation" project description in `backend/pyproject.toml` and the README's stale "evaluation/observability reserved for S3" line (both are now delivered).

**Verification (last run)**

- Backend: 60 passed, 1 skipped (no backend runtime code changed in S4; re-run to confirm no regression after the `pyproject.toml` description edit). Ruff: clean.
- Frontend: lint clean, typecheck clean, production build succeeded (4 routes) — re-run because UI copy changed.
- No secrets, employer/internal terminology, proprietary data, or fabricated metrics found. The evaluation number in the README/docs matches the actual last run of `python -m app.evaluation.run`.

**Could not be validated in this environment**

- Screenshots were not captured (no way to render/capture a real browser session here); the README's demo section documents how to add them.
- The CI fix (adding a build step before typecheck) was verified by reproducing the same failure/fix sequence locally, not by an actual GitHub Actions run.

### S3 — Production Proof / Hardening

Added evaluation, observability, reliability, and security/grounding depth on top of the working S2 MVP. No S1/S2 functionality was redesigned; the job-queue shape, retrieval pipeline, and UI are unchanged.

**Delivered in S3**

- **Evaluation:** `backend/app/evaluation/` — a deterministic, fully offline Recall@K/MRR check over a small synthetic fixture, run via `python -m app.evaluation.run` (no database, network, or credentials). Baseline on the fixture: Recall@3 = 1.000, MRR = 0.900 (5 queries), pinned as a regression guard in `tests/test_evaluation.py`.
- **Observability:** structured JSON request/job telemetry via `structlog` contextvars — an HTTP request ID (middleware in `app/main.py`, echoed as `X-Request-ID`) or ingestion job ID, plus latency, dense/lexical/fused retrieval counts, reranker usage, and (from the Groq provider, only when the API returns it) model name and token usage. No monitoring/tracing infrastructure was introduced.
- **Reliability:** ingestion jobs now retry on transient failure (requeued while `attempts < MAX_INGESTION_ATTEMPTS`, default 3) instead of failing on the first error, and jobs stuck `processing` from a crashed/killed worker are recovered after `INGESTION_STALE_AFTER_SECONDS` (default 600s). Both are plain conditional SQL updates layered onto the existing `SKIP LOCKED` queue — no new worker or scheduler.
- **Security/grounding:** PDF/DOCX uploads are now content-sniffed against real magic bytes, not just extension/MIME, rejecting mislabeled files. `KnowledgeQueryService` explicitly frames retrieved excerpts as untrusted data in both the prompt and system prompt and instructs the model to ignore embedded instructions; citations remain structurally bounded to actually-retrieved chunks regardless of model output (tested with an injected-instruction document chunk). Workspace isolation (already SQL- and cache-enforced) is exercised across dense, lexical, and hybrid layers in tests.
- **Tests:** 15 new backend tests (retry/stale-recovery, magic-byte validation, prompt-injection/citation-bounding, evaluation metrics and fixture regression).

**Verification (last run)**

- Backend: **60 passed, 1 skipped** (skipped = optional live PostgreSQL connectivity, requires `TEST_DATABASE_URL`). Ruff: clean.
- No frontend code changed in S3, so frontend lint/typecheck/build were not re-run (last verified clean at S2 closeout).
- No S1/S2 regressions.

**Could not be validated in this environment**

- Same as S2: Docker is unavailable, so no live PostgreSQL/pgvector run. Reliability logic (retry, stale-lock recovery) is proven by unit tests against compiled SQL and fakes, not a live crashed-worker scenario.
- The evaluation fixture measures retrieval-pipeline mechanics (dense+lexical fusion, ranking) using a dependency-free bag-of-words stand-in for the dense retriever, not production embedding quality with `sentence-transformers`.

### S2 — Functional MVP

The end-to-end knowledge path is implemented and tested locally.

**Working end-to-end**

upload → validation → local storage → parse (PDF/DOCX/TXT/MD) → chunk → embed → PostgreSQL/pgvector → dense + BM25 retrieval → RRF fusion → optional rerank → context assembly → grounded answer with citations → Documents and Knowledge Chat UI.

**Delivered in S2**

- Upload API with extension/MIME/size validation, filename sanitization, storage cleanup on database failure.
- Parsers for PDF, DOCX, TXT, Markdown; scanned PDFs rejected explicitly (no OCR).
- Deterministic chunker with configurable size/overlap and preserved location metadata.
- Ingestion worker process wired to the durable `SKIP LOCKED` job queue; atomic completion, useful failure messages.
- pgvector dense retriever, in-memory BM25 lexical retriever, RRF hybrid retriever, optional cross-encoder reranker (off by default).
- `KnowledgeQueryService` with application-constructed citations and stripping of model-invented source labels.
- API routes: `/documents` (upload/list/detail), `/query/retrieve`, `/query/answer`, `/workspaces/development`.
- Functional Documents and Knowledge Chat frontend pages replacing the S1 placeholders.
- Root context files: `PROJECT_CONTEXT.md`, `BUILD_STATUS.md`, `DECISIONS.md`.

**Verification (last run at S2 closeout)**

- Backend: 45 passed, 1 skipped. Ruff: clean. Alembic `upgrade head --sql` (offline) generates valid DDL with no errors.
- Frontend: lint clean, typecheck clean, production build succeeded (4 routes).
- Documents and Knowledge Chat pages confirmed to render at desktop/mobile widths with no overflow, and show an honest connection/config error instead of fabricated data when the API/database is unavailable.
- Docker is not installed in this environment, so live PostgreSQL/pgvector was unavailable; dense retrieval SQL and the Alembic baseline were validated by compiled-statement assertions and offline DDL generation.

## Not implemented

Authentication/authorization, actually provisioned AWS/Supabase resources (the Lambda/SQS/S3/Gemini/Supabase adapters exist in code and are unit-tested against fakes, but nothing has been created or deployed against real accounts), live Groq/Gemini configuration, monitoring/tracing infrastructure beyond structured logs, cost monitoring, OCR, additional file formats, knowledge briefs, rate limiting, malware scanning, live-database validation of retry/stale-recovery/SQS-idempotency logic, repository screenshots.

## Next state

**Code Complete — Manual Integration & Deployment.**

All planned local implementation work (S1–S4, ND-02) is done and verified, including AWS production-topology code readiness. What remains is not more code: it's a person supplying real credentials/infrastructure (cloud storage, an SQS queue, a Groq and/or Gemini key, a production database, a Lambda/API Gateway/Vercel deployment, auth) as described in the README's [Manual integration & deployment](README.md#manual-integration--deployment) section, then deploying.
