#!/usr/bin/env python3
"""Reconstruct byte-identical source release assets from their pinned originals."""

import argparse
import concurrent.futures
import hashlib
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.collect_sources import retrieve


def assemble(archive, members, directory, manifest):
    for values in members:
        info = tarfile.TarInfo(values["name"])
        for key, value in values.items():
            setattr(info, key, value.encode("ascii") if key == "type" else value)
        path = manifest if info.name == "corresponding-sources.json" else directory / info.name
        with path.open("rb") as handle:
            archive.addfile(info, handle)


class DigestWriter:
    def __init__(self):
        self.digest = hashlib.sha256()

    def write(self, data):
        self.digest.update(data)
        return len(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    spec = json.loads((ROOT / "packaging/source-archives-0.1.0.json").read_text())
    manifest_path = ROOT / "dist/corresponding-sources.json"
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != spec["manifest_sha256"]:
        raise RuntimeError("Source manifest changed.")
    manifest = json.loads(manifest_path.read_text())
    directory = ROOT / "build/corresponding-sources"
    work = []
    expected = set()
    for source in manifest["sources"]:
        if Path(source["directory"]).name != source["directory"]:
            raise RuntimeError("Invalid source directory.")
        for file in source["files"]:
            if Path(file["name"]).name != file["name"]:
                raise RuntimeError("Invalid source filename.")
            relative = source["directory"] + "/" + file["name"]
            expected.add(relative)
            work.append((file, directory / relative))
    actual = [
        entry["name"]
        for shard in spec["archives"]
        for entry in shard["members"]
        if entry["name"] != "corresponding-sources.json"
    ]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise RuntimeError("Source archive specification differs from the manifest.")
    if not args.check_only:
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            futures = [
                pool.submit(retrieve, file["url"], path, file["sha256"], file["bytes"])
                for file, path in work
            ]
            for count, future in enumerate(concurrent.futures.as_completed(futures), 1):
                future.result()
                if count % 100 == 0:
                    print(f"Verified {count}/{len(work)} source files", flush=True)
    for shard in spec["archives"]:
        if args.check_only:
            sink = DigestWriter()
            with tarfile.open(mode="w|", fileobj=sink) as archive:
                assemble(archive, shard["members"], directory, manifest_path)
            digest = sink.digest.hexdigest()
        else:
            target = ROOT / "dist" / shard["name"]
            if Path(shard["name"]).name != shard["name"]:
                raise RuntimeError("Invalid archive filename.")
            with tarfile.open(target, "w") as archive:
                assemble(archive, shard["members"], directory, manifest_path)
            with target.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if digest != shard["sha256"]:
            raise RuntimeError("Archive reconstruction differs: " + shard["name"])
        print("Byte-identical source archive: " + shard["name"], flush=True)


if __name__ == "__main__":
    main()
