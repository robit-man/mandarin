"""Bounded URI parsing and non-destructive filesystem publication."""

from __future__ import annotations

import ctypes
import errno
import os
import stat
from pathlib import Path
from urllib.parse import unquote_to_bytes, urlsplit


def parse_uris(data: str | bytes) -> list[Path]:
    raw = data.encode("utf-8", "surrogateescape") if isinstance(data, str) else data
    if len(raw) > 1024 * 1024:
        raise ValueError("The dragged file list is too large.")
    result = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(b"#"):
            continue
        parts = urlsplit(line.decode("ascii"))
        if (
            parts.scheme != "file"
            or parts.netloc not in ("", "localhost")
            or parts.query
            or parts.fragment
        ):
            raise ValueError(
                "Choose local files. Web links and remote file addresses are not downloaded."
            )
        decoded = unquote_to_bytes(parts.path)
        if b"\0" in decoded or not decoded.startswith(b"/"):
            raise ValueError("The file address is invalid.")
        result.append(Path(os.fsdecode(decoded)))
        if len(result) > 1000:
            raise ValueError("Select no more than 1,000 files at once.")
    return result


def file_identity(path: Path) -> tuple[int, int, int, int]:
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) and not stat.S_ISDIR(st.st_mode):
        raise ValueError("Only regular files and folders are accepted.")
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns


def publish(staged: Path, directory: Path, basename: str) -> Path:
    """Atomic same-filesystem no-replace publication using held directory FDs."""
    if Path(basename).name != basename or basename in ("", ".", ".."):
        raise ValueError("Invalid output name")
    if staged.is_symlink() or not (staged.is_file() or staged.is_dir()):
        raise ValueError("The output is not a regular file or output folder.")
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    source_fd = os.open(staged.parent, os.O_DIRECTORY | os.O_RDONLY | os.O_CLOEXEC)
    destination_fd = os.open(directory, os.O_DIRECTORY | os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    stem, suffix = Path(basename).stem, Path(basename).suffix
    try:
        if staged.is_file():
            with staged.open("rb") as handle:
                os.fsync(handle.fileno())
        else:
            members = list(staged.rglob("*"))
            for member in members:
                if member.is_file():
                    with member.open("rb") as handle:
                        os.fsync(handle.fileno())
            for staged_directory in sorted(
                [staged] + [p for p in members if p.is_dir()],
                key=lambda p: len(p.parts),
                reverse=True,
            ):
                descriptor = os.open(staged_directory, os.O_DIRECTORY | os.O_RDONLY | os.O_CLOEXEC)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        for number in range(1, 10001):
            name = basename if number == 1 else f"{stem} ({number}){suffix}"
            if (
                rename(
                    source_fd,
                    os.fsencode(staged.name),
                    destination_fd,
                    os.fsencode(name),
                    1,
                )
                == 0
            ):
                os.fsync(destination_fd)
                return directory / name
            error = ctypes.get_errno()
            if error != errno.EEXIST:
                raise OSError(error, "Could not safely publish output", name)
        raise RuntimeError("Too many output name collisions.")
    finally:
        os.close(source_fd)
        os.close(destination_fd)
