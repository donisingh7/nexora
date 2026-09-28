import uuid
from pathlib import PurePath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.security import sanitize_filename
from app.models.document import Document
from app.models.enums import IngestionStatus
from app.models.ingestion_job import IngestionJob
from app.providers.storage.interface import ObjectStorage
from app.schemas.documents import DocumentRead
from app.services.workspaces import DEFAULT_DEVELOPMENT_WORKSPACE_ID

SUPPORTED_MIME_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain", "text/x-markdown"},
    ".markdown": {"text/markdown", "text/plain", "text/x-markdown"},
}

# Content sniffing for formats with a reliable magic number, so a renamed or
# mislabeled file cannot pass validation on extension/MIME claims alone.
_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF-",),
    ".docx": (b"PK\x03\x04",),
}


class UploadValidationError(ValueError):
    status_code = 400


class UnsupportedUploadTypeError(UploadValidationError):
    status_code = 415


class UploadTooLargeError(UploadValidationError):
    status_code = 413


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        storage: ObjectStorage,
        settings: Settings,
    ) -> None:
        self._session = session
        self._storage = storage
        self._settings = settings

    def validate_upload(self, filename: str, content_type: str, content: bytes) -> str:
        safe_filename = sanitize_filename(filename)
        extension = PurePath(safe_filename).suffix.lower()
        accepted_types = SUPPORTED_MIME_TYPES.get(extension)
        if accepted_types is None:
            raise UnsupportedUploadTypeError(
                "Supported formats are PDF, DOCX, TXT, and Markdown"
            )
        normalized_type = content_type.split(";", maxsplit=1)[0].strip().lower()
        allowed = {item.lower() for item in self._settings.allowed_upload_mime_types}
        if normalized_type not in accepted_types or normalized_type not in allowed:
            raise UnsupportedUploadTypeError(
                "File extension and MIME type are not supported together"
            )
        if not content:
            raise UploadValidationError("The uploaded file is empty")
        magic_signatures = _MAGIC_BYTES.get(extension)
        if magic_signatures is not None and not content.startswith(magic_signatures):
            raise UnsupportedUploadTypeError(
                "File content does not match its declared type"
            )
        if len(content) > self._settings.max_upload_size_bytes:
            raise UploadTooLargeError(
                f"File exceeds the {self._settings.max_upload_size_bytes} byte upload limit"
            )
        return safe_filename

    async def upload(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
        workspace_id: uuid.UUID = DEFAULT_DEVELOPMENT_WORKSPACE_ID,
    ) -> DocumentRead:
        safe_filename = self.validate_upload(filename, content_type, content)
        normalized_type = content_type.split(";", maxsplit=1)[0].strip().lower()
        document_id = uuid.uuid4()
        storage_key = f"{workspace_id}/{document_id}/{safe_filename}"
        await self._storage.upload(storage_key, content, normalized_type)

        document = Document(
            id=document_id,
            workspace_id=workspace_id,
            filename=safe_filename,
            storage_key=storage_key,
            mime_type=normalized_type,
            size_bytes=len(content),
            status=IngestionStatus.QUEUED.value,
        )
        job = IngestionJob(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            document_id=document_id,
            status=IngestionStatus.QUEUED.value,
        )
        self._session.add_all([document, job])
        try:
            await self._session.commit()
            await self._session.refresh(document)
        except Exception:
            await self._session.rollback()
            try:
                await self._storage.delete(storage_key)
            except Exception:
                pass
            raise
        return DocumentRead.from_model(document)

    async def list_documents(
        self, workspace_id: uuid.UUID = DEFAULT_DEVELOPMENT_WORKSPACE_ID
    ) -> list[DocumentRead]:
        statement = (
            select(Document)
            .options(selectinload(Document.ingestion_jobs))
            .where(Document.workspace_id == workspace_id)
            .order_by(Document.created_at.desc(), Document.id)
        )
        result = await self._session.scalars(statement)
        return [DocumentRead.from_model(document) for document in result.all()]

    async def get_document(
        self,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID = DEFAULT_DEVELOPMENT_WORKSPACE_ID,
    ) -> DocumentRead | None:
        statement = (
            select(Document)
            .options(selectinload(Document.ingestion_jobs))
            .where(Document.id == document_id, Document.workspace_id == workspace_id)
        )
        document = await self._session.scalar(statement)
        return DocumentRead.from_model(document) if document is not None else None
