from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_development_workspace
from app.models.workspace import Workspace
from app.schemas.documents import WorkspaceRead

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("/development", response_model=WorkspaceRead)
async def development_workspace(
    workspace: Annotated[Workspace, Depends(get_development_workspace)],
) -> WorkspaceRead:
    return WorkspaceRead(id=workspace.id, name=workspace.name)
