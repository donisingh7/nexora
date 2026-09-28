# Decisions

## Existing S1 decisions

- Use async FastAPI and SQLAlchemy with PostgreSQL as the source of truth.
- Use typed provider protocols; keep generation-provider choice independent from embeddings.
- Use database-backed ingestion jobs and PostgreSQL `SKIP LOCKED` instead of an in-memory authoritative queue.
- Default to local object storage. S3/Groq/model SDKs remain optional and are not required by tests.
- Keep the initial vector column at 384 dimensions. Any dimension change needs a migration and re-embedding.
- Workspace/User relationships are present, but S1 has no authentication or authorization.
- Do not commit secrets or employer/internal material.

## S2 constraints

- Build local functionality only; do not configure real AWS, S3, Groq credentials, or cloud deployment.
- Use PDF, DOCX, TXT, and Markdown only; no OCR or unsupported media types.
- PostgreSQL remains authoritative for documents/chunks/jobs. BM25 may be rebuilt in process memory.
- Use fake embeddings and fake LLM providers in automated tests; no model downloads or network calls in the default suite.
- A development workspace is convenience only, never an authorization claim.

## S2 decisions

- **Chunks and job finalization commit together.** The worker adds chunk rows and lets the durable queue's conditional `processing → completed` update own the commit, so a partially indexed document can never show `completed`.
- **Document status mirrors job status in the same transaction.** The UI reads authoritative status from PostgreSQL rather than inferring it from worker memory.
- **Existing chunks are deleted before reinsert.** Reprocessing a document is idempotent and cannot produce duplicate chunks.
- **BM25 lives in process memory, keyed by a workspace version tuple.** Accepted trade-off for the MVP: no extra service, but per-process and not suitable for very large corpora. Documented in `docs/architecture.md` as future work.
- **Dense and lexical retrieval run sequentially, not concurrently.** They share one `AsyncSession`, which does not support concurrent operations.
- **Workspace filtering is applied in SQL**, so cross-workspace rows are never fetched into the application.
- **Citations are built by application code from retrieved chunk metadata**, and unknown `[Sn]` labels emitted by the model are stripped. The model may reference only supplied sources.
- **Missing generation credentials return `503` with guidance**, not a crash; retrieval-only mode remains fully usable.
- **Reranking is opt-in and fails safe** to RRF ordering; it never blocks a query and downloads no model by default.
- **Upload errors are typed** (`415` unsupported type, `413` too large, `400` empty) rather than a single generic status.
- **Failed database writes delete the uploaded object** so storage does not accumulate orphans.
- **Heavy parsing/BM25 dependencies are core; vendor SDKs and model libraries stay optional** under the `providers` extra, keeping the default install and test suite lean and offline.

## S3 constraints

- Add production-proof depth (evaluation, observability, reliability, security hardening) without redesigning working S1/S2 functionality or the job-queue shape.
- No AWS/S3, Groq credentials, cloud deployment, Docker/Kubernetes work, or auth/SSO. No new product features or UI changes.
- Evaluation must run fully offline with no external APIs or credentials.

## S3 decisions

- **Retry before permanent failure.** A failed ingestion job is requeued (`status = queued`, error message preserved) rather than marked `failed` while `attempts < MAX_INGESTION_ATTEMPTS` (default 3). Only after exhausting attempts does it fail permanently. This reuses the existing status enum and `_finish` transition; no schema change.
- **Stale-lock recovery is a plain conditional `UPDATE`, not a scheduler.** `IngestionWorker.process_next` calls `recover_stale` before each claim, requeuing any `processing` job whose `locked_at` is older than `INGESTION_STALE_AFTER_SECONDS` (default 600s). No cron, no separate reaper process — consistent with the existing single-process worker design.
- **Telemetry rides on `structlog` contextvars already configured in S1**, not a new logging layer. HTTP requests get a request ID (from `X-Request-ID` or generated); ingestion jobs get a job ID. Both are bound for the duration of the operation so every nested log line inherits them automatically.
- **Token usage is logged only when a provider actually returns it.** The Groq provider reads `response.usage`; fields are `None`, never estimated or fabricated, when the API does not supply them.
- **Upload validation adds content sniffing, not a new validation layer.** PDF/DOCX uploads must start with their real magic bytes in addition to the existing extension+MIME check; TXT/Markdown have no reliable magic number and are left as before.
- **Retrieved document text is explicitly framed as untrusted data in both the system prompt and the context block.** This is a mitigation, not a guarantee — the real safety property is structural: citations are built by application code from the retrieved candidate list, never parsed from model output, so injected text in a document cannot fabricate a citation or misattribute one regardless of what the model does with it.
- **Evaluation uses a dependency-free bag-of-words stand-in for the dense retriever**, not the real embedding provider, so `python -m app.evaluation.run` needs no model download, network access, or credentials and stays runnable in the same environment as the test suite. It is explicitly documented as a proxy for exercising hybrid fusion, not a measure of production embedding quality.
