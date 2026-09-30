import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import Document
from app.models.enums import IngestionStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    filename: str
    mime_type: str
    size_bytes: int
    status: IngestionStatus
    created_at: datetime | None
    updated_at: datetime | None
    ingestion_error: str | None = None
    ingestion_stage: str | None = None

    @classmethod
    def from_model(cls, document: Document) -> "DocumentRead":
        jobs = document.__dict__.get("ingestion_jobs", [])
        latest_job = max(
            jobs,
            key=lambda job: job.created_at.isoformat() if job.created_at else "",
            default=None,
        )
        return cls(
            id=document.id,
            workspace_id=document.workspace_id,
            filename=document.filename,
            mime_type=document.mime_type,
            size_bytes=document.size_bytes,
            status=document.status,
            created_at=document.created_at,
            updated_at=document.updated_at,
            ingestion_error=latest_job.error_message if latest_job else None,
            ingestion_stage=latest_job.stage if latest_job else None,
        )


class WorkspaceRead(BaseModel):
    id: uuid.UUID
    name: str
    mode: str = "development"
