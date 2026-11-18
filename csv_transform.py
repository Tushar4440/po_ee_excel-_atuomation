import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException


@dataclass(frozen=True)
class CsvTable:
    headers: list[str]
    rows: list[list[str]]
    delimiter: str
    quotechar: str
    quoting: int
    doublequote: bool
    escapechar: str | None
    skipinitialspace: bool
    lineterminator: str
    has_bom: bool


class CsvFormatError(ValueError):
    pass


def _validate_records(
    records: list[list[str]],
    filename: str,
) -> tuple[list[str], list[list[str]]]:
    records = [row for row in records if row and any(value != "" for value in row)]
    if not records:
        raise CsvFormatError(f"{filename} is empty.")

    headers = records[0]
    if any(not header.strip() for header in headers):
        raise CsvFormatError(f"{filename} contains an empty column name.")
    if len(set(headers)) != len(headers):
        raise CsvFormatError(f"{filename} contains duplicate column names.")

    rows = records[1:]
    for row_number, row in enumerate(rows, start=2):
        if len(row) != len(headers):
            raise CsvFormatError(
                f"{filename} row {row_number} has {len(row)} values; "
                f"expected {len(headers)}."
            )
    return headers, rows


def _xlsx_value(value: object, number_format: str) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, int) and set(number_format) == {"0"}:
        return str(value).zfill(len(number_format))
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
    return str(value)


def suggest_source_column(template_header: str, source_headers: list[str]) -> int | None:
    def normalized(header: str) -> str:
        return re.sub(r"[^a-z0-9]", "", header.casefold())

    ean_names = {"ean", "eannumber", "eanno", "eancode"}
    template_name = normalized(template_header)
    if template_name in ean_names:
        matches = [
            index
            for index, header in enumerate(source_headers)
            if normalized(header) in ean_names
        ]
    else:
        matches = [
            index
            for index, header in enumerate(source_headers)
            if normalized(header) == template_name
        ]
    return matches[0] if len(matches) == 1 else None


def read_csv(data: bytes, filename: str) -> CsvTable:
    has_bom = data.startswith(b"\xef\xbb\xbf")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CsvFormatError(
            f"{filename} is not UTF-8 encoded. Save it as a UTF-8 CSV and try again."
        ) from error

    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    try:
        records = list(csv.reader(io.StringIO(text, newline=""), dialect))
    except csv.Error as error:
        raise CsvFormatError(f"{filename} could not be read as a CSV file: {error}") from error

    headers, rows = _validate_records(records, filename)

    newline_match = re.search(r"\r\n|\n|\r", text)
    lineterminator = newline_match.group(0) if newline_match else "\r\n"
    return CsvTable(
        headers=headers,
        rows=rows,
        delimiter=dialect.delimiter,
        quotechar=dialect.quotechar or '"',
        quoting=dialect.quoting,
        doublequote=dialect.doublequote,
        escapechar=dialect.escapechar,
        skipinitialspace=dialect.skipinitialspace,
        lineterminator=lineterminator,
        has_bom=has_bom,
    )


def read_xlsx(data: bytes, filename: str) -> CsvTable:
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, OSError, ValueError) as error:
        raise CsvFormatError(f"{filename} could not be read as an Excel workbook.") from error

    try:
        worksheet = workbook.active
        records = [
            [_xlsx_value(cell.value, cell.number_format) for cell in row]
            for row in worksheet.iter_rows()
        ]
    finally:
        workbook.close()

    headers, rows = _validate_records(records, filename)
    return CsvTable(
        headers=headers,
        rows=rows,
        delimiter=",",
        quotechar='"',
        quoting=csv.QUOTE_MINIMAL,
        doublequote=True,
        escapechar=None,
        skipinitialspace=False,
        lineterminator="\r\n",
        has_bom=False,
    )


def read_source_file(data: bytes, filename: str) -> CsvTable:
    extension = filename.rpartition(".")[2].casefold()
    if extension == "csv":
        return read_csv(data, filename)
    if extension == "xlsx":
        return read_xlsx(data, filename)
    raise CsvFormatError(f"{filename} must be a CSV or XLSX file.")


def transform_csv(
    source: CsvTable,
    template: CsvTable,
    mappings: dict[int, str],
    vendor_token: str,
) -> tuple[bytes, list[list[str]]]:
    if not source.rows:
        raise CsvFormatError("The PO file has no data rows.")
    if not vendor_token.strip():
        raise CsvFormatError("Enter the EasyEcom vendor token.")
    if len(mappings) != len(template.headers):
        raise CsvFormatError("Choose a mapping for every template column.")

    token_columns = [column for column, mapping in mappings.items() if mapping == "vendor_token"]
    price_columns = [column for column, mapping in mappings.items() if mapping == "unit_price"]
    if len(token_columns) != 1:
        raise CsvFormatError("Map exactly one template column to Vendor token.")
    if len(price_columns) != 1:
        raise CsvFormatError("Map exactly one template column to Unit price (10).")

    output_rows: list[list[str]] = []
    for source_row in source.rows:
        output_row: list[str] = []
        for column_index in range(len(template.headers)):
            mapping = mappings[column_index]
            if mapping == "blank":
                value = ""
            elif mapping == "vendor_token":
                value = vendor_token
            elif mapping == "unit_price":
                value = "10"
            elif mapping.startswith("source:"):
                try:
                    source_index = int(mapping.split(":", 1)[1])
                    value = source_row[source_index]
                except (ValueError, IndexError) as error:
                    raise CsvFormatError(
                        f"Invalid source-column mapping for {template.headers[column_index]}."
                    ) from error
            else:
                raise CsvFormatError(
                    f"Invalid mapping for template column {template.headers[column_index]}."
                )
            output_row.append(value)
        output_rows.append(output_row)

    output = io.StringIO(newline="")
    writer = csv.writer(
        output,
        delimiter=template.delimiter,
        quotechar=template.quotechar,
        quoting=template.quoting,
        doublequote=template.doublequote,
        escapechar=template.escapechar,
        skipinitialspace=template.skipinitialspace,
        lineterminator=template.lineterminator,
    )
    writer.writerow(template.headers)
    writer.writerows(output_rows)
    encoded = output.getvalue().encode("utf-8")
    if template.has_bom:
        encoded = b"\xef\xbb\xbf" + encoded
    return encoded, output_rows
