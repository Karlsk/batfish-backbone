import io
import re

import pytest

from app.infrastructure.source_lines import LineScanner, source_lines


@pytest.mark.parametrize(
    "data", [b"", b"a\rb\r", b"\r\n\n", b"a\r\r\nb\rc\nd", b"x" * 65535 + b"\r\nnext\r"]
)
def test_line_scanner_matches_engine_delimiters_across_chunks(data):
    expected = re.sub(rb"\r+", b"\n", re.sub(rb"\r+\n", b"\n", data)).split(b"\n")
    if expected[-1] == b"":
        expected.pop()
    scanner = LineScanner(max_bytes=70000)
    rows = []
    for index in range(0, len(data), 7):
        rows.extend(scanner.feed(data[index : index + 7]))
    rows.extend(scanner.finish())
    assert rows == [(i + 1, line, False) for i, line in enumerate(expected)]
    assert len(list(source_lines(io.BytesIO(data), max_bytes=0))) == len(expected)
