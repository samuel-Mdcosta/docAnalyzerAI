import pytest

from app.config import settings
from app.pipelines.chunker import (
    _split_sentences,
    _take_overlap,
    chunk_text,
    chunk_text_items,
)


@pytest.fixture
def small_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "chunk_size", 20)
    monkeypatch.setattr(settings, "chunk_overlap", 10)


def test_split_sentences_handles_all_punctuation() -> None:
    assert _split_sentences("Oi. Tudo? Eba!") == ["Oi.", "Tudo?", "Eba!"]


def test_split_sentences_returns_empty_for_blank_input() -> None:
    assert _split_sentences("") == []
    assert _split_sentences("   \n  ") == []


def test_take_overlap_returns_empty_when_target_is_zero() -> None:
    assert _take_overlap(["A.", "B.", "C."], 0) == ([], 0)


def test_take_overlap_picks_tail_sentences_within_budget() -> None:
    overlap, length = _take_overlap(["Aaaa.", "Bb.", "Cc."], 10)
    assert overlap == ["Bb.", "Cc."]
    assert length == 7


def test_take_overlap_skips_when_first_tail_is_oversized() -> None:
    overlap, length = _take_overlap(["Massive sentence here."], 5)
    assert overlap == []
    assert length == 0


def test_chunk_text_returns_empty_for_blank_input(small_chunks: None) -> None:
    assert chunk_text("") == []


def test_chunk_text_keeps_short_input_in_single_chunk(small_chunks: None) -> None:
    assert chunk_text("Oi.") == ["Oi."]


def test_chunk_text_overlap_carries_tail_sentences_into_next_chunk(small_chunks: None) -> None:
    chunks = chunk_text("Oi. Tudo bem? Que bom. Tchau.")
    assert chunks == [
        "Oi. Tudo bem?",
        "Tudo bem? Que bom.",
        "Que bom. Tchau.",
    ]


def test_chunk_text_oversized_sentence_becomes_its_own_chunk(small_chunks: None) -> None:
    long_sentence = "A" * 100 + "."
    chunks = chunk_text(f"{long_sentence} Curta.")
    assert chunks[0] == long_sentence
    assert "Curta." in chunks[-1]


def test_chunk_text_items_returns_empty_for_no_items(small_chunks: None) -> None:
    assert chunk_text_items([], source="doc.pdf") == []


def test_chunk_text_items_streaming_revisit_creates_separate_groups(small_chunks: None) -> None:
    items: list[tuple[str, int | None]] = [
        ("Primeiro.", 1),
        ("Segundo.", 2),
        ("Terceiro.", 1),
    ]
    chunks = chunk_text_items(items, source="doc.pdf")
    assert [c.page for c in chunks] == [1, 2, 1]


def test_chunk_text_items_assigns_sequential_indices_and_metadata(small_chunks: None) -> None:
    items: list[tuple[str, int | None]] = [("Frase um.", 1), ("Frase dois.", 2)]
    chunks = chunk_text_items(items, source="example.pdf")
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert all(c.chunk_type == "text" for c in chunks)
    assert all(c.metadata == {"source": "example.pdf"} for c in chunks)


def test_chunk_text_items_preserves_none_page(small_chunks: None) -> None:
    items: list[tuple[str, int | None]] = [("Sem página.", None)]
    chunks = chunk_text_items(items, source="doc.pdf")
    assert chunks[0].page is None
