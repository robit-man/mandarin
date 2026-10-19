"""Bounded libarchive decoding with no symlinks, hard links or special files."""

from __future__ import annotations

import ctypes as C
import ctypes.util
import gzip
import os
import shutil
import stat
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

MAX_BYTES = 2 * 1024**3
MAX_ENTRIES = 20000


def extract(source: Path, destination: Path) -> list[Path]:
    destination.mkdir(mode=0o700)
    if source.suffix.lower() == ".gz" and not source.name.endswith((".tar.gz", ".tgz")):
        target = destination / (source.stem or "file")
        try:
            with gzip.open(source, "rb") as inp, target.open("xb") as out:
                total = 0
                while block := inp.read(65536):
                    total += len(block)
                    if total > MAX_BYTES:
                        raise ValueError("Archive exceeds the 2 GiB extraction limit.")
                    out.write(block)
            # A .gz may contain a TAR despite its filename; inspect content before nesting.
            with target.open("rb") as handle:
                header = handle.read(512)
            if header[257:262] == b"ustar":
                nested = destination / "contents"
                files = extract(target, nested)
                target.unlink()
                for child in nested.iterdir():
                    child.rename(destination / child.name)
                nested.rmdir()
                return [p for p in destination.rglob("*") if p.is_file()]
            return [target]
        except Exception:
            shutil.rmtree(destination)
            raise
    library = C.CDLL(ctypes.util.find_library("archive") or "libarchive.so.13")
    signatures = {
        "archive_read_new": ([], C.c_void_p),
        "archive_read_support_filter_all": ([C.c_void_p], C.c_int),
        "archive_read_support_format_all": ([C.c_void_p], C.c_int),
        "archive_read_open_filename": ([C.c_void_p, C.c_char_p, C.c_size_t], C.c_int),
        "archive_read_next_header": ([C.c_void_p, C.POINTER(C.c_void_p)], C.c_int),
        "archive_read_data": ([C.c_void_p, C.c_void_p, C.c_size_t], C.c_ssize_t),
        "archive_entry_pathname": ([C.c_void_p], C.c_char_p),
        "archive_entry_filetype": ([C.c_void_p], C.c_uint),
        "archive_entry_symlink": ([C.c_void_p], C.c_char_p),
        "archive_entry_hardlink": ([C.c_void_p], C.c_char_p),
        "archive_read_free": ([C.c_void_p], C.c_int),
        "archive_error_string": ([C.c_void_p], C.c_char_p),
    }
    for name, (args, restype) in signatures.items():
        function = getattr(library, name)
        function.argtypes = args
        function.restype = restype
    reader = library.archive_read_new()
    library.archive_read_support_filter_all(reader)
    library.archive_read_support_format_all(reader)
    files, seen, total = [], set(), 0
    try:
        if library.archive_read_open_filename(reader, os.fsencode(source), 65536) != 0:
            raise ValueError("The archive could not be opened, or it needs a password.")
        entry = C.c_void_p()
        buffer = C.create_string_buffer(65536)
        while True:
            code = library.archive_read_next_header(reader, C.byref(entry))
            if code == 1:
                break
            if code < 0:
                raise ValueError("The archive is damaged or unsupported.")
            raw = library.archive_entry_pathname(entry)
            if not raw:
                raise ValueError("Archive member has no name.")
            name = os.fsdecode(raw)
            logical = PurePosixPath(name)
            if (
                logical.is_absolute()
                or ".." in logical.parts
                or "\\" in name
                or len(logical.parts) > 32
            ):
                raise ValueError("Archive contains an unsafe member path.")
            if str(logical) in ("", "."):
                continue
            if str(logical) in seen:
                raise ValueError("Archive contains duplicate member names.")
            seen.add(str(logical))
            if len(seen) > MAX_ENTRIES:
                raise ValueError("Archive has too many members.")
            if library.archive_entry_symlink(entry) or library.archive_entry_hardlink(entry):
                raise ValueError("Archive links are not extracted.")
            kind = library.archive_entry_filetype(entry)
            target = destination.joinpath(*logical.parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("Unsafe archive path.")
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if kind == stat.S_IFDIR:
                target.mkdir(exist_ok=True, mode=0o700)
                continue
            if kind != stat.S_IFREG:
                raise ValueError("Archive contains special filesystem nodes.")
            with target.open("xb") as out:
                while True:
                    size = library.archive_read_data(reader, buffer, len(buffer))
                    if size == 0:
                        break
                    if size < 0:
                        raise ValueError("Archive member could not be decoded.")
                    total += size
                    if total > MAX_BYTES:
                        raise ValueError("Archive exceeds the 2 GiB extraction limit.")
                    out.write(buffer.raw[:size])
            files.append(target)
        return files
    finally:
        library.archive_read_free(reader)


def pack(directory: Path, destination: Path, target: str) -> None:
    members = sorted(directory.rglob("*"))
    if target == "zip":
        with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as archive:
            for member in members:
                archive.write(member, member.relative_to(directory))
    else:
        with tarfile.open(destination, "x:gz" if target == "gz" else "x") as archive:
            for member in members:
                info = archive.gettarinfo(str(member), str(member.relative_to(directory)))
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mode &= 0o777
                if member.is_file():
                    with member.open("rb") as handle:
                        archive.addfile(info, handle)
                else:
                    archive.addfile(info)
