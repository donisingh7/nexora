# Demo walkthrough

Four small, synthetic Markdown documents in [`sample-documents/`](sample-documents/) exercise the full flow end to end: **upload → ingestion → hybrid retrieval → grounded answer → citations**. They are invented generic HR/IT policy text written for this demo — not real organizational, employer, or customer data.

Prerequisites: the local stack is running per the root [README's Local setup](../README.md#local-setup) (PostgreSQL with pgvector, the API, the ingestion worker, and the frontend).

## 1. Upload the sample documents

**Using the UI:** open `http://localhost:3000/library` and upload each file in `sample-documents/` through the "Add a document" form. Wait for each row's status to reach `completed` (the ingestion worker parses, chunks, and embeds it).

**Using the API directly** (from the repo root, one call per file):

```bash
curl -F "file=@demo/sample-documents/remote-work-policy.md" http://localhost:8000/api/v1/documents
curl -F "file=@demo/sample-documents/travel-expense-policy.md" http://localhost:8000/api/v1/documents
curl -F "file=@demo/sample-documents/data-security-guidelines.md" http://localhost:8000/api/v1/documents
curl -F "file=@demo/sample-documents/onboarding-checklist.md" http://localhost:8000/api/v1/documents
curl http://localhost:8000/api/v1/documents  # poll until every "status" is "completed"
```

## 2. Ask questions — retrieval only (no LLM key needed)

Retrieval-only mode exercises dense + BM25 + RRF fusion without any generation provider. In the UI, open `http://localhost:3000/chat`, switch to **Retrieval only**, and try:

- "How many days per week qualify for the home office stipend?" → `remote-work-policy.md`
- "How long do I have to submit an expense report?" → `travel-expense-policy.md`
- "What is the required screen lock timeout?" → `data-security-guidelines.md`
- "When must benefits enrollment be completed?" → `onboarding-checklist.md`

Or via the API:

```bash
curl -X POST http://localhost:8000/api/v1/query/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "How long do I have to submit an expense report?", "top_k": 5}'
```

Each result includes the source filename, dense/BM25/fused scores, and the matched excerpt.

## 3. Ask questions — grounded answer (requires `GROQ_API_KEY`)

With a Groq API key configured (see the root README's environment variables section — **not required for the rest of this demo**), switch to **Grounded answer** and ask the same questions. The response includes an answer plus a structured citation list built from the actually-retrieved chunks (`[S1]`, `[S2]`, …).

```bash
curl -X POST http://localhost:8000/api/v1/query/answer \
  -H "Content-Type: application/json" \
  -d '{"query": "How long do I have to submit an expense report?", "top_k": 5}'
```

Without a configured key, this endpoint returns `503` with a message directing you back to retrieval-only mode — an honest error, not a fabricated answer.

## What this does and does not demonstrate

This walkthrough proves the pipeline is wired correctly end to end on a small corpus. It is not a benchmark of retrieval quality — for a quantitative (if small) measure of hybrid retrieval, see the [Retrieval evaluation](../README.md#retrieval-evaluation) section of the root README.
