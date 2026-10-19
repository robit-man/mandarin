"""Run inside a minimal Ubuntu container after installing the actual .deb."""

import json
import os
import subprocess
import time
from pathlib import Path


def main():
    for directory, _, files in os.walk("/opt/mandarin"):
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink() and (
                path.stat().st_mode & 0o6022 or os.listxattr(path, follow_symlinks=False)
            ):
                raise RuntimeError("Privileged/writable installed payload: " + str(path))
    from mandarin.runtime import bundle_environment

    os.environ.update(bundle_environment())
    from mandarin.ui import Application

    if Application.__module__ != "mandarin.ui":
        raise RuntimeError("Bundled GTK application did not load")
    from mandarin.runtime import python_command

    subprocess.run(python_command() + ["-c", "import mandarin.indicator"], check=True, timeout=15)
    work = Path("/work")
    report = []
    for path in [
        "/usr/bin/ffmpeg",
        "/usr/bin/convert",
        "/usr/bin/soffice",
        "/usr/bin/pandoc",
        "/usr/bin/python3",
    ]:
        if Path(path).exists():
            raise RuntimeError("Host converter/runtime unexpectedly present: " + path)
    result = subprocess.run(
        ["/usr/bin/mandarin", "--health"], capture_output=True, text=True, timeout=15
    )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    health = json.loads(result.stdout)
    if (
        health["profile"] != "bundled"
        or not all(health["engines"].values())
        or not health["isolation"]["available"]
    ):
        raise RuntimeError("Incomplete packaged runtime")
    if any(not value.startswith("/opt/mandarin/runtime/") for value in health["engines"].values()):
        raise RuntimeError("Host engine fallback detected")
    fixtures = json.loads((work / "cases.json").read_text())
    outputs = work / "outputs"
    outputs.mkdir(exist_ok=True)
    for index, case in enumerate(fixtures):
        started = time.monotonic()
        process = subprocess.run(
            [
                "/usr/bin/mandarin",
                "--convert",
                case["output"],
                "--output",
                str(outputs),
                case["path"],
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        row = {
            "input": case["input"],
            "output": case["output"],
            "status": "pass" if process.returncode == 0 else "fail",
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        }
        if process.returncode:
            row["error"] = (process.stderr + process.stdout)[-4096:]
        else:
            response = json.loads(process.stdout)
            if response["state"] != "succeeded" or not all(
                Path(path).exists() for path in response["outputs"]
            ):
                row.update(status="fail", error="Missing/unsuccessful published output")
        report.append(row)
        (work / "package-report.json").write_text(
            json.dumps(
                {
                    "health": health,
                    "network": "disabled",
                    "host_tools": "absent",
                    "uid": os.getuid(),
                    "results": report,
                },
                indent=2,
            )
        )
        if row["status"] == "fail" or index % 20 == 0:
            print(
                f"{index + 1}/{len(fixtures)} {case['input']} -> {case['output']}: {row['status']} "
                + row.get("error", "")[:200],
                flush=True,
            )
    failed = [row for row in report if row["status"] != "pass"]
    print(
        f"Packaged offline corpus: {len(report) - len(failed)}/{len(report)} passed as UID {os.getuid()}.",
        flush=True,
    )
    return bool(failed)


if __name__ == "__main__":
    raise SystemExit(main())
