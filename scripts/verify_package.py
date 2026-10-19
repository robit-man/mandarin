#!/usr/bin/env python3
"""Install and verify the full package offline with no host converter tools."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mandarin.capabilities import targets
from mandarin.jobs import JobManager
from mandarin.runtime import health


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--image", default="ubuntu:24.04")
    parser.add_argument("--sample", action="store_true")
    args = parser.parse_args()
    package = args.package.resolve()
    if not package.is_file():
        raise ValueError("The package has not been built.")
    if not args.sample:
        (package.parent / "verification.json").unlink(missing_ok=True)
    corpus = ROOT / "build/corpus"
    if not (corpus / "fixtures.json").exists():
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/verify_conversions.py"),
                "--seed-only",
            ],
            check=True,
        )
    source_paths = json.loads((corpus / "fixtures.json").read_text())
    work = ROOT / "build" / ("package-qa-" + args.image.replace(":", "-"))
    work.mkdir(exist_ok=True)
    (work / "package-report.json").unlink(missing_ok=True)
    inputs = work / "inputs"
    inputs.mkdir(exist_ok=True)
    cases = []
    manager = JobManager(work / "host-probe-state")
    try:
        engines = health()["engines"]
        for kind, value in source_paths.items():
            source = Path(value)
            target = inputs / (kind + source.suffix)
            shutil.copyfile(source, target)
            item = manager.inspect([source])[0]
            choices = targets(item, engines)
            if args.sample:
                choices = choices[:1]
            for output in choices:
                cases.append(
                    {
                        "input": kind,
                        "output": output,
                        "path": "/work/inputs/" + target.name,
                    }
                )
    finally:
        manager.close()
    (work / "cases.json").write_text(json.dumps(cases, indent=2))
    name = "mandarin-qa-" + uuid.uuid4().hex[:12]
    subprocess.run(
        ["docker", "image", "inspect", args.image],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    try:
        subprocess.run(
            [
                "docker",
                "create",
                "--name",
                name,
                "--network",
                "none",
                "--memory",
                "4g",
                "--cpus",
                "3",
                "--security-opt",
                "seccomp=unconfined",
                "--tmpfs",
                "/tmp:rw,nosuid,size=1g",
                "-v",
                str(package) + ":/package.deb:ro",
                "-v",
                str(ROOT / "scripts/isolated_smoke.py") + ":/qa.py:ro",
                "-v",
                str(ROOT / "tests/test_tools.py") + ":/qa-tools.py:ro",
                "-v",
                str(work) + ":/work:rw",
                args.image,
                "sleep",
                "infinity",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(["docker", "start", name], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["docker", "exec", name, "dpkg", "--install", "/package.deb"], check=True)
        library = ":".join(
            "/opt/mandarin/runtime/" + path
            for path in [
                "usr/lib/libreoffice/program",
                "usr/lib/x86_64-linux-gnu",
                "usr/lib/x86_64-linux-gnu/pulseaudio",
                "usr/lib/x86_64-linux-gnu/blas",
                "usr/lib/x86_64-linux-gnu/lapack",
                "lib/x86_64-linux-gnu",
                "usr/lib",
            ]
        )
        runner = [
            "docker",
            "exec",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--workdir",
            "/work",
            "-e",
            "HOME=/work",
            "-e",
            "XDG_STATE_HOME=/work/state",
            "-e",
            "PYTHONHOME=/opt/mandarin/runtime/usr",
            "-e",
            "PYTHONPATH=/opt/mandarin",
            "-e",
            "PYTHONNOUSERSITE=1",
            "-e",
            "LD_LIBRARY_PATH=" + library,
            name,
            "/opt/mandarin/runtime/lib64/ld-linux-x86-64.so.2",
            "--library-path",
            library,
            "/opt/mandarin/runtime/usr/bin/python3.12",
            "-P",
        ]
        result = subprocess.run(runner + ["/qa.py"], check=False)
        if result.returncode:
            return result.returncode
        result = subprocess.run(runner + ["/qa-tools.py"], check=False)
        if result.returncode == 0 and not args.sample:
            with package.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            image_id = subprocess.check_output(
                ["docker", "image", "inspect", args.image, "--format", "{{.Id}}"], text=True
            ).strip()
            (package.parent / "verification.json").write_text(
                json.dumps(
                    {
                        "package": package.name,
                        "sha256": digest,
                        "status": "pass",
                        "checks": [
                            "offline-install",
                            "unprivileged-conversion-corpus",
                            "packaged-tool-operations",
                            "bundled-GTK-import",
                        ],
                        "base_image": args.image,
                        "base_image_id": image_id,
                        "conversions": len(cases),
                        "uid": os.getuid(),
                        "evidence": str(work.relative_to(ROOT)),
                    },
                    indent=2,
                )
                + "\n"
            )
        return result.returncode
    finally:
        subprocess.run(
            ["docker", "rm", "-f", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


if __name__ == "__main__":
    raise SystemExit(main())
