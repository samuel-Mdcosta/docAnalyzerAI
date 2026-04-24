import asyncio
import base64
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import google.generativeai as genai
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import ConversionStatus
from docling.datamodel.document import DoclingDocument
from docling.datamodel.pipeline_options import PdfPipelineOptions

from pydantic import BaseModel, ConfigDict

from langfuse.decorators import observe

from app.config import settings

genai.configure(api_key=settings.gemini_api_key)
_gemini = genai.GenerativeModel(settings.gemini_model)

_PROMPTS_DIR = Path(__file__).parent.parent / "agent" / "prompts"
_FIGURE_PROMPT = (_PROMPTS_DIR / "figure_description.txt").read_text(encoding="utf-8").strip()

class TableResult(BaseModel):
    index: int
    page: int | None
    markdown: str
    dataframe: Any


class FigureResult(BaseModel):
    index: int
    page: int | None
    description: str


class ExtractionResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    document: DoclingDocument
    full_text: str
    tables: list[TableResult]
    figures: list[FigureResult]

@observe()
async def extract_document(path: Path, enable_ocr: bool = False) -> ExtractionResult:
    converter = _build_converter(enable_ocr)

    result = await asyncio.to_thread(converter.convert, path)

    if result.status == ConversionStatus.FAILURE:
        raise RuntimeError(
            f"Docling não conseguiu processar o arquivo '{path.name}'. "
            f"Verifique se o arquivo é um PDF válido e não está corrompido."
        )

    document = result.document

    full_text = document.export_to_markdown()

    tables = _extract_tables(document)

    figures = await _extract_figures(document) if settings.enable_chart_extraction else []

    return ExtractionResult(
        document=document,
        full_text=full_text,
        tables=tables,
        figures=figures,
    )


@observe()
async def _extract_figures(document: DoclingDocument) -> list[FigureResult]:
    figures = []

    for index, picture in enumerate(document.pictures):
        image = picture.get_image(document)
        if image is None:
            continue

        page = picture.prov[0].page_no if picture.prov else None

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        try:
            response = await asyncio.to_thread(
                _gemini.generate_content,
                [_FIGURE_PROMPT, {"mime_type": "image/png", "data": image_b64}],
            )
            description = response.text.strip()
        except Exception:
            description = "[erro ao processar figura com Gemini]"

        figures.append(FigureResult(index=index, page=page, description=description))

    return figures


@observe()
def _extract_tables(document: DoclingDocument) -> list[TableResult]:
    tables = []

    for index, table in enumerate(document.tables):
        page = table.prov[0].page_no if table.prov else None

        markdown = table.export_to_markdown()

        dataframe: pd.DataFrame = table.export_to_dataframe()

        tables.append(TableResult(index=index, page=page, markdown=markdown, dataframe=dataframe))

    return tables


def _build_converter(enable_ocr: bool) -> DocumentConverter:
    pipeline_options = PdfPipelineOptions(
        do_ocr=enable_ocr,

        do_table_structure=True,

        generate_picture_images=settings.enable_chart_extraction,
    )

    return DocumentConverter(
        format_options={
            "pdf": PdfFormatOption(pipeline_options=pipeline_options),
        }
    )
