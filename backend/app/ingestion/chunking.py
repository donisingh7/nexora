from dataclasses import dataclass

from app.ingestion.parsers import ParsedUnit


@dataclass(frozen=True)
class TextChunk:
    text: str
    chunk_index: int
    page_number: int | None
    location_metadata: dict[str, object]


class TextChunker:
    def __init__(self, chunk_size: int = 1200, overlap: int = 180) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be non-negative and smaller than chunk_size")
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk(self, units: list[ParsedUnit]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for unit in units:
            text = unit.text.strip()
            if not text:
                continue
            start = 0
            while start < len(text):
                end = min(start + self._chunk_size, len(text))
                if end < len(text):
                    boundary = max(
                        text.rfind(" ", start + self._chunk_size // 2, end),
                        text.rfind("\n", start + self._chunk_size // 2, end),
                    )
                    if boundary > start:
                        end = boundary
                chunk_text = text[start:end].strip()
                if chunk_text:
                    location = dict(unit.location or {})
                    location.update({"char_start": start, "char_end": end})
                    if unit.page_number is None:
                        location["line_start"] = text.count("\n", 0, start) + 1
                        location["line_end"] = text.count("\n", 0, end) + 1
                    chunks.append(
                        TextChunk(
                            text=chunk_text,
                            chunk_index=len(chunks),
                            page_number=unit.page_number,
                            location_metadata=location,
                        )
                    )
                if end == len(text):
                    break
                start = max(end - self._overlap, start + 1)
        return chunks
