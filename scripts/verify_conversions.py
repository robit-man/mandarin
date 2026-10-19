#!/usr/bin/env python3
"""Execute a real generated-fixture corpus and report each directed route."""

import argparse
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from mandarin.capabilities import targets
from mandarin.jobs import JobManager
from mandarin.runtime import (
    engine,
    health,
    engine_path,
    native_command,
    sandbox_command,
    worker_environment,
    ROOT,
)


def wait(job):
    deadline = time.monotonic() + 120
    while job.state in {"queued", "running", "validating", "publishing"}:
        if time.monotonic() > deadline:
            job.cancel_event.set()
            for _ in range(40):
                if job.state not in {"queued", "running", "validating", "publishing"}:
                    break
                time.sleep(0.05)
            raise RuntimeError("Job timed out")
        time.sleep(0.025)
    if job.state != "succeeded":
        raise RuntimeError(job.error)
    return job.outputs[0]


def fixtures(root, manager):
    root.mkdir(parents=True, exist_ok=True)
    sources = {}
    image = root / "image.png"
    canvas = Image.new("RGB", (96, 64), "#edf0e2")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((10, 10, 70, 48), fill="#d45c1e")
    draw.text((12, 12), "Mandarin", fill="white")
    canvas.save(image)
    sources["png"] = image
    for target in ["jpg", "webp", "tiff", "bmp", "avif", "heic"]:
        sources[target] = wait(manager.submit([image], "convert:" + target, destination=root))
    svg = root / "vector.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="64"><rect width="96" height="64" fill="orange"/></svg>'
    )
    sources["svg"] = svg
    audio = root / "tone.wav"
    subprocess.run(
        engine("ffmpeg")
        + [
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.4",
            "-y",
            str(audio),
        ],
        check=True,
    )
    sources["wav"] = audio
    for target in ["mp3", "m4a", "flac", "ogg", "opus", "aiff", "wma"]:
        sources[target] = wait(manager.submit([audio], "convert:" + target, destination=root))
    video = root / "clip.mp4"
    subprocess.run(
        engine("ffmpeg")
        + [
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=orange:s=96x64:d=0.4",
            "-i",
            str(audio),
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-y",
            str(video),
        ],
        check=True,
    )
    sources["mp4"] = video
    for target in ["mov", "mkv", "webm", "avi", "wmv", "gif"]:
        sources[target] = wait(manager.submit([video], "convert:" + target, destination=root))
    document = root / "notes.md"
    document.write_text(
        "# Mandarin\n\nA local conversion test.\n\n| Name | Count |\n| --- | --- |\n| Orange | 3 |\n"
    )
    sources["md"] = document
    for target in ["docx", "txt", "html", "epub", "pdf"]:
        sources[target] = wait(manager.submit([document], "convert:" + target, destination=root))
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.active.append(["Name", "Count"])
    workbook.active.append(["Orange", 3])
    workbook.active.append(["Total", "=SUM(B2:B2)"])
    sheet = root / "figures.xlsx"
    workbook.save(sheet)
    sources["xlsx"] = sheet
    for target in ["ods", "csv", "tsv"]:
        sources[target] = wait(manager.submit([sheet], "convert:" + target, destination=root))
    subtitle = root / "captions.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:00,300\nMandarin\n")
    sources["srt"] = subtitle
    sources["vtt"] = wait(manager.submit([subtitle], "convert:vtt", destination=root))
    archive = root / "files.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("folder/note.txt", "Mandarin local archive")
    sources["zip"] = archive
    for target in ["tar", "gz"]:
        sources[target] = wait(manager.submit([archive], "convert:" + target, destination=root))
    (root / "fixtures.json").write_text(
        json.dumps({key: str(value) for key, value in sources.items()}, indent=2)
    )
    return sources


def add_legacy_fixtures(root, sources):
    rtf = root / "notes.rtf"
    rtf.write_text(r"{\rtf1\ansi Mandarin local document.\par A second paragraph.}")
    sources["rtf"] = rtf
    presentation = root / "presentation.pptx"
    import shutil

    shutil.copyfile(ROOT / "tests/fixtures/presentation.pptx", presentation)
    sources["pptx"] = presentation
    workspace = root / "legacy-generator"
    workspace.mkdir(exist_ok=True)
    for kind, source in [("ppt", presentation), ("xls", sources["xlsx"])]:
        output = workspace / ("legacy." + kind)
        command = native_command(ROOT / "build/mandarin-office") + [
            str(engine_path("soffice").parent),
            source.as_uri(),
            output.as_uri(),
            kind,
            (workspace / "profile").as_uri(),
        ]
        subprocess.run(
            sandbox_command(workspace, [source], command, 60),
            env=worker_environment(workspace),
            check=True,
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=65,
        )
        sources[kind] = output
    (root / "fixtures.json").write_text(
        json.dumps({key: str(value) for key, value in sources.items()}, indent=2)
    )
    return sources


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=Path("build/corpus"))
    parser.add_argument("--seed-only", action="store_true")
    args = parser.parse_args()
    root = args.fixtures.resolve()
    manager = JobManager(root / "state")
    results = []
    try:
        existing = root / "fixtures.json"
        sources = (
            {key: Path(value) for key, value in json.loads(existing.read_text()).items()}
            if existing.exists()
            else fixtures(root, manager)
        )
        if "pptx" not in sources:
            sources = add_legacy_fixtures(root, sources)
        sources["rar"] = ROOT / "tests/fixtures/libarchive-stored.rar"
        (root / "fixtures.json").write_text(
            json.dumps({key: str(value) for key, value in sources.items()}, indent=2) + "\n"
        )
        if args.seed_only:
            print(f"Seeded {len(sources)} source formats.")
            return 0
        output = root / "results"
        output.mkdir(exist_ok=True)
        engines = health()["engines"]
        for kind, source in sources.items():
            item = manager.inspect([source])[0]
            if item["format"] != kind:
                raise ValueError(f"Source misidentified: {kind} -> {item['format']}")
            for target in targets(item, engines):
                started = time.monotonic()
                try:
                    artifact = wait(
                        manager.submit([source], "convert:" + target, destination=output)
                    )
                    record = {
                        "input": kind,
                        "output": target,
                        "status": "pass",
                        "artifact": str(artifact),
                    }
                except Exception as exc:
                    record = {
                        "input": kind,
                        "output": target,
                        "status": "fail",
                        "error": str(exc),
                    }
                record["elapsed_ms"] = round((time.monotonic() - started) * 1000)
                results.append(record)
                print(
                    f"{kind:5} -> {target:5}: {record['status']}"
                    + (" " + record.get("error", "")[:150] if record["status"] == "fail" else ""),
                    flush=True,
                )
                (root / "report.json").write_text(
                    json.dumps(
                        {
                            "profile": "development-generated-fixtures",
                            "results": results,
                        },
                        indent=2,
                    )
                )
        failed = [row for row in results if row["status"] != "pass"]
        print(f"Corpus: {len(results) - len(failed)}/{len(results)} passed.")
        return bool(failed)
    finally:
        manager.close()


if __name__ == "__main__":
    raise SystemExit(main())
