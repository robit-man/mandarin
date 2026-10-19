#!/usr/bin/env python3
"""Validate the full runtime inventory and fail on missing/modified tools."""

import argparse
import hashlib
import json
from pathlib import Path


def verify(root: Path):
    manifest = json.loads((root / "runtime-manifest.json").read_text())
    failures = []
    for relative, record in manifest["files"].items():
        path = root / relative
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            failures.append("Missing or escaped runtime file: " + relative)
            continue
        if path.stat().st_size != record["bytes"]:
            failures.append("Wrong size: " + relative)
            continue
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if digest != record["sha256"]:
            failures.append("Hash mismatch: " + relative)
    for name, relative in manifest["required_engines"].items():
        path = root / "runtime" / relative.lstrip("/")
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            failures.append("Missing engine: " + name)
    for relative in [
        "bin/mandarin-sandbox",
        "bin/mandarin-office",
        "runtime/lib64/ld-linux-x86-64.so.2",
        "runtime/usr/bin/python3.12",
        "runtime/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
        "runtime/usr/share/tesseract-ocr/5/tessdata/eng.traineddata",
        "mandarin/resources/reference.docx",
    ]:
        if not (root / relative).is_file():
            failures.append("Missing required asset: " + relative)
    report = {
        "runtime_files": len(manifest["files"]),
        "pinned_packages": len(manifest["packages"]),
        "failures": failures,
        "status": "fail" if failures else "pass",
    }
    print(json.dumps(report, indent=2))
    return bool(failures)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path("/opt/mandarin"))
    arguments = parser.parse_args()
    raise SystemExit(verify(arguments.root))
