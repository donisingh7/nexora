import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_development_workspace, get_document_service
from app.core.config import Settings
from app.main import app
from app.models.enums import IngestionStatus
from app.models.workspace import Workspace
from app.providers.storage.local import LocalStorageProvider
from app.services.documents import (
    DocumentService,
    UnsupportedUploadTypeError,
    UploadTooLargeError,
    UploadValidationError,
)
from app.services.workspaces import DEFAULT_DEVELOPMENT_WORKSPACE_ID

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class FakeSession:
    def __init__(self, fail_commit: bool = False) -> None:
        self.records = []
        self.fail_commit = fail_commit
        self.commit = AsyncMock(
            side_effect=RuntimeError("database unavailable") if fail_commit else None
        )
        self.rollback = AsyncMock()
        self.refresh = AsyncMock(side_effect=self._refresh)

    def add_all(self, records) -> None:
        self.records.extend(records)

    async def _refresh(self, document) -> None:
        document.created_at = datetime.now(UTC)
        document.updated_at = document.created_at


class FakeJobPublisher:
    def __init__(self) -> None:
        self.published: list = []

    async def publish(self, job_id) -> None:
        self.published.append(job_id)


@pytest.fixture
def upload_service(tmp_path):
    session = FakeSession()
    storage = LocalStorageProvider(tmp_path)
    settings = Settings(_env_file=None)
    return DocumentService(session, storage, settings), session, storage


@pytest.mark.asyncio
async def test_upload_creates_document_job_and_local_object(upload_service) -> None:
    service, session, storage = upload_service
    workspace_id = uuid.uuid4()

    result = await service.upload(
        filename="../../team-notes.txt",
        content_type="text/plain; charset=utf-8",
        content=b"knowledge text",
        workspace_id=workspace_id,
    )

    document, job = session.records
    assert result.filename == "team-notes.txt"
    assert result.workspace_id == workspace_id
    assert result.status == IngestionStatus.QUEUED
    assert job.document_id == document.id
    assert job.status == IngestionStatus.QUEUED.value
    assert await storage.read(document.storage_key) == b"knowledge text"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_publishes_job_id_when_a_publisher_is_configured(tmp_path) -> None:
    session = FakeSession()
    storage = LocalStorageProvider(tmp_path)
    publisher = FakeJobPublisher()
    service = DocumentService(session, storage, Settings(_env_file=None), publisher)

    result = await service.upload(
        filename="notes.txt", content_type="text/plain", content=b"text", workspace_id=uuid.uuid4()
    )

    _, job = session.records
    assert publisher.published == [job.id]
    assert result.status == IngestionStatus.QUEUED


@pytest.mark.parametrize(
    ("filename", "content_type", "expected"),
    [
        ("slides.pptx", PPTX_MIME, UnsupportedUploadTypeError),
        ("notes.pdf", "text/plain", UnsupportedUploadTypeError),
        ("notes.txt", "text/plain", UploadValidationError),
    ],
)
def test_upload_validation_rejects_unsupported_or_empty(
    filename, content_type, expected, upload_service
):
    service, _, _ = upload_service
    with pytest.raises(expected):
        service.validate_upload(filename, content_type, b"" if filename == "notes.txt" else b"data")


def test_upload_validation_enforces_maximum_size(upload_service) -> None:
    service, _, _ = upload_service
    service._settings = Settings(_env_file=None, max_upload_size_bytes=3)

    with pytest.raises(UploadTooLargeError):
        service.validate_upload("notes.txt", "text/plain", b"more")


def test_upload_validation_rejects_content_that_does_not_match_declared_pdf_type(
    upload_service,
) -> None:
    service, _, _ = upload_service
    with pytest.raises(UnsupportedUploadTypeError):
        service.validate_upload("fake.pdf", "application/pdf", b"this is not a pdf")


def test_upload_validation_rejects_content_that_does_not_match_declared_docx_type(
    upload_service,
) -> None:
    service, _, _ = upload_service
    docx_mime = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    with pytest.raises(UnsupportedUploadTypeError):
        service.validate_upload("fake.docx", docx_mime, b"this is not a zip")


def test_upload_validation_accepts_content_matching_declared_pdf_type(
    upload_service,
) -> None:
    service, _, _ = upload_service
    filename = service.validate_upload("real.pdf", "application/pdf", b"%PDF-1.4 minimal body")
    assert filename == "real.pdf"


def test_upload_validation_does_not_magic_byte_check_plain_text_formats(
    upload_service,
) -> None:
    service, _, _ = upload_service
    assert service.validate_upload("notes.txt", "text/plain", b"anything at all") == "notes.txt"


@pytest.mark.asyncio
async def test_failed_database_commit_removes_uploaded_object(tmp_path) -> None:
    session = FakeSession(fail_commit=True)
    storage = LocalStorageProvider(tmp_path)
    service = DocumentService(session, storage, Settings(_env_file=None))

    with pytest.raises(RuntimeError, match="database unavailable"):
        await service.upload(
            filename="notes.txt",
            content_type="text/plain",
            content=b"text",
            workspace_id=uuid.uuid4(),
        )

    session.rollback.assert_awaited_once()
    assert list(tmp_path.rglob("notes.txt")) == []


def test_upload_route_returns_queued_document_and_rejects_bad_type(tmp_path) -> None:
    session = FakeSession()
    service = DocumentService(
        session,
        LocalStorageProvider(tmp_path),
        Settings(_env_file=None),
    )
    workspace = Workspace(id=DEFAULT_DEVELOPMENT_WORKSPACE_ID, name="Development workspace")
    app.dependency_overrides[get_document_service] = lambda: service
    app.dependency_overrides[get_development_workspace] = lambda: workspace
    try:
        with TestClient(app) as client:
            accepted = client.post(
                "/api/v1/documents",
                files={"file": ("notes.md", b"# notes", "text/markdown")},
            )
            rejected = client.post(
                "/api/v1/documents",
                files={"file": ("slides.pptx", b"data", "application/octet-stream")},
            )
    finally:
        app.dependency_overrides.clear()

    assert accepted.status_code == 202
    assert accepted.json()["status"] == "queued"
    assert accepted.json()["workspace_id"] == str(DEFAULT_DEVELOPMENT_WORKSPACE_ID)
    assert rejected.status_code == 415
