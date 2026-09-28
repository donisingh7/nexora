from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.dependencies import get_development_workspace, get_document_service
from app.core.config import Settings, get_settings
from app.models.workspace import Workspace
from app.schemas.documents import DocumentRead
from app.services.documents import DocumentService, UploadValidationError

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: Annotated[UploadFile, File()],
    service: Annotated[DocumentService, Depends(get_document_service)],
    workspace: Annotated[Workspace, Depends(get_development_workspace)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentRead:
    content = await file.read(settings.max_upload_size_bytes + 1)
    try:
        return await service.upload(
            filename=file.filename or "",
            content_type=file.content_type or "",
            content=content,
            workspace_id=workspace.id,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    finally:
        await file.close()


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    service: Annotated[DocumentService, Depends(get_document_service)],
    workspace: Annotated[Workspace, Depends(get_development_workspace)],
) -> list[DocumentRead]:
    return await service.list_documents(workspace.id)


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: UUID,
    service: Annotated[DocumentService, Depends(get_document_service)],
    workspace: Annotated[Workspace, Depends(get_development_workspace)],
) -> DocumentRead:
    document = await service.get_document(document_id, workspace.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
