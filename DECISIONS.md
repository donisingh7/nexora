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

## ND-02 constraints (production-demo UX + AWS readiness)

- Improve UX feedback/loading/onboarding within the existing design language; do not replace it with a generic dashboard or redesign the RAG architecture.
- No fake progress percentages; only real, worker-reported stages.
- Implement AWS code/config readiness (Lambda, SQS, S3, Gemini, Supabase-safe DB pooling) without creating AWS resources or using real credentials.
- Preserve local development exactly as-is: every new adapter is additive and opt-in via configuration, never a replacement the local path depends on.
- SQS delivers at-least-once; ingestion must stay idempotent under redelivery. No silently swallowed ingestion failures.
- No Docker/Kubernetes/Terraform work, no auth/SSO, no new product features.

## ND-02 decisions

- **Ingestion progress is a `stage` column on the job row, not a percentage.** The worker writes `parsing`/`chunking`/`embedding`/`indexing` via `update_stage()`, a small commit guarded to `status = 'processing'` at each of the four real steps. It is advisory UI state only; `status` (`queued`/`processing`/`completed`/`failed`) remains the sole correctness signal, unchanged from S2.
- **The SQS worker path reuses the same `IngestionWorker`, not a parallel implementation.** `process_next` (poll: claim whatever's queued) and `process_job(job_id)` (push: claim one named job) both delegate to a shared `_process_claimed_job`, so parsing/chunking/embedding/retry/stage logic exists exactly once regardless of which Lambda or process calls it.
- **SQS idempotency is enforced by the claim, not by deduplication logic.** `claim_job(job_id)` only succeeds if the job is still `queued`; a redelivered message for an already-claimed or finished job finds nothing to claim and is logged as a no-op. No message-ID tracking table was added - the job's own status is the dedupe key.
- **Publishing to SQS is best-effort and never blocks or fails the upload.** The database row is the durable source of truth (unchanged from S1/S2); a publish failure is logged loudly (`logger.exception`), not swallowed, but the HTTP response still succeeds, since local/poll-based workers do not depend on the publish at all and a push-only deployment already has the durable row to fall back on once whatever's wrong with SQS is fixed.
- **A `NoopJobPublisher` is the default, matching the existing provider-protocol pattern** (`ObjectStorage`, `EmbeddingProvider`, `TextGenerationProvider`) rather than an `if settings.ingestion_queue_url` branch inside `DocumentService`. `create_job_publisher()` picks `SqsJobPublisher` only when `INGESTION_QUEUE_URL` is set.
- **Gemini embeddings are implemented against the published SDK shape but not verified against a live API** in this repository (no key available, none requested). Documented as such in code and docs, consistent with how the Groq provider was already treated - a real key is required before relying on it in production.
- **No AWS credentials, SAM/CDK/Terraform templates, or actual resource provisioning were created.** `backend/lambda/` contains only a requirements file and a manual packaging README; wiring API Gateway, the SQS event source mapping, and IAM policies is an explicitly deferred manual step.
- **Toasts, skeleton loaders, and reveal animations reuse existing CSS custom properties, keyframes, and component classes** (the forest/mint/coral palette, the existing `reveal`/`spin` keyframes, `.primary-button`) rather than introducing a UI library or a new visual language. The global `prefers-reduced-motion` rule already in `globals.css` covers all new animations without additional guards.
