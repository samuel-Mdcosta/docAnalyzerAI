import re
from typing import Any, Literal

from pydantic import BaseModel

from app.config import settings


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


class ChunkResult(BaseModel):
    text: str
    index: int
    page: int | None
    chunk_type: Literal["text", "table", "figure"]
    metadata: dict[str, Any]


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text.strip()) if s.strip()]


def _take_overlap(sentences: list[str], target: int) -> tuple[list[str], int]:
    if target <= 0:
        return [], 0

    overlap: list[str] = []
    overlap_len = 0
    for tail in reversed(sentences):
        cost = len(tail) + (1 if overlap else 0)
        if overlap_len + cost > target:
            break
        overlap.insert(0, tail)
        overlap_len += cost

    return overlap, overlap_len


def chunk_text(text: str) -> list[str]:
    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        cost = len(sentence) + (1 if current else 0)

        if current and current_len + cost > settings.chunk_size:
            chunks.append(" ".join(current))
            current, current_len = _take_overlap(current, settings.chunk_overlap)
            cost = len(sentence) + (1 if current else 0)

        current.append(sentence)
        current_len += cost

    if current:
        chunks.append(" ".join(current))

    return chunks


def chunk_text_items(
    items: list[tuple[str, int | None]],
    source: str,
) -> list[ChunkResult]:
    if not items:
        return []

    def make_chunks(page: int | None, texts: list[str], start: int) -> list[ChunkResult]:
        return [
            ChunkResult(
                text=chunk,
                index=start + i,
                page=page,
                chunk_type="text",
                metadata={"source": source},
            )
            for i, chunk in enumerate(chunk_text("\n".join(texts)))
        ]

    results: list[ChunkResult] = []
    current_page = items[0][1]
    current_texts: list[str] = []

    for text, page in items:
        if page != current_page and current_texts:
            results.extend(make_chunks(current_page, current_texts, len(results)))
            current_page = page
            current_texts = []
        current_texts.append(text)

    if current_texts:
        results.extend(make_chunks(current_page, current_texts, len(results)))

    return results
