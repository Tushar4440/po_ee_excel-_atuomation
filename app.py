import json
import re
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import HTMLResponse

from csv_transform import (
    CsvTable,
    CsvFormatError,
    read_csv,
    read_source_file,
    suggest_source_column,
    transform_csv,
)


app = FastAPI(title="PO CSV Builder")


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    html = (Path(__file__).parent / "public" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


async def _read_tables(
    source_file: UploadFile,
    template_file: UploadFile,
) -> tuple[CsvTable, CsvTable]:
    source_name = source_file.filename or "orders.csv"
    template_name = template_file.filename or "template.csv"
    try:
        source = read_source_file(await source_file.read(), source_name)
        template = read_csv(await template_file.read(), template_name)
    except CsvFormatError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if not source.rows:
        raise HTTPException(
            status_code=400,
            detail="The PO file has a header row but no order rows.",
        )
    return source, template


@app.post("/api/preview")
async def preview(
    source_file: Annotated[UploadFile, File()],
    template_file: Annotated[UploadFile, File()],
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    source, template = await _read_tables(source_file, template_file)
    suggested_mappings = []
    for header in template.headers:
        source_index = suggest_source_column(header, source.headers)
        suggested_mappings.append(
            f"source:{source_index}" if source_index is not None else "blank"
        )
    return {
        "source_headers": source.headers,
        "template_headers": template.headers,
        "row_count": len(source.rows),
        "suggested_mappings": suggested_mappings,
    }


@app.post("/api/transform")
async def transform(
    source_file: Annotated[UploadFile, File()],
    template_file: Annotated[UploadFile, File()],
    vendor_token: Annotated[str, Form()],
    mappings: Annotated[str, Form()],
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    source, template = await _read_tables(source_file, template_file)
    try:
        mapping_data = json.loads(mappings)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Invalid column mappings.") from error

    expected_keys = {str(index) for index in range(len(template.headers))}
    if (
        not isinstance(mapping_data, dict)
        or set(mapping_data) != expected_keys
        or any(not isinstance(value, str) for value in mapping_data.values())
    ):
        raise HTTPException(
            status_code=400,
            detail="Choose a mapping for every template column.",
        )

    try:
        output, rows = transform_csv(
            source=source,
            template=template,
            mappings={int(index): mapping for index, mapping in mapping_data.items()},
            vendor_token=vendor_token,
        )
    except CsvFormatError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    source_stem = Path((source_file.filename or "orders.csv").replace("\\", "/")).stem
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", source_stem).strip("._")
    return {
        "filename": f"{safe_stem or 'orders'}_updated.csv",
        "headers": template.headers,
        "preview": rows[:20],
        "row_count": len(rows),
        "output_csv": output.decode("utf-8"),
    }
