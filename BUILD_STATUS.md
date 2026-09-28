# Build Status

## Completed sessions

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

Authentication/authorization, cloud deployment, real AWS/S3/IAM, live Groq configuration, monitoring/tracing infrastructure (log-based observability only exists), cost monitoring, OCR, additional file formats, knowledge briefs, rate limiting, malware scanning, live-database validation of retry/stale-recovery logic, repository screenshots.

## Next state

**Code Complete — Manual Integration & Deployment.**

All planned local implementation work (S1–S4) is done and verified. What remains is not more code: it's a person supplying real credentials/infrastructure (cloud storage, a Groq key, a production database, a deployment target, auth) as described in the README's [Manual integration & deployment](README.md#manual-integration--deployment) section, then deploying.
