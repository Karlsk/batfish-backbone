"""Encode saved public result data; never calls the SDK or accepts paths."""

import csv
import io
import json
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class ResultDownload:
    chunks: Iterator[bytes]
    media_type: str
    filename: str


def csv_cell(value):
    if value is None:
        return ""
    text = (
        value
        if isinstance(value, str)
        else json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    )
    # Spreadsheet importers may discard leading whitespace/control characters.
    index = 0
    while index < len(text) and (
        text[index].isspace() or unicodedata.category(text[index]).startswith("C")
    ):
        index += 1
    if text[index : index + 1] in {"=", "+", "-", "@"} or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def csv_chunks(metadata, payload):
    yield "\ufeff"
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    columns = [item["key"] for item in payload["columns"]]

    def row(values):
        output.seek(0)
        output.truncate()
        writer.writerow([csv_cell(value) for value in values])
        return output.getvalue()

    yield row(["record_type", "metadata_json", *("data:" + key for key in columns)])
    yield row(["metadata", metadata, *("" for _ in columns)])
    for item in payload["rows"]:
        yield row(["data", "", *(item.get(key) for key in columns)])


def buffered_chunks(chunks, size=65536):
    """Amortize ASGI/threadpool sends without materializing the whole response."""
    pending = bytearray()
    for chunk in chunks:
        data = chunk.encode("utf-8")
        offset = 0
        while offset < len(data):
            take = min(size - len(pending), len(data) - offset)
            pending.extend(data[offset : offset + take])
            offset += take
            if len(pending) == size:
                yield bytes(pending)
                pending.clear()
    if pending:
        yield bytes(pending)


def download(result, payload, format):
    metadata = result.model_dump(mode="json")
    if format == "csv":
        chunks = csv_chunks(metadata, payload)
        media_type = "text/csv"
    else:
        chunks = json.JSONEncoder(
            ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).iterencode({"metadata": metadata, "data": payload})
        media_type = "application/json"
    return ResultDownload(buffered_chunks(chunks), media_type, f"batfish-{result.id}.{format}")
