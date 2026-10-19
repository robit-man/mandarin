#!/usr/bin/env python3
"""Collect exact Ubuntu corresponding sources and shard them for release."""

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_package import dependency_closure


def retrieve(url, path, expected=None, size=None):
    if path.is_file():
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if (expected is None or digest == expected) and (
            size is None or path.stat().st_size == size
        ):
            return digest
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        partial = path.with_name(path.name + ".partial")
        try:
            digest = hashlib.sha256()
            with urlopen(url, timeout=90) as source, partial.open("wb") as output:
                while block := source.read(1024 * 1024):
                    digest.update(block)
                    output.write(block)
            value = digest.hexdigest()
            if (expected and value != expected) or (
                size is not None and partial.stat().st_size != size
            ):
                raise RuntimeError("Corresponding source checksum/size mismatch: " + path.name)
            partial.replace(path)
            return value
        except Exception:
            partial.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()
    directory = ROOT / "build/corresponding-sources"
    directory.mkdir(parents=True, exist_ok=True)
    packages = dependency_closure(
        json.loads((ROOT / "packaging/runtime-packages.json").read_text())["packages"]
    )
    raw = subprocess.check_output(
        ["dpkg-query", "-W", "-f=${binary:Package}\t${source:Package}\t${source:Version}\n"]
        + [p["name"] for p in packages],
        text=True,
    )
    sources = {}
    overrides = json.loads((ROOT / "packaging/runtime-overrides.json").read_text())
    for line in raw.splitlines():
        binary, name, version = line.split("\t")
        if binary.split(":")[0] in overrides:
            override = overrides[binary.split(":")[0]]
            name, version = override["source_name"], override["source_version"]
        sources.setdefault((name, version), []).append(binary)

    def metadata(item):
        (name, version), binaries = item
        base = (
            "https://launchpad.net/ubuntu/+archive/primary/+sourcefiles/"
            + quote(name, safe="")
            + "/"
            + quote(version, safe="")
            + "/"
        )
        filename = name + "_" + version.split(":")[-1] + ".dsc"
        folder = directory / (name + "_" + version.split(":")[-1])
        descriptor = folder / filename
        sha = retrieve(base + quote(filename, safe=""), descriptor)
        text = descriptor.read_text()
        match = re.search(r"Checksums-Sha256:\n((?: .*(?:\n|$))+)", text)
        if not match:
            raise RuntimeError("No SHA256 source inventory: " + filename)
        files = [
            {
                "name": filename,
                "url": base + quote(filename, safe=""),
                "sha256": sha,
                "bytes": descriptor.stat().st_size,
            }
        ]
        for line in match.group(1).splitlines():
            digest, length, source_name = line.split()
            if Path(source_name).name != source_name or not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError("Invalid source descriptor: " + filename)
            files.append(
                {
                    "name": source_name,
                    "url": base + quote(source_name, safe=""),
                    "sha256": digest,
                    "bytes": int(length),
                }
            )
        return {
            "name": name,
            "version": version,
            "binaries": binaries,
            "directory": folder.name,
            "files": files,
        }

    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(metadata, item): item for item in sorted(sources.items())}
        for future in concurrent.futures.as_completed(futures):
            try:
                records.append(future.result())
            except Exception as error:
                raise RuntimeError("Missing exact source: " + str(futures[future][0])) from error
            if len(records) % 40 == 0:
                print(f"Resolved {len(records)}/{len(sources)} exact source packages", flush=True)
    records.sort(key=lambda row: (row["name"], row["version"]))
    manifest = {
        "schema_version": 1,
        "binary_packages": len(packages),
        "source_packages": len(records),
        "sources": records,
    }
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    (output / "corresponding-sources.json").write_text(json.dumps(manifest, indent=2) + "\n")
    total = sum(file["bytes"] for row in records for file in row["files"])
    print(f"Corresponding sources: {total // 1024 // 1024} MiB compressed originals", flush=True)
    if args.metadata_only:
        return
    work = [
        (file, directory / row["directory"] / file["name"])
        for row in records
        for file in row["files"]
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [
            pool.submit(retrieve, file["url"], path, file["sha256"], file["bytes"])
            for file, path in work
        ]
        for count, future in enumerate(concurrent.futures.as_completed(futures), 1):
            future.result()
            if count % 50 == 0:
                print(f"Verified {count}/{len(work)} source files", flush=True)
    shards = []
    current = []
    size = 0
    for _, path in sorted(work, key=lambda item: str(item[1])):
        if current and size + path.stat().st_size > 1400 * 1024 * 1024:
            shards.append(current)
            current, size = [], 0
        current.append(path)
        size += path.stat().st_size
    if current:
        shards.append(current)
    for index, paths in enumerate(shards, 1):
        target = output / f"mandarin-0.1.0-corresponding-sources-{index:02}.tar"
        with tarfile.open(target, "w") as archive:
            archive.add(output / "corresponding-sources.json", arcname="corresponding-sources.json")
            for path in paths:
                archive.add(path, arcname=str(path.relative_to(directory)))
        print(f"Created {target.name}", flush=True)


if __name__ == "__main__":
    main()
