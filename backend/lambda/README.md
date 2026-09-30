# Lambda packaging (readiness only - not deployed by this repo)

Two Lambda functions share one codebase and one requirements file:

- **API Lambda** - `app.main_lambda.handler`, behind API Gateway. Wraps the same FastAPI app used locally (`app.main:app`) with [Mangum](https://mangum.io/).
- **Worker Lambda** - `app.workers.lambda_handler.handler`, triggered by an SQS event source mapping on the queue named by `INGESTION_QUEUE_URL`. Reuses `IngestionWorker.process_job`, the same ingestion logic as the local polling worker.

Neither is deployed, invoked, or given real credentials in this repository - see `DECISIONS.md` for why.

## Building a deployment package (manual, when you're ready)

```bash
cd backend
pip install -r lambda/requirements.txt -t lambda/package
cp -r app lambda/package/
cd lambda/package
zip -r ../function.zip .
```

Upload `function.zip` to each Lambda function, or push the same source to a container image and point each function at its own handler path. A deployment tool (SAM, CDK, Terraform, Serverless Framework) is not included here by design - wiring API Gateway, the SQS event source mapping, IAM roles, and environment variables is a deliberately deferred manual step. See the root README's [Manual integration & deployment](../../README.md#manual-integration--deployment) section.

## Configuration

Both functions read the same environment variables as local `Settings` (`backend/app/core/config.py`). Production-relevant ones:

- `DATABASE_URL` - a Supabase (or any managed) PostgreSQL connection string with pgvector enabled.
- `STORAGE_PROVIDER=s3`, `S3_BUCKET`, `AWS_REGION` - credentials are **not** set via env vars in production; the Lambda execution role's IAM permissions are used via the AWS SDK default credential chain (`boto3.client(...)` with no explicit keys - see `app/providers/storage/s3.py` and `app/providers/queue/sqs.py`).
- `INGESTION_QUEUE_URL` - the SQS queue URL. When set, `DocumentService.upload` publishes the new job's ID to this queue after committing it, so the worker Lambda runs immediately instead of a poller finding it later.
- `EMBEDDING_PROVIDER=gemini`, `GEMINI_API_KEY`, `GEMINI_EMBEDDING_MODEL` - avoids bundling the local sentence-transformers model (and torch) into the Lambda package.
- `GROQ_API_KEY` - unchanged from local development.

Required IAM permissions for the Lambda execution role (not created here): `s3:GetObject`/`PutObject`/`DeleteObject`/`HeadObject` on the bucket, `sqs:SendMessage` on the queue (API Lambda), `sqs:ReceiveMessage`/`DeleteMessage`/`GetQueueAttributes` on the queue (worker Lambda, usually granted automatically by the event source mapping).
