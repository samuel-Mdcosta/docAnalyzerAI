import asyncio
import base64
from io import BytesIO
from pathlib import Path

import pandas as pd
import google.generativeai as genai
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import ConversionStatus
from docling.datamodel.document import DoclingDocument
from docling.datamodel.pipeline_options import PdfPipelineOptions

from app.config import settings

genai.configure(api_key=settings.gemini_api_key)
_gemini = genai.GenerativeModel("gemini-1.5-pro")

_FIGURE_PROMPT = (
    "Descreva objetivamente o conteúdo deste gráfico ou figura. "
    "Se houver valores numéricos, séries ou categorias visíveis, liste-os explicitamente. "
    "Se não for possível identificar nenhum dado relevante, responda apenas: [figura sem dados extraíveis]."
)


async def extract_document(path: Path, enable_ocr: bool = False) -> tuple[DoclingDocument, str, list[dict], list[dict]]:
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

    return document, full_text, tables, figures


async def _extract_figures(document: DoclingDocument) -> list[dict]:
    """
    Itera sobre as figuras do documento e envia cada imagem ao Gemini para
    gerar uma descrição textual. Figuras sem imagem gerada (PDFs vetoriais
    onde o Docling não conseguiu recortar) são ignoradas silenciosamente.
    """
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

        figures.append({
            "index": index,
            "page": page,
            "description": description,
        })

    return figures


def _extract_tables(document: DoclingDocument) -> list[dict]:
    tables = []

    for index, table in enumerate(document.tables):
        page = table.prov[0].page_no if table.prov else None

        markdown = table.export_to_markdown()

        dataframe: pd.DataFrame = table.export_to_dataframe()

        tables.append({
            "index": index,
            "page": page,
            "markdown": markdown,
            "dataframe": dataframe,
        })

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
