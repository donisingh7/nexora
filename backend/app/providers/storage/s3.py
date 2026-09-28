import asyncio
from typing import Any

from app.core.config import Settings
from app.providers.storage.interface import ObjectMetadata


class S3StorageProvider:
    def __init__(self, settings: Settings) -> None:
        if not settings.s3_bucket:
            raise ValueError("S3_BUCKET must be configured when S3 storage is selected")
        self._bucket = settings.s3_bucket
        self._region = settings.aws_region
        self._access_key_id = (
            settings.aws_access_key_id.get_secret_value() if settings.aws_access_key_id else None
        )
        self._secret_access_key = (
            settings.aws_secret_access_key.get_secret_value()
            if settings.aws_secret_access_key
            else None
        )
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                region_name=self._region,
                **(
                    {
                        "aws_access_key_id": self._access_key_id,
                        "aws_secret_access_key": self._secret_access_key,
                    }
                    if self._access_key_id and self._secret_access_key
                    else {}
                ),
            )
        return self._client

    async def upload(self, key: str, content: bytes, content_type: str) -> ObjectMetadata:
        await asyncio.to_thread(
            self._get_client().put_object,
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return ObjectMetadata(key=key, size_bytes=len(content), content_type=content_type)

    async def read(self, key: str) -> bytes:
        response = await asyncio.to_thread(
            self._get_client().get_object, Bucket=self._bucket, Key=key
        )
        return await asyncio.to_thread(response["Body"].read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._get_client().delete_object, Bucket=self._bucket, Key=key)

    async def get_metadata(self, key: str) -> ObjectMetadata | None:
        from botocore.exceptions import ClientError

        try:
            response = await asyncio.to_thread(
                self._get_client().head_object, Bucket=self._bucket, Key=key
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return ObjectMetadata(
            key=key,
            size_bytes=response["ContentLength"],
            content_type=response.get("ContentType"),
        )
