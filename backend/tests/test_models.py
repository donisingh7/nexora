from sqlalchemy.orm import configure_mappers

from app.db.base import Base
from app.models import Document, DocumentChunk, IngestionJob, User


def test_generic_domain_tables_and_relationships_are_configured() -> None:
    configure_mappers()

    assert set(Base.metadata.tables) == {
        "workspaces",
        "users",
        "documents",
        "document_chunks",
        "ingestion_jobs",
    }
    assert User.__table__.c.workspace_id.foreign_keys
    assert Document.__table__.c.workspace_id.foreign_keys
    assert DocumentChunk.__table__.c.document_id.foreign_keys
    assert IngestionJob.__table__.c.document_id.foreign_keys
    assert DocumentChunk.__table__.c.embedding.type.dim == 384
