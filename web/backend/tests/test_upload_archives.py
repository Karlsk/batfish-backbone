import io
import stat
import zipfile

import pytest

from app.contracts.errors import ServiceError
from app.modules.uploads.archive import prepare
from app.modules.uploads.schemas import UploadInput, UploadLimits


def zipped(entries, *, symlink=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, data in entries:
            info = zipfile.ZipInfo(path)
            if path == symlink:
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, data)
    stream.seek(0)
    return stream


def run(tmp_path, entries, **kwargs):
    root = tmp_path / "files"
    root.mkdir()
    return prepare(
        [UploadInput("input.zip", zipped(entries, **kwargs))],
        archive=True,
        root=root,
        limits=UploadLimits(),
    )


@pytest.mark.parametrize(
    "path",
    [
        "../escape",
        "/etc/passwd",
        "root/configs/../../escape",
        "C:/configs/a",
        "root\\configs\\a",
        "root/configs/a\x00hidden",
    ],
)
def test_traversal_rejected(tmp_path, path):
    # ZIP writer truncates NUL filenames; patch the bytes to exercise the reader instead.
    if "\x00" in path:
        stream = zipped([("root/configs/a_hidden", b"x")])
        raw = stream.getvalue().replace(b"a_hidden", b"a\x00hidden")
        stream = io.BytesIO(raw)
        with pytest.raises(ServiceError):
            prepare(
                [UploadInput("x.zip", stream)], archive=True, root=tmp_path, limits=UploadLimits()
            )
    else:
        with pytest.raises(ServiceError):
            run(tmp_path, [("root/configs/good", b"ok"), (path, b"bad")])
    assert not (tmp_path.parent / "escape").exists()


@pytest.mark.parametrize(
    "entries",
    [
        [("a/configs/r1", b"x"), ("b/configs/r2", b"y")],
        [("readme", b"x")],
        [("configs/a", b"x"), ("configs/a/b", b"y")],
        [("configs/a", b"x"), ("configs/a", b"y")],
        [("configs/a.zip", b"x")],
        [("configs/a", b"PK\x03\x04" + b"x" * 10)],
    ],
)
def test_zip_roots_conflicts_and_nested_rejected(tmp_path, entries):
    with pytest.raises(ServiceError):
        run(tmp_path, entries)


def test_symlink_and_encrypted_zip_rejected(tmp_path):
    with pytest.raises(ServiceError):
        run(tmp_path, [("configs/link", b"/etc/passwd")], symlink="configs/link")
    stream = zipped([("configs/a", b"x")])
    data = bytearray(stream.getvalue())
    # Set encryption flags in local and central headers.
    for signature, offset in [(b"PK\x03\x04", 6), (b"PK\x01\x02", 8)]:
        index = data.index(signature) + offset
        data[index] |= 1
    with pytest.raises(ServiceError):
        prepare(
            [UploadInput("x.zip", io.BytesIO(data))],
            archive=True,
            root=tmp_path,
            limits=UploadLimits(),
        )


def test_original_bytes_and_hash_preserved(tmp_path):
    original = "sysname 交换机\r\n".encode("gb18030") + b"\x1b[31m#\r\n"
    files, digest = run(
        tmp_path, [("snapshot/configs/r1.cfg", original), ("snapshot/hosts/h.json", b"{}")]
    )
    config = next(file for file in files if file.path.startswith("configs/"))
    assert (tmp_path / "files" / str(config.id)).read_bytes() == original
    assert config.encoding == "gb18030" and config.line_count == 2
    assert len(digest) == 64 and len(files) == 2


@pytest.mark.parametrize(
    "limits",
    [UploadLimits(max_bytes=5), UploadLimits(max_expanded_bytes=5), UploadLimits(max_files=1)],
)
def test_zip_actual_limits(tmp_path, limits):
    stream = zipped([("configs/a", b"x" * 10), ("configs/b", b"y")])
    with pytest.raises(ServiceError):
        prepare([UploadInput("x.zip", stream)], archive=True, root=tmp_path, limits=limits)


def test_stream_bytes_not_declared_size_and_duplicate_names(tmp_path):
    with pytest.raises(ServiceError):
        prepare(
            [UploadInput("a", io.BytesIO(b"x" * 20))],
            archive=False,
            root=tmp_path,
            limits=UploadLimits(max_bytes=10),
        )
    with pytest.raises(ServiceError):
        prepare(
            [UploadInput("a", io.BytesIO(b"x")), UploadInput("a", io.BytesIO(b"y"))],
            archive=False,
            root=tmp_path,
            limits=UploadLimits(),
        )


def test_corrupt_deflate_is_validation_error(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("configs/r1", b"hostname r1\n" * 20)
    data = bytearray(stream.getvalue())
    name_length = int.from_bytes(data[26:28], "little")
    extra_length = int.from_bytes(data[28:30], "little")
    data[30 + name_length + extra_length] = 0xFF
    with pytest.raises(ServiceError) as error:
        prepare(
            [UploadInput("x.zip", io.BytesIO(data))],
            archive=True,
            root=tmp_path,
            limits=UploadLimits(),
        )
    assert error.value.code == "VALIDATION_ERROR"


@pytest.mark.parametrize("compression", [zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA])
def test_unsupported_zip_algorithm_is_validation_error(tmp_path, compression):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression) as archive:
        archive.writestr("configs/r1", b"hostname r1\n")
    stream.seek(0)
    with pytest.raises(ServiceError) as error:
        prepare([UploadInput("x.zip", stream)], archive=True, root=tmp_path, limits=UploadLimits())
    assert error.value.code == "VALIDATION_ERROR"
