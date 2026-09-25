"""Bounded input decoding; files use generated IDs, never archive paths on disk."""

import codecs
import hashlib
import json
import os
import stat
import tempfile
import unicodedata
import zipfile
import zlib
from pathlib import Path
from uuid import uuid4

from app.contracts.errors import ErrorCode, ServiceError
from app.infrastructure.source_lines import LineScanner
from app.modules.uploads.schemas import FileEntry, UploadInput, UploadLimits

CHUNK = 64 * 1024


def invalid():
    return ServiceError(ErrorCode.VALIDATION_ERROR)


def safe_path(name: str) -> str:
    if (
        not name
        or len(name) > 1024
        or any(ord(c) < 32 for c in name)
        or "\\" in name
        or ":" in name
    ):
        raise invalid()
    name = unicodedata.normalize("NFC", name)
    parts = name.rstrip("/").split("/")
    if any(part in {"", ".", ".."} or len(part.encode("utf-8")) > 255 for part in parts):
        raise invalid()
    return "/".join(parts)


def copy_bounded(source, destination, budget):
    digest = hashlib.sha256()
    size = 0
    scanner = LineScanner(max_bytes=0)
    decoders = {
        encoding: codecs.getincrementaldecoder(encoding)() for encoding in ("utf-8", "gb18030")
    }
    first = True
    while data := source.read(CHUNK):
        if first and data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
            raise invalid()
        first = False
        size += len(data)
        budget[0] -= len(data)
        if budget[0] < 0:
            raise ServiceError(ErrorCode.UPLOAD_TOO_LARGE)
        digest.update(data)
        for _ in scanner.feed(data):
            pass
        for encoding in tuple(decoders):
            try:
                decoders[encoding].decode(data)
            except UnicodeDecodeError:
                del decoders[encoding]
        destination.write(data)
    for encoding in tuple(decoders):
        try:
            decoders[encoding].decode(b"", final=True)
        except UnicodeDecodeError:
            del decoders[encoding]
    for _ in scanner.finish():
        pass
    encoding = next(iter(decoders), "binary")
    return (
        size,
        digest.hexdigest(),
        encoding,
        (scanner.number if encoding != "binary" else None),
    )


def write_file(root, path, source, budget):
    if path.casefold().endswith(".zip"):
        raise invalid()
    identifier = uuid4()
    fd = os.open(
        root / str(identifier), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(fd, "wb") as target:
        size, digest, encoding, lines = copy_bounded(source, target, budget)
        target.flush()
        os.fsync(target.fileno())
    return FileEntry(
        id=identifier,
        path=path,
        sha256=digest,
        size_bytes=size,
        encoding=encoding,
        line_count=lines,
        line_policy="crlf-v1",
    )


def prepare(inputs: list[UploadInput], *, archive: bool, root: Path, limits: UploadLimits):
    if not inputs or len(inputs) > limits.max_files or archive and len(inputs) != 1:
        raise invalid()
    files = []
    if not archive:
        names = [safe_path(item.filename) for item in inputs]
        if any("/" in name for name in names) or len({name.casefold() for name in names}) != len(
            names
        ):
            raise invalid()
        budget = [min(limits.max_bytes, limits.max_expanded_bytes)]
        for name, item in zip(names, inputs, strict=True):
            files.append(write_file(root, "configs/" + name, item.stream, budget))
    else:
        # Bound compressed bytes before ZIP inspection. TemporaryFile is private and auto-closed.
        with tempfile.TemporaryFile(dir=root) as compressed:
            count = 0
            while data := inputs[0].stream.read(CHUNK):
                count += len(data)
                if count > limits.max_bytes:
                    raise ServiceError(ErrorCode.UPLOAD_TOO_LARGE)
                compressed.write(data)
            compressed.seek(0)
            try:
                with zipfile.ZipFile(compressed) as bundle:
                    infos = bundle.infolist()
                    if not infos or len(infos) > limits.max_files:
                        raise ServiceError(ErrorCode.UPLOAD_TOO_LARGE)
                    entries, known, roots = [], {}, set()
                    for info in infos:
                        if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                            raise invalid()
                        path = safe_path(info.orig_filename)
                        mode = info.external_attr >> 16
                        if info.flag_bits & 1 or stat.S_IFMT(mode) not in {
                            0,
                            stat.S_IFREG,
                            stat.S_IFDIR,
                        }:
                            raise invalid()
                        key = path.casefold()
                        if key in known:
                            raise invalid()
                        known[key] = info.is_dir()
                        parts = path.split("/")
                        if "configs" in parts and not info.is_dir():
                            roots.add(tuple(parts[: parts.index("configs")]))
                        entries.append((path, info))
                    if len(roots) != 1:
                        raise invalid()
                    prefix = next(iter(roots))
                    for path, info in entries:
                        parts = tuple(path.split("/"))
                        for i in range(1, len(parts)):
                            if known.get("/".join(parts[:i]).casefold()) is False:
                                raise invalid()
                        if info.is_dir() and parts == prefix[: len(parts)]:
                            continue
                        if parts[: len(prefix)] != prefix or len(parts) <= len(prefix):
                            raise invalid()
                    budget = [limits.max_expanded_bytes]
                    for path, info in entries:
                        if info.is_dir():
                            continue
                        logical = "/".join(path.split("/")[len(prefix) :])
                        with bundle.open(info) as source:
                            files.append(write_file(root, logical, source, budget))
            except (
                zipfile.BadZipFile,
                zlib.error,
                NotImplementedError,
                RuntimeError,
                EOFError,
                ValueError,
            ):
                raise invalid() from None
    if not files or not any(file.path.startswith("configs/") for file in files):
        raise invalid()
    files = tuple(sorted(files, key=lambda file: file.path))
    digest = hashlib.sha256(
        json.dumps(
            [(f.path, f.sha256, f.size_bytes) for f in files],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return files, digest
