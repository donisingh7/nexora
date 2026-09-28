import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace

DEFAULT_DEVELOPMENT_WORKSPACE_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


async def ensure_development_workspace(session: AsyncSession) -> Workspace:
    statement = (
        pg_insert(Workspace)
        .values(id=DEFAULT_DEVELOPMENT_WORKSPACE_ID, name="Development workspace")
        .on_conflict_do_nothing(index_elements=[Workspace.id])
    )
    await session.execute(statement)
    await session.commit()
    workspace = await session.get(Workspace, DEFAULT_DEVELOPMENT_WORKSPACE_ID)
    if workspace is None:
        raise RuntimeError("Unable to initialize the development workspace")
    return workspace
