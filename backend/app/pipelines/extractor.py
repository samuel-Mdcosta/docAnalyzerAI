import asyncio
from pathlib import Path

import pandas as pd
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import ConversionStatus
from docling.datamodel.document import DoclingDocument
from docling.datamodel.pipeline_options import PdfPipelineOptions

from app.config import settings


async def extract_document(path: Path, enable_ocr: bool = False) -> tuple[DoclingDocument, str, list[dict]]:
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

    return document, full_text, tables


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
