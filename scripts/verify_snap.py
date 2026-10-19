#!/usr/bin/env python3
"""Exercise installed strict Snap across representative engine families."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    (ROOT / "build/snap-report.json").unlink(missing_ok=True)
    artifact = ROOT / "dist/mandarin_0.1.0_amd64.snap"
    revision = Path("/snap/mandarin/current").resolve().name
    installed = Path("/var/lib/snapd/snaps") / f"mandarin_{revision}.snap"
    with artifact.open("rb") as handle:
        expected_sha = hashlib.file_digest(handle, "sha256").hexdigest()
    try:
        with installed.open("rb") as handle:
            installed_sha = hashlib.file_digest(handle, "sha256").hexdigest()
    except PermissionError:
        installed_sha = subprocess.check_output(
            ["sudo", "-n", "/usr/bin/sha256sum", "--", str(installed)], text=True, timeout=30
        ).split()[0]
    if installed_sha != expected_sha:
        raise RuntimeError("The installed Snap differs from the release artifact.")
    fixtures = json.loads((ROOT / "build/corpus/fixtures.json").read_text())
    output = ROOT / "build/snap-qa"
    output.mkdir(exist_ok=True)
    health = subprocess.run(
        ["snap", "run", "mandarin", "--health"],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    checks = [
        ("png", "heic"),
        ("heic", "png"),
        ("png", "avif"),
        ("svg", "pdf"),
        ("wav", "opus"),
        ("mp4", "webm"),
        ("md", "docx"),
        ("docx", "pdf"),
        ("csv", "pdf"),
        ("pdf", "png"),
        ("rar", "zip"),
        ("srt", "vtt"),
    ]
    report = {
        "health": json.loads(health.stdout),
        "distribution": "installed strict Snap",
        "results": [],
    }
    for source, target in checks:
        result = subprocess.run(
            [
                "snap",
                "run",
                "mandarin",
                "--convert",
                target,
                "--output",
                str(output),
                fixtures[source],
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        row = {
            "input": source,
            "output": target,
            "status": "pass" if result.returncode == 0 else "fail",
        }
        if result.returncode:
            row["error"] = result.stdout + result.stderr
        report["results"].append(row)
        (ROOT / "build/snap-report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(source, "->", target, row["status"], row.get("error", "")[:500], flush=True)
    report["sha256"] = expected_sha
    report["installed_revision"] = revision
    (ROOT / "build/snap-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return any(row["status"] != "pass" for row in report["results"])


if __name__ == "__main__":
    raise SystemExit(main())
