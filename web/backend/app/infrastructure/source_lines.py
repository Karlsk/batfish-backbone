"""Bounded original-line scanner matching Batfish CR-run / CRLF normalization.

Only line delimiters are interpreted. Original file bytes are never rewritten.
"""

import re

_SEPARATORS = re.compile(rb"\r+|\n")


class LineScanner:
    def __init__(self, max_bytes=65536):
        self.max_bytes = max_bytes
        self.number = 0
        self._prefix = bytearray()
        self._size = 0
        self._cr = False

    def _append(self, data):
        if data:
            self._cr = False
            self._size += len(data)
            self._prefix.extend(data[: max(0, self.max_bytes - len(self._prefix))])

    def _emit(self):
        self.number += 1
        result = (self.number, bytes(self._prefix), self._size > self.max_bytes)
        self._prefix.clear()
        self._size = 0
        return result

    def feed(self, data):
        cursor = 0
        for match in _SEPARATORS.finditer(data):
            self._append(data[cursor : match.start()])
            if not self._cr:
                yield self._emit()
            self._cr = match.group().startswith(b"\r")
            cursor = match.end()
        self._append(data[cursor:])

    def finish(self):
        if self._size:
            yield self._emit()


def source_lines(source, *, max_bytes=65536):
    scanner = LineScanner(max_bytes)
    while data := source.read(65536):
        yield from scanner.feed(data)
    yield from scanner.finish()
