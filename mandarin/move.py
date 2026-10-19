"""Recoverable Move: claim without clobbering, copy/verify, retain recovery data.

The original pathname is relocated, but the held source is never automatically
deleted. This avoids deleting an inode that an uncooperative writer still uses.
Recovery locations are returned explicitly and journaled before mutations.
"""

import hashlib
import json
import os
import shutil
import stat
import tempfile
import uuid
from pathlib import Path

from .files import file_identity, publish


def manifest(path: Path) -> dict:
    members = [path] + sorted(path.rglob("*")) if path.is_dir() else [path]
    if len(members) > 20000:
        raise ValueError("Move supports no more than 20,000 members.")
    result = {}
    total = 0
    for member in members:
        info = member.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Move does not follow symlinks, hard links or special files.")
        total += info.st_size
        if total > 4 * 1024**3:
            raise ValueError("Move exceeds the 4 GiB verified-transfer limit.")
        before = file_identity(member)
        with member.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if file_identity(member) != before:
            raise ValueError("A source changed while it was being verified.")
        result[str(member.relative_to(path)) if path.is_dir() else "."] = [
            info.st_size,
            digest,
        ]
    return result


def move_files(paths: list[Path], destination: Path, state_dir: Path) -> dict:
    destination = destination.resolve()
    if not destination.is_dir():
        raise ValueError("Choose an existing destination folder.")
    identifier = uuid.uuid4().hex
    journal_dir = state_dir / "moves"
    journal_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    journal = journal_dir / (identifier + ".json")
    record = {"id": identifier, "state": "preparing", "items": []}

    def persist():
        temp = journal.with_suffix(".tmp")
        with temp.open("w") as handle:
            json.dump(record, handle, ensure_ascii=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, journal)
        directory_fd = os.open(journal_dir, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    persist()
    for source in paths:
        source = source.absolute()
        if source.is_symlink():
            raise ValueError("Move does not follow symlinks.")
        if (
            destination == source.parent
            or destination == source
            or destination.is_relative_to(source)
        ):
            raise ValueError("Choose a different folder outside the selected source.")
        identity = file_identity(source)
        expected = manifest(source)
        recovery = Path(tempfile.mkdtemp(prefix=".mandarin-move-recovery-", dir=source.parent))
        entry = {
            "original": str(source),
            "recovery": str(recovery / source.name),
            "destination": None,
            "state": "claiming",
        }
        record["items"].append(entry)
        persist()
        held = publish(source, recovery, source.name)
        try:
            if file_identity(held) != identity or manifest(held) != expected:
                raise ValueError(
                    "The source changed before Move could claim it. Its data is retained in the recovery folder."
                )
            entry["state"] = "copying"
            persist()
            staging = Path(tempfile.mkdtemp(prefix=".mandarin-move-", dir=destination))
            try:
                candidate = staging / source.name
                if held.is_dir():
                    shutil.copytree(held, candidate, symlinks=True)
                else:
                    shutil.copyfile(held, candidate)
                if manifest(candidate) != expected or manifest(held) != expected:
                    raise ValueError(
                        "The source changed during Move. All source data is retained in recovery."
                    )
                entry["destination"] = str(publish(candidate, destination, source.name))
                entry["state"] = "published-with-recovery"
                persist()
            finally:
                shutil.rmtree(staging, ignore_errors=True)
        except Exception as exc:
            entry["state"] = "needs-recovery"
            entry["error"] = str(exc)
            record["state"] = "incomplete"
            persist()
            raise ValueError(
                f"Move is incomplete. Source data is preserved at {held}. {exc}"
            ) from exc
    record["state"] = "completed-with-recovery"
    persist()
    return record
