"""Payloads run as their caller and carry no filesystem privileges."""

import os
from pathlib import Path


def sanitize(root: Path):
    root.chmod(root.stat().st_mode & 0o755)
    for attribute in os.listxattr(root, follow_symlinks=False):
        os.removexattr(root, attribute, follow_symlinks=False)
    changed = []
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in folders + files:
            path = Path(directory) / name
            if path.is_symlink():
                continue
            mode = path.stat().st_mode & 0o7777
            safe = mode & 0o755
            if mode != safe:
                path.chmod(safe)
                if mode & 0o6000:
                    changed.append(str(path.relative_to(root)))
            for attribute in os.listxattr(path, follow_symlinks=False):
                os.removexattr(path, attribute, follow_symlinks=False)
    return changed


def violations(root: Path):
    failures = []
    if root.stat().st_mode & 0o6022 or os.listxattr(root, follow_symlinks=False):
        failures.append("Unsafe payload root permissions or attributes")
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in folders + files:
            path = Path(directory) / name
            if path.is_symlink():
                continue
            relative = str(path.relative_to(root))
            if path.stat().st_mode & 0o6022:
                failures.append("Privileged or writable payload mode: " + relative)
            if os.listxattr(path, follow_symlinks=False):
                failures.append("Extended attributes in payload: " + relative)
    return failures
