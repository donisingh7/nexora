import asyncio

from app.api.dependencies import get_embedding_provider, get_storage_provider
from app.core.config import get_settings
from app.db.session import SessionFactory
from app.services.ingestion import IngestionWorker


async def main() -> None:
    settings = get_settings()
    async with SessionFactory() as session:
        worker = IngestionWorker(
            session,
            get_storage_provider(),
            get_embedding_provider(),
            settings,
        )
        await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
