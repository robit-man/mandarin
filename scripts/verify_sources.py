#!/usr/bin/env python3
"""Verify every exact source file inside the assembled release archives."""

import hashlib
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    directory = ROOT / "dist"
    manifest_path = directory / "corresponding-sources.json"
    manifest = json.loads(manifest_path.read_text())
    expected = {
        source["directory"] + "/" + file["name"]: file
        for source in manifest["sources"]
        for file in source["files"]
    }
    seen = set()
    shards = sorted(directory.glob("mandarin-0.1.0-corresponding-sources-*.tar"))
    if not shards:
        raise RuntimeError("No source archives.")
    for path in shards:
        metadata_found = False
        with tarfile.open(path, "r:") as archive:
            for member in archive:
                if not member.isfile():
                    raise RuntimeError("Non-regular source entry: " + member.name)
                with archive.extractfile(member) as handle:
                    digest = hashlib.file_digest(handle, "sha256").hexdigest()
                if member.name == "corresponding-sources.json":
                    if (
                        metadata_found
                        or digest != hashlib.sha256(manifest_path.read_bytes()).hexdigest()
                    ):
                        raise RuntimeError("Source manifest differs inside archive.")
                    metadata_found = True
                    continue
                file = expected.get(member.name)
                if not file or member.name in seen:
                    raise RuntimeError("Unexpected or duplicate source entry: " + member.name)
                if file["sha256"] != digest or file["bytes"] != member.size:
                    raise RuntimeError("Source archive content differs: " + member.name)
                seen.add(member.name)
        if not metadata_found:
            raise RuntimeError("Source archive is missing its manifest.")
    if seen != set(expected):
        raise RuntimeError("Source archives are incomplete.")
    report = {
        "status": "pass",
        "source_packages": manifest["source_packages"],
        "binary_packages": manifest["binary_packages"],
        "source_files": len(seen),
        "archives": [path.name for path in shards],
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "checks": [
            "every-source-present-once",
            "source-file-SHA256",
            "source-file-size",
            "matching-manifest",
        ],
    }
    (ROOT / "build/sources-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"PASS: {len(seen)} source files, {manifest['source_packages']} exact source packages, {len(shards)} archives."
    )


if __name__ == "__main__":
    main()
