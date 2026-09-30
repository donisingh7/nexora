"""AWS Lambda entry point for the API, via API Gateway.

Not used for local development (`uvicorn app.main:app` / `docker compose` serve the
same `app.main:app` FastAPI instance directly). This module only adapts that app to
the Lambda/API Gateway event format.

Packaging: install `nexora-backend[aws]` (adds `mangum`) into the Lambda deployment
package - see `backend/lambda/README.md`. Not deployed or invoked in this repository.
"""

from mangum import Mangum

from app.main import app

handler = Mangum(app)
