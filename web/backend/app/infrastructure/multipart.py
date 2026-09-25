"""Bound actual body and part bytes before parser spool files can grow without limit."""

from contextlib import asynccontextmanager

from starlette.formparsers import MultiPartException, MultiPartParser

from app.contracts.errors import ErrorCode, ServiceError


class BoundedParser(MultiPartParser):
    def __init__(self, *args, max_bytes, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_bytes = max_bytes
        self.received = 0
        self.complete = False

    def on_part_data(self, data, start, end):
        self.received += end - start
        if self.received > self.max_bytes:
            raise ServiceError(ErrorCode.UPLOAD_TOO_LARGE)
        super().on_part_data(data, start, end)

    def on_end(self):
        self.complete = True
        super().on_end()


@asynccontextmanager
async def bounded_form(request, *, max_bytes, max_files):
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "multipart/form-data"
    ):
        raise ServiceError(ErrorCode.VALIDATION_ERROR)

    async def stream():
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > max_bytes + 1024 * 1024:
                raise ServiceError(ErrorCode.UPLOAD_TOO_LARGE)
            yield chunk

    parser = BoundedParser(
        request.headers, stream(), max_bytes=max_bytes, max_files=max_files, max_fields=0
    )
    form = None
    try:
        form = await parser.parse()
        if not parser.complete:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        yield form
    except MultiPartException:
        raise ServiceError(ErrorCode.VALIDATION_ERROR) from None
    finally:
        if form is not None:
            await form.close()
        # Also close an unfinished part not present in FormData after truncated input.
        for file in parser._files_to_close_on_error:
            file.close()
