import asyncio

import pytest
from starlette.requests import Request

from app.contracts.errors import ServiceError
from app.infrastructure.multipart import bounded_form


def parse(body, *, limit=10, cut=None):
    async def execute():
        chunks = [body[i : i + 3] for i in range(0, len(body), 3)]

        async def receive():
            return {"type": "http.request", "body": chunks.pop(0), "more_body": bool(chunks)}

        request = Request(
            {"type": "http", "headers": [(b"content-type", b"multipart/form-data; boundary=TEST")]},
            receive,
        )
        async with bounded_form(request, max_bytes=limit, max_files=1) as form:
            return [(key, await value.read()) for key, value in form.multi_items()]

    return asyncio.run(execute())


def body(content):
    return (
        b'--TEST\r\nContent-Disposition: form-data; name="files"; filename="a"\r\n\r\n'
        + content
        + b"\r\n--TEST--\r\n"
    )


def test_chunked_upload_counts_bytes_without_content_length():
    assert parse(body(b"1234567890")) == [("files", b"1234567890")]
    with pytest.raises(ServiceError) as error:
        parse(body(b"12345678901"))
    assert error.value.code == "UPLOAD_TOO_LARGE"


def test_truncated_multipart_is_rejected():
    with pytest.raises(ServiceError):
        parse(body(b"x")[:-8])
