from pathlib import Path
from typing import Any

import pytest

from app.config import settings
from app.pipelines import extractor
from app.pipelines.extractor import (
    ExtractionResult,
    FigureResult,
    TableResult,
    _extract_figures,
    _extract_tables,
    extract_document,
)


class _FakeProv:
    def __init__(self, page_no: int) -> None:
        self.page_no = page_no


class _FakeTable:
    def __init__(self, page: int | None, markdown: str, dataframe: Any) -> None:
        self.prov = [_FakeProv(page)] if page is not None else []
        self._markdown = markdown
        self._dataframe = dataframe

    def export_to_markdown(self) -> str:
        return self._markdown

    def export_to_dataframe(self) -> Any:
        return self._dataframe


class _FakeImage:
    def save(self, buffer: Any, format: str) -> None:
        buffer.write(b"fake-png-bytes")


class _FakePicture:
    def __init__(self, page: int | None, image: _FakeImage | None) -> None:
        self.prov = [_FakeProv(page)] if page is not None else []
        self._image = image

    def get_image(self, document: Any) -> _FakeImage | None:
        return self._image


class _FakeDocument:
    def __init__(
        self,
        markdown: str = "",
        tables: list[_FakeTable] | None = None,
        pictures: list[_FakePicture] | None = None,
    ) -> None:
        self._markdown = markdown
        self.tables = tables or []
        self.pictures = pictures or []

    def export_to_markdown(self) -> str:
        return self._markdown


class _FakeConvertResult:
    def __init__(self, document: _FakeDocument, status: Any) -> None:
        self.document = document
        self.status = status


class _FakeConverter:
    def __init__(self, result: _FakeConvertResult) -> None:
        self._result = result

    def convert(self, path: Path) -> _FakeConvertResult:
        return self._result


# ---------- _extract_tables ----------


def test_extract_tables_returns_empty_when_document_has_no_tables() -> None:
    document = _FakeDocument(tables=[])
    assert _extract_tables(document) == []  # type: ignore[arg-type]


def test_extract_tables_maps_each_table_with_index_and_page() -> None:
    document = _FakeDocument(
        tables=[
            _FakeTable(page=1, markdown="| a | b |", dataframe="df-1"),
            _FakeTable(page=3, markdown="| c | d |", dataframe="df-2"),
        ]
    )
    tables = _extract_tables(document)  # type: ignore[arg-type]

    assert len(tables) == 2
    assert tables[0] == TableResult(index=0, page=1, markdown="| a | b |", dataframe="df-1")
    assert tables[1].index == 1
    assert tables[1].page == 3
    assert tables[1].dataframe == "df-2"


def test_extract_tables_sets_page_to_none_when_prov_is_empty() -> None:
    document = _FakeDocument(tables=[_FakeTable(page=None, markdown="md", dataframe="df")])
    tables = _extract_tables(document)  # type: ignore[arg-type]
    assert tables[0].page is None


# ---------- _extract_figures ----------


class _FakeGeminiResponse:
    def __init__(self, text: str) -> None:
        self.text = text


def _patch_gemini(monkeypatch: pytest.MonkeyPatch, response_text: str = "descrição ok") -> list[Any]:
    calls: list[Any] = []

    def fake_generate_content(payload: Any) -> _FakeGeminiResponse:
        calls.append(payload)
        return _FakeGeminiResponse(response_text)

    monkeypatch.setattr(extractor._gemini, "generate_content", fake_generate_content)
    return calls


@pytest.mark.asyncio
async def test_extract_figures_returns_empty_for_no_pictures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_gemini(monkeypatch)
    document = _FakeDocument(pictures=[])
    assert await _extract_figures(document) == []  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_extract_figures_describes_each_picture_via_gemini(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_gemini(monkeypatch, response_text="  gráfico de barras  ")
    document = _FakeDocument(
        pictures=[
            _FakePicture(page=2, image=_FakeImage()),
            _FakePicture(page=5, image=_FakeImage()),
        ]
    )

    figures = await _extract_figures(document)  # type: ignore[arg-type]

    assert len(calls) == 2
    assert figures == [
        FigureResult(index=0, page=2, description="gráfico de barras"),
        FigureResult(index=1, page=5, description="gráfico de barras"),
    ]


@pytest.mark.asyncio
async def test_extract_figures_skips_pictures_without_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_gemini(monkeypatch)
    document = _FakeDocument(
        pictures=[
            _FakePicture(page=1, image=None),
            _FakePicture(page=2, image=_FakeImage()),
        ]
    )

    figures = await _extract_figures(document)  # type: ignore[arg-type]

    assert len(figures) == 1
    assert figures[0].page == 2


@pytest.mark.asyncio
async def test_extract_figures_returns_fallback_text_when_gemini_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(payload: Any) -> _FakeGeminiResponse:
        raise RuntimeError("gemini down")

    monkeypatch.setattr(extractor._gemini, "generate_content", boom)
    document = _FakeDocument(pictures=[_FakePicture(page=1, image=_FakeImage())])

    figures = await _extract_figures(document)  # type: ignore[arg-type]

    assert figures[0].description == "[erro ao processar figura com Gemini]"


# ---------- extract_document ----------


@pytest.mark.asyncio
async def test_extract_document_raises_when_conversion_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _FakeDocument()
    fake_result = _FakeConvertResult(document, status=extractor.ConversionStatus.FAILURE)
    monkeypatch.setattr(
        extractor, "_build_converter", lambda enable_ocr: _FakeConverter(fake_result)
    )

    with pytest.raises(RuntimeError, match="Docling não conseguiu processar"):
        await extract_document(Path("broken.pdf"))


@pytest.mark.asyncio
async def test_extract_document_skips_figures_when_flag_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "enable_chart_extraction", False)

    document = _FakeDocument(
        markdown="# Título\nconteúdo",
        tables=[_FakeTable(page=1, markdown="| a |", dataframe="df")],
        pictures=[_FakePicture(page=1, image=_FakeImage())],
    )
    fake_result = _FakeConvertResult(document, status=extractor.ConversionStatus.SUCCESS)
    monkeypatch.setattr(
        extractor, "_build_converter", lambda enable_ocr: _FakeConverter(fake_result)
    )

    result = await extract_document(Path("doc.pdf"))

    assert isinstance(result, ExtractionResult)
    assert result.full_text == "# Título\nconteúdo"
    assert len(result.tables) == 1
    assert result.figures == []


@pytest.mark.asyncio
async def test_extract_document_runs_full_pipeline_when_flag_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "enable_chart_extraction", True)
    _patch_gemini(monkeypatch, response_text="figura descrita")

    document = _FakeDocument(
        markdown="texto completo",
        tables=[_FakeTable(page=2, markdown="| h |", dataframe="df")],
        pictures=[_FakePicture(page=2, image=_FakeImage())],
    )
    fake_result = _FakeConvertResult(document, status=extractor.ConversionStatus.SUCCESS)
    monkeypatch.setattr(
        extractor, "_build_converter", lambda enable_ocr: _FakeConverter(fake_result)
    )

    result = await extract_document(Path("doc.pdf"), enable_ocr=True)

    assert result.full_text == "texto completo"
    assert [t.index for t in result.tables] == [0]
    assert [f.description for f in result.figures] == ["figura descrita"]
