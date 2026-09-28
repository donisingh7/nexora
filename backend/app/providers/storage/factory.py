from app.core.config import Settings, get_settings
from app.providers.storage.interface import ObjectStorage
from app.providers.storage.local import LocalStorageProvider
from app.providers.storage.s3 import S3StorageProvider


def create_object_storage(settings: Settings | None = None) -> ObjectStorage:
    configured = settings or get_settings()
    if configured.storage_provider == "local":
        return LocalStorageProvider(configured.local_storage_path)
    if configured.storage_provider == "s3":
        return S3StorageProvider(configured)
    raise ValueError(f"Unsupported storage provider: {configured.storage_provider}")
