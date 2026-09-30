from enum import StrEnum


class IngestionStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionStage(StrEnum):
    """Granular progress within `processing`, for UI feedback only - never used for
    correctness decisions. `status` remains the source of truth for completion."""

    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
