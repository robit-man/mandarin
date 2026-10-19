"""Disposable parser/conversion/validation process. All calls require isolation."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import mimetypes
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import archiveio
from .operations import validate_options
from .probe import probe
from .runtime import engine

# Format mappings are built in. Optional host /etc MIME databases must never
# become a hidden dependency of the bundled spreadsheet writer.
mimetypes.knownfiles = []

Image = ImageOps = ImageDraw = ImageFont = ImageEnhance = None


def images():
    global Image, ImageOps, ImageDraw, ImageFont, ImageEnhance
    if Image is None:
        from PIL import Image, ImageOps, ImageDraw, ImageFont, ImageEnhance

        Image.MAX_IMAGE_PIXELS = 50000000


def emit(kind: str, **values):
    print(json.dumps({"event": kind, **values}, ensure_ascii=True), flush=True)


def run(command: list[str], timeout: int = 600, capture: bool = False) -> str:
    log = Path.cwd() / "engine.log"
    with log.open("wb") as error:
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else error,
            stderr=error,
            timeout=timeout,
            check=False,
        )
    if result.returncode:
        with log.open("rb") as stream:
            stream.seek(max(0, log.stat().st_size - 4096))
            detail = stream.read().decode("utf-8", "replace")
        raise ValueError(
            detail.strip() or f"{Path(command[0]).name} exited with status {result.returncode}."
        )
    if capture:
        if len(result.stdout) > 4 * 1024 * 1024:
            raise ValueError("Engine response is too large.")
        return result.stdout.decode("utf-8", "replace")
    return ""


def ffmpeg(
    inputs: list[str],
    output: Path,
    filters: list[str] | None = None,
    target: str | None = None,
):
    command = (
        engine("ffmpeg")
        + [
            "-hide_banner",
            "-v",
            "error",
            "-nostdin",
            "-n",
            "-threads",
            "2",
            "-filter_threads",
            "2",
            "-filter_complex_threads",
            "2",
            "-protocol_whitelist",
            "file,pipe",
        ]
        + inputs
    )
    if filters:
        command += filters
    if target:
        command += media_options(target)
    run(command + ["-threads", "2", str(output)])


def media_options(target: str) -> list[str]:
    audio = {
        "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
        "m4a": ["-c:a", "aac", "-b:a", "192k"],
        "wav": ["-c:a", "pcm_s16le"],
        "flac": ["-c:a", "flac"],
        "ogg": ["-c:a", "libvorbis", "-q:a", "5"],
        "opus": ["-c:a", "libopus", "-b:a", "128k"],
        "aiff": ["-c:a", "pcm_s16be"],
        "wma": ["-c:a", "wmav2", "-b:a", "192k"],
    }
    if target in audio:
        return ["-vn", "-map", "0:a:0"] + audio[target]
    if target == "gif":
        return ["-an", "-vf", "fps=15,scale='min(720,iw)':-2:flags=lanczos"]
    if target == "webm":
        return ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-c:a", "libopus"]
    if target == "wmv":
        return ["-c:v", "wmv2", "-c:a", "wmav2"]
    if target == "avi":
        return ["-c:v", "mpeg4", "-q:v", "4", "-c:a", "libmp3lame"]
    return [
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
    ]


def load_image(path: Path):
    images()
    if path.suffix.lower() in {".heic", ".avif", ".svg"}:
        temporary = Path.cwd() / f"decoded-{len(list(Path.cwd().glob('decoded-*')))}.png"
        if path.suffix.lower() == ".svg":
            run(engine("rsvg") + ["-o", str(temporary), str(path)])
        else:
            run(engine("convert") + [str(path) + "[0]", str(temporary)])
        path = temporary
    image = Image.open(path)
    if getattr(image, "n_frames", 1) > 1:
        raise ValueError(
            "This image has multiple frames. Convert its frames or export them to PDF before editing."
        )
    image.load()
    return ImageOps.exif_transpose(image).convert("RGBA")


def image_output(path: Path, output: Path, target: str, options: dict):
    if target == "pdf":
        images_to_pdf([path], output)
        return
    source = path
    if path.suffix.lower() == ".svg":
        source = Path.cwd() / "rasterized.png"
        run(engine("rsvg") + ["-o", str(source), str(path)])
    command = engine("convert") + [str(source) + "[0]", "-auto-orient"]
    if target in {"jpg", "bmp"}:
        command += ["-background", "white", "-alpha", "remove", "-alpha", "off"]
    command += ["-quality", str(int(options.get("quality", 85))), str(output)]
    run(command)


def images_to_pdf(paths: list[Path], output: Path):
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    document = canvas.Canvas(str(output))
    for path in paths:
        images()
        if path.suffix.lower() in {".png", ".tif", ".tiff", ".webp"}:
            from PIL import ImageSequence

            with Image.open(path) as decoded:
                frames = [
                    ImageOps.exif_transpose(frame.copy()).convert("RGBA")
                    for frame in ImageSequence.Iterator(decoded)
                ]
        else:
            frames = [load_image(path)]
        for image in frames:
            width, height = image.size
            document.setPageSize((width * 0.75, height * 0.75))
            document.drawImage(ImageReader(image), 0, 0, width * 0.75, height * 0.75, mask="auto")
            document.showPage()
    document.save()


def render_pdf(source: Path, folder: Path, target: str):
    folder.mkdir()
    run(
        engine("pdftoppm")
        + [
            "-r",
            "300",
            "-png" if target == "png" else "-jpeg",
            str(source),
            str(folder / "page"),
        ]
    )


def office(source: Path, target: str, folder: Path) -> Path:
    from .runtime import ROOT, PACKAGED, engine_path, native_command

    folder.mkdir(exist_ok=True)
    helper = ROOT / ("bin/mandarin-office" if PACKAGED else "build/mandarin-office")
    output = folder / (source.stem + "." + target)
    format_name = "csv" if target == "tsv" else target
    run(
        native_command(helper)
        + [
            str(engine_path("soffice").parent),
            source.as_uri(),
            output.as_uri(),
            format_name,
            (Path.cwd() / "office-profile").as_uri(),
        ]
    )
    if target == "tsv":
        with output.open(newline="") as handle:
            rows = list(csv.reader(handle))
        with output.open("w", newline="") as handle:
            csv.writer(handle, delimiter="\t").writerows(rows)
    matches = [p for p in folder.iterdir() if p.is_file() and p.stem == source.stem]
    if len(matches) != 1:
        raise ValueError("The office engine did not produce the requested format.")
    return matches[0]


def convert(source: Path, item: dict, target: str, output: Path, options: dict):
    family = item["family"]
    if family == "image":
        if item.get("frames", 1) > 1 and target != "pdf":
            images()
            from PIL import ImageSequence

            output.mkdir()
            with Image.open(source) as decoded:
                for index, frame in enumerate(ImageSequence.Iterator(decoded)):
                    intermediate = Path.cwd() / f"frame-{index:04}.png"
                    ImageOps.exif_transpose(frame.copy()).save(intermediate)
                    image_output(
                        intermediate,
                        output / f"frame-{index + 1:04}.{target}",
                        target,
                        options,
                    )
        else:
            image_output(source, output, target, options)
    elif family in {"audio", "video"}:
        ffmpeg(["-i", str(source)], output, target=target)
    elif family == "pdf":
        if target in {"png", "jpg"}:
            render_pdf(source, output, target)
        elif target in {"txt", "md"}:
            run(engine("pdftotext") + ["-layout", "-enc", "UTF-8", str(source), str(output)])
        else:
            raise ValueError("Editable PDF reconstruction is not certified in this build.")
    elif family in {"document", "spreadsheet", "presentation"}:
        document_source = source
        if family == "spreadsheet" and item["format"] in {"csv", "tsv"}:
            if source.stat().st_size > 32 * 1024 * 1024:
                raise ValueError("Delimited tables are limited to 32 MiB per file.")
            delimiter = "\t" if item["format"] == "tsv" else ","
            with source.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle, delimiter=delimiter))
            if len(rows) > 100000 or sum(len(row) for row in rows) > 1000000:
                raise ValueError("The table exceeds the row/cell safety limit.")
            if target in {"csv", "tsv"}:
                with output.open("w", encoding="utf-8", newline="") as handle:
                    csv.writer(handle, delimiter="\t" if target == "tsv" else ",").writerows(rows)
                return
            from openpyxl import Workbook
            from openpyxl.cell import WriteOnlyCell

            workbook = Workbook(write_only=True)
            sheet = workbook.create_sheet("Table")
            for row in rows:
                cells = []
                for value in row:
                    cell = WriteOnlyCell(sheet, value=value)
                    cell.data_type = "s"
                    cells.append(cell)
                sheet.append(cells)
            document_source = Path.cwd() / (source.stem + "-table.xlsx")
            workbook.save(document_source)
            if target == "xlsx":
                shutil.copyfile(document_source, output)
                return
        if (
            family == "document"
            and item["format"] in {"md", "txt", "html", "epub"}
            and target in {"pdf", "png", "jpg"}
        ):
            from .runtime import BUNDLE, PACKAGED

            document_source = Path.cwd() / (source.stem + "-structured.docx")
            reader = {
                "md": "markdown",
                "txt": "markdown",
                "html": "html",
                "epub": "epub",
            }[item["format"]]
            data_dir = (BUNDLE if PACKAGED else Path("/")) / "usr/share/pandoc/data"
            run(
                engine("pandoc")
                + [
                    "--data-dir=" + str(data_dir),
                    "--reference-doc=" + str(Path(__file__).parent / "resources/reference.docx"),
                    "-f",
                    reader,
                    "-t",
                    "docx",
                    "-o",
                    str(document_source),
                    str(source),
                ]
            )
        if target in {"png", "jpg"}:
            pdf = office(document_source, "pdf", Path.cwd() / "office-pdf")
            render_pdf(pdf, output, target)
        elif (
            family in {"spreadsheet", "presentation"}
            or target == "pdf"
            or item["format"] in {"pages", "rtf", "doc"}
            and target in {"docx", "txt"}
        ):
            actual = office(document_source, target, Path.cwd() / "office-result")
            shutil.copyfile(actual, output)
        else:
            reader = {
                "md": "markdown",
                "txt": "markdown",
                "docx": "docx",
                "epub": "epub",
                "html": "html",
            }.get(item["format"])
            if reader is None:
                document_source = office(source, "docx", Path.cwd() / "office-intermediate")
                reader = "docx"
            writer = {"md": "markdown", "txt": "plain"}.get(target, target)
            extra = (
                ["--reference-doc=" + str(Path(__file__).parent / "resources/reference.docx")]
                if target == "docx"
                else []
            )
            from .runtime import BUNDLE, PACKAGED

            data_dir = (BUNDLE if PACKAGED else Path("/")) / "usr/share/pandoc/data"
            run(
                engine("pandoc")
                + ["--data-dir=" + str(data_dir)]
                + extra
                + ["-f", reader, "-t", writer, "-o", str(output), str(document_source)]
            )
    elif family == "subtitle":
        convert_subtitle(source, output, target)
    elif family == "archive":
        unpacked = Path.cwd() / "unpacked"
        archiveio.extract(source, unpacked)
        archiveio.pack(unpacked, output, target)
    else:
        raise ValueError("This conversion is not supported.")


def convert_subtitle(source: Path, output: Path, target: str):
    text = source.read_text(encoding="utf-8-sig")
    if len(text) > 10000000:
        raise ValueError("Subtitle file is too large.")
    text = text.replace("\r\n", "\n")
    if target == "txt":
        lines = [
            line
            for line in text.splitlines()
            if line.strip()
            and line.strip() != "WEBVTT"
            and not line.strip().isdigit()
            and "-->" not in line
        ]
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif target == "vtt":
        text = re.sub(r"(\d\d:\d\d:\d\d),(\d{3})", r"\1.\2", text)
        output.write_text("WEBVTT\n\n" + text.removeprefix("WEBVTT").lstrip(), encoding="utf-8")
    else:
        text = re.sub(r"(\d\d:\d\d:\d\d)\.(\d{3})", r"\1,\2", text)
        blocks = text.removeprefix("WEBVTT").strip().split("\n\n")
        cleaned = []
        for block in blocks:
            lines = block.splitlines()
            if not any("-->" in line for line in lines):
                continue
            while lines and "-->" not in lines[0]:
                lines.pop(0)
            lines[0] = re.sub(r"(-->\s*\d\d:\d\d:\d\d,\d{3}).*", r"\1", lines[0])
            cleaned.append(f"{len(cleaned) + 1}\n" + "\n".join(lines))
        output.write_text("\n\n".join(cleaned) + "\n", encoding="utf-8")


def pdf_tool(operation: str, sources: list[Path], output: Path, options: dict):
    from pypdf import PdfReader, PdfWriter

    if operation == "merge_pdf":
        writer = PdfWriter()
        for source in sources:
            reader = PdfReader(str(source))
            if reader.is_encrypted:
                raise ValueError("Unlock encrypted PDFs before merging.")
            for page in reader.pages:
                writer.add_page(page)
        with output.open("wb") as handle:
            writer.write(handle)
        return
    reader = PdfReader(str(sources[0]))
    if reader.is_encrypted:
        raise ValueError("Unlock this PDF before editing.")
    selection = options.get("pages", "all").strip()
    indexes = list(range(len(reader.pages))) if selection == "all" else []
    if selection != "all":
        for section in selection.split(","):
            if not re.fullmatch(r"\s*\d+(?:-\d+)?\s*", section):
                raise ValueError("Use page numbers or ranges, for example 1-3,5.")
            numbers = [int(n) for n in section.strip().split("-")]
            indexes.extend(range(numbers[0] - 1, numbers[-1]))
    if not indexes or len(indexes) > 10000 or any(i < 0 or i >= len(reader.pages) for i in indexes):
        raise ValueError("The page selection is outside this PDF.")
    if operation == "split_pdf":
        output.mkdir()
        for i in indexes:
            writer = PdfWriter()
            writer.add_page(reader.pages[i])
            with (output / f"page-{i + 1:04}.pdf").open("xb") as handle:
                writer.write(handle)
    else:
        writer = PdfWriter()
        for i in indexes:
            page = reader.pages[i]
            if int(options.get("rotation", 0)):
                page.rotate(int(options["rotation"]))
            writer.add_page(page)
        with output.open("wb") as handle:
            writer.write(handle)


def image_tool(operation: str, sources: list[Path], output: Path, options: dict):
    image = load_image(sources[0])
    x, y = int(options.get("x", 0)), int(options.get("y", 0))
    width, height = (
        int(options.get("width", image.width)),
        int(options.get("height", image.height)),
    )
    color = options.get("color", "#202020")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("Use a six-digit color such as #202020.")
    if operation in {"crop_image", "redact_image", "annotate"}:
        if x >= image.width or y >= image.height:
            raise ValueError("The selected area starts outside the image.")
        width, height = min(width, image.width - x), min(height, image.height - y)
    if operation == "crop_image":
        image = image.crop((x, y, x + width, y + height))
    elif operation == "resize":
        image = ImageOps.contain(image, (width, height), Image.Resampling.LANCZOS)
    elif operation == "edit_image":
        for key, enhancement in [
            ("brightness", ImageEnhance.Brightness),
            ("contrast", ImageEnhance.Contrast),
            ("saturation", ImageEnhance.Color),
            ("sharpness", ImageEnhance.Sharpness),
        ]:
            image = enhancement(image).enhance(float(options[key]))
    elif operation == "annotate":
        draw = ImageDraw.Draw(image)
        shape = options["shape"]
        if shape == "text":
            font_path = next(
                (
                    p
                    for p in [
                        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                        Path(__file__).parent.parent
                        / "runtime/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    ]
                    if p.exists()
                ),
                None,
            )
            font = (
                ImageFont.truetype(str(font_path), int(options["font_size"]))
                if font_path
                else ImageFont.load_default()
            )
            draw.text((x, y), options["text"], font=font, fill=color)
        elif shape == "rectangle":
            draw.rectangle((x, y, x + width, y + height), outline=color, width=4)
        elif shape == "ellipse":
            draw.ellipse((x, y, x + width, y + height), outline=color, width=4)
        else:
            draw.line((x, y, x + width, y + height), fill=color, width=5)
            angle = math.atan2(height, width)
            end = (x + width, y + height)
            draw.polygon(
                [
                    end,
                    (
                        end[0] - 20 * math.cos(angle - 0.45),
                        end[1] - 20 * math.sin(angle - 0.45),
                    ),
                    (
                        end[0] - 20 * math.cos(angle + 0.45),
                        end[1] - 20 * math.sin(angle + 0.45),
                    ),
                ],
                fill=color,
            )
    elif operation == "background":
        padding, radius = int(options["padding"]), int(options["radius"])
        mask = Image.new("L", image.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, image.width, image.height), radius=radius, fill=255
        )
        base = Image.new("RGBA", (image.width + padding * 2, image.height + padding * 2), color)
        base.paste(image, (padding, padding), mask)
        image = base
    elif operation == "collage":
        columns, cell, gap = (
            int(options["columns"]),
            int(options["cell"]),
            int(options["spacing"]),
        )
        rows = math.ceil(len(sources) / columns)
        if columns * cell * rows * cell > 100000000:
            raise ValueError("The collage would exceed 100 megapixels.")
        base = Image.new(
            "RGBA",
            (columns * cell + (columns + 1) * gap, rows * cell + (rows + 1) * gap),
            color,
        )
        for index, source in enumerate(sources):
            tile = ImageOps.fit(load_image(source), (cell, cell))
            base.paste(
                tile,
                (
                    gap + (index % columns) * (cell + gap),
                    gap + (index // columns) * (cell + gap),
                ),
            )
        image = base
    elif operation == "redact_image":
        boxes = [(x, y, width, height)]
        if options["detect"] == "faces":
            import cv2
            import numpy as np
            from .runtime import BUNDLE, PACKAGED

            cascade = (
                BUNDLE if PACKAGED else Path("/")
            ) / "usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml"
            detector = cv2.CascadeClassifier(str(cascade))
            boxes = detector.detectMultiScale(
                cv2.cvtColor(np.array(image), cv2.COLOR_RGBA2GRAY), 1.1, 4
            )
        elif options["detect"] == "text":
            ocr_input = Path.cwd() / "ocr-input.png"
            image.save(ocr_input)
            tsv = run(engine("tesseract") + [str(ocr_input), "stdout", "tsv"], capture=True)
            boxes = [
                (int(r["left"]), int(r["top"]), int(r["width"]), int(r["height"]))
                for r in csv.DictReader(tsv.splitlines(), delimiter="\t")
                if r.get("text", "").strip()
            ]
        draw = ImageDraw.Draw(image)
        for left, top, w, h in boxes:
            draw.rectangle((int(left), int(top), int(left + w), int(top + h)), fill=color)
    image.info.clear()
    image.save(output, format="PNG")


def media_tool(operation: str, sources: list[Path], items: list[dict], output: Path, options: dict):
    source, item = sources[0], items[0]
    inputs, filters = ["-i", str(source)], []
    family = item["family"]
    target = "mp4" if family == "video" else "wav"
    start, end = float(options.get("start", 0)), float(options.get("end", 0))
    duration = item.get("duration", 0)
    if start and duration and start >= duration:
        raise ValueError("The start is beyond the end of this file.")
    if operation.startswith("trim_"):
        filters += ["-ss", str(start)]
        if end:
            filters += ["-t", str(end - start)]
    elif operation == "mute":
        filters += ["-an"]
    elif operation == "crop_video":
        filters += [
            "-vf",
            f"crop={int(options['width'])}:{int(options['height'])}:{int(options['x'])}:{int(options['y'])}",
        ]
    elif operation == "speed":
        speed = options["speed"]
        filters += ["-vf", f"setpts=PTS/{speed}"]
        if any(s["codec_type"] == "audio" for s in item.get("streams", [])):
            filters += ["-af", f"atempo={math.sqrt(speed)},atempo={math.sqrt(speed)}"]
    elif operation == "snapshot":
        ffmpeg(inputs, output, ["-ss", str(start), "-frames:v", "1"])
        return
    elif operation == "normalize":
        filters += [
            "-af",
            f"loudnorm=I={options['loudness']}:TP={options['peak']}:LRA={options['range']}",
        ]
    elif operation == "channels":
        left, right = options["left_gain"], options["right_gain"]
        channels = next(
            (s.get("channels", 1) for s in item.get("streams", []) if s["codec_type"] == "audio"),
            1,
        )
        if channels == 1:
            pan = f"pan=stereo|c0={left}*c0|c1={right}*c0"
        else:
            pan = f"pan=stereo|c0={left}*c0|c1={right}*c1"
        if options["channels"] == "mono":
            pan += ",pan=mono|c0=0.5*c0+0.5*c1"
        filters += ["-af", pan]
    elif operation == "bleep":
        if not end:
            end = min(duration, start + 1)
        count = next(
            (
                stream.get("channels", 1)
                for stream in item.get("streams", [])
                if stream["codec_type"] == "audio"
            ),
            1,
        )
        expression = "|".join(
            f"if(between(t,{start},{end}),0.2*sin(2*PI*1000*t),val({channel}))"
            for channel in range(count)
        )
        filters += ["-af", f"aeval='{expression}':c=same"]
    elif operation == "redact_video":
        color = options["color"]
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("Invalid redaction color.")
        interval = f":enable='between(t,{start},{end})'" if end else ""
        filters += [
            "-vf",
            f"drawbox=x={int(options['x'])}:y={int(options['y'])}:w={int(options['width'])}:h={int(options['height'])}:color={color.replace('#', '0x')}:t=fill{interval}",
        ]
    elif operation == "visualizer":
        width, height = int(options["width"]), int(options["height"])
        color = options["color"]
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("Invalid waveform color.")
        ffmpeg(
            inputs,
            output,
            [
                "-filter_complex",
                f"[0:a]showwaves=s={width}x{height}:mode=line:colors={color.replace('#', '0x')},format=yuv420p[v]",
                "-map",
                "[v]",
                "-map",
                "0:a",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
            ],
        )
        return
    elif operation == "split_video":
        if not duration:
            raise ValueError("The video duration could not be determined.")
        output.mkdir()
        parts = int(options["parts"])
        for number in range(parts):
            ffmpeg(
                inputs,
                output / f"clip-{number + 1:03}.mp4",
                ["-ss", str(duration * number / parts), "-t", str(duration / parts)],
                "mp4",
            )
        return
    elif operation == "join":
        normalized = []
        first_video = next(s for s in items[0]["streams"] if s["codec_type"] == "video")
        width, height = first_video["width"] // 2 * 2, first_video["height"] // 2 * 2
        for index, path in enumerate(sources):
            clip = Path.cwd() / f"normalized-{index}.mp4"
            video_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
            has_audio = any(s["codec_type"] == "audio" for s in items[index].get("streams", []))
            if has_audio:
                ffmpeg(
                    ["-i", str(path)],
                    clip,
                    ["-vf", video_filter, "-ar", "48000", "-ac", "2"],
                    "mp4",
                )
            else:
                ffmpeg(
                    [
                        "-i",
                        str(path),
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=r=48000:cl=stereo",
                    ],
                    clip,
                    ["-vf", video_filter, "-shortest"],
                    "mp4",
                )
            normalized.append(clip)
        concat = Path.cwd() / "concat.txt"
        concat.write_text("".join(f"file '{p.name}'\n" for p in normalized))
        ffmpeg(["-f", "concat", "-safe", "1", "-i", str(concat)], output, ["-c", "copy"])
        return
    ffmpeg(inputs, output, filters, target)


def execute(request: dict) -> dict:
    from .capabilities import common_targets
    from .operations import BY_ID
    from .runtime import ENGINE_PATHS

    sources = [Path(p) for p in request["inputs"]]
    items = [probe(path) for path in sources]
    operation = request["operation"]
    options = validate_options(operation, request.get("options", {}))
    if operation.startswith("convert:"):
        if operation.split(":", 1)[1] not in common_targets(
            items, {name: True for name in ENGINE_PATHS}
        ):
            raise ValueError("The selected files do not share this conversion path.")
    else:
        definition = BY_ID[operation]
        if len(sources) < definition.minimum_inputs or not {
            item["family"] for item in items
        } <= set(definition.families):
            raise ValueError("This tool does not support this selection.")
    output_root = Path.cwd() / "outputs"
    output_root.mkdir()
    aggregate = operation in {"collage", "images_pdf", "merge_pdf", "join"}
    results = []
    groups = [list(range(len(sources)))] if aggregate else [[i] for i in range(len(sources))]
    for indexes in groups:
        i = indexes[0]
        source, item = sources[i], items[i]
        group_sources, group_items = (
            [sources[n] for n in indexes],
            [items[n] for n in indexes],
        )
        emit(
            "progress",
            fraction=i / max(1, len(sources)),
            message="Processing " + request["names"][i],
        )
        label = Path(request["names"][i]).stem
        if operation.startswith("convert:"):
            target = operation.split(":", 1)[1]
            suffix = "tar.gz" if target == "gz" else target
            directory = (
                target in {"png", "jpg"}
                and item["family"] in {"pdf", "presentation", "document"}
                or item["family"] == "image"
                and item.get("frames", 1) > 1
                and target != "pdf"
            )
            output = output_root / (f"result-{i}" + ("" if directory else "." + suffix))
            convert(source, item, target, output, options)
            name = f"{label} {target.upper()}" if directory else f"{label}.{suffix}"
        elif operation == "images_pdf":
            output = output_root / "images.pdf"
            images_to_pdf(group_sources, output)
            name = "Images.pdf"
        elif operation in {"merge_pdf", "split_pdf", "organize_pdf"}:
            output = output_root / ("pages" if operation == "split_pdf" else "document.pdf")
            pdf_tool(operation, group_sources, output, options)
            name = f"{label} {operation.replace('_', ' ')}" + ("" if output.is_dir() else ".pdf")
        elif operation == "extract":
            output = output_root / f"extracted-{i}"
            archiveio.extract(source, output)
            name = f"{label} extracted"
        elif operation == "qr":
            qr_input = Path.cwd() / f"qr-input-{i}.png"
            load_image(source).save(qr_input)
            decoded = run(engine("zbarimg") + ["--quiet", "--raw", str(qr_input)], capture=True)
            output = output_root / f"qr-{i}.txt"
            output.write_text(decoded)
            name = f"{label} QR.txt"
        elif operation == "metadata":
            if options["mode"] == "inspect":
                metadata = run(engine("exiftool") + ["-json", str(source)], capture=True)
                output = output_root / f"metadata-{i}.json"
                output.write_text(metadata)
                name = f"{label} metadata.json"
            else:
                output = output_root / f"metadata-{i}.{item['format']}"
                shutil.copyfile(source, output)
                if item["family"] in {"video", "audio"}:
                    output.unlink()
                    edits = ["-map", "0", "-c", "copy", "-map_metadata", "-1"]
                    if options["mode"] == "edit":
                        edits += [
                            "-metadata",
                            "title=" + options["title"],
                            "-metadata",
                            "artist=" + options["author"],
                        ]
                    ffmpeg(["-i", str(source)], output, edits)
                else:
                    edits = (
                        ["-all="]
                        if options["mode"] == "remove"
                        else [
                            "-Title=" + options["title"],
                            "-Artist=" + options["author"],
                            "-Author=" + options["author"],
                        ]
                    )
                    if item["family"] == "image" and options["mode"] == "remove":
                        edits += ["-tagsFromFile", "@", "-Orientation", "-ICC_Profile"]
                    run(engine("exiftool") + ["-overwrite_original"] + edits + [str(output)])
                    if item["family"] == "pdf" and options["mode"] == "remove":
                        rewritten = Path.cwd() / "metadata-rewritten.pdf"
                        run(engine("qpdf") + [str(output), str(rewritten)])
                        rewritten.replace(output)
                name = f"{label} metadata.{item['format']}"
        elif operation == "compress":
            target = item["format"]
            if target in {"wav", "aiff"}:
                target = "flac"
            output = output_root / f"compressed-{i}.{target}"
            target_bytes = int(options["target_kb"] * 1024) or int(
                source.stat().st_size * (1 - options["percent"] / 100)
            )
            if source.stat().st_size <= target_bytes and target == item["format"]:
                shutil.copyfile(source, output)
            elif item["family"] == "image":
                quality = int(options["quality"])
                target_bytes = int(options["target_kb"] * 1024) or int(
                    source.stat().st_size * (1 - options["percent"] / 100)
                )
                for attempt in range(8):
                    image_output(source, output, target, {"quality": quality})
                    if not target_bytes or output.stat().st_size <= target_bytes:
                        break
                    quality = max(10, quality - 10)
                if target_bytes and output.stat().st_size > target_bytes:
                    raise ValueError(
                        "This size target could not be met. Choose a larger size or a different output format."
                    )
            elif item["family"] in {"video", "audio"}:
                if (
                    item["family"] == "audio"
                    and target not in {"flac"}
                    and item.get("duration", 0) > 0
                ):
                    bitrate = max(8000, min(320000, int(target_bytes * 7 / item["duration"])))
                    settings = media_options(target)
                    if "-q:a" in settings:
                        position = settings.index("-q:a")
                        del settings[position : position + 2]
                    ffmpeg(["-i", str(source)], output, settings + ["-b:a", str(bitrate)])
                else:
                    ffmpeg(["-i", str(source)], output, target=target)
            else:
                run(
                    engine("gs")
                    + [
                        "-dSAFER",
                        "-dBATCH",
                        "-dNOPAUSE",
                        "-dQUIET",
                        "-sDEVICE=pdfwrite",
                        "-dCompatibilityLevel=1.7",
                        "-dPDFSETTINGS="
                        + (
                            "/screen"
                            if options["quality"] < 45
                            else "/ebook"
                            if options["quality"] < 75
                            else "/printer"
                        ),
                        "-sOutputFile=" + str(output),
                        str(source),
                    ]
                )
            if target_bytes and output.stat().st_size > target_bytes:
                raise ValueError(
                    "The requested size target could not be met. Choose a larger size or another output format."
                )
            name = f"{label} compressed.{target}"
        elif item["family"] == "image":
            output = output_root / f"edited-{i}.png"
            image_tool(operation, group_sources, output, options)
            name = f"{label} {operation.replace('_', ' ')}.png"
        elif item["family"] in {"audio", "video"}:
            suffix = (
                "png"
                if operation == "snapshot"
                else "mp4"
                if operation in {"visualizer", "join"} or item["family"] == "video"
                else "wav"
            )
            output = output_root / (
                f"media-{i}" if operation == "split_video" else f"media-{i}.{suffix}"
            )
            media_tool(operation, group_sources, group_items, output, options)
            name = f"{label} {operation.replace('_', ' ')}" + (
                "" if output.is_dir() else "." + suffix
            )
        else:
            raise ValueError("This tool does not support the selected files.")
        results.append(
            {
                "path": str(output.relative_to(Path.cwd())),
                "name": name,
                "source_index": i,
            }
        )
    return {"artifacts": results}


def validate_artifacts(request: dict) -> dict:
    records = []
    for artifact in request["artifacts"]:
        path = Path.cwd() / artifact["path"]
        if not path.resolve().is_relative_to(Path.cwd() / "outputs") or path.is_symlink():
            raise ValueError("Unsafe artifact manifest.")
        members = list(path.rglob("*")) if path.is_dir() else [path]
        if len(members) > 20000:
            raise ValueError("Too many output artifacts.")
        for member in members:
            if member.is_symlink() or not (member.is_file() or member.is_dir()):
                raise ValueError("Unsafe output node.")
            if member.is_dir():
                continue
            if member.stat().st_nlink != 1:
                raise ValueError("Output contains hard links.")
            item = probe(member)
            if item["family"] == "image":
                run(engine("convert") + [str(member) + "[0]", "null:"])
            elif item["family"] in {"video", "audio"}:
                run(
                    engine("ffmpeg")
                    + [
                        "-v",
                        "error",
                        "-nostdin",
                        "-protocol_whitelist",
                        "file,pipe",
                        "-i",
                        str(member),
                        "-t",
                        "2",
                        "-f",
                        "null",
                        "-",
                    ]
                )
            elif item["family"] == "pdf":
                run(engine("pdfinfo") + [str(member)])
            elif item["family"] == "archive":
                archiveio.extract(member, Path.cwd() / f"validate-archive-{len(records)}")
            with member.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            records.append(
                {
                    "path": str(member.relative_to(Path.cwd())),
                    "size": member.stat().st_size,
                    "sha256": digest,
                    "format": item["format"],
                }
            )
    return {"validated": records}


def main() -> int:
    if os.environ.get("MANDARIN_WORKER") != "1":
        print("Run workers through the Mandarin supervisor.", file=sys.stderr)
        return 125
    try:
        request = json.loads(Path(sys.argv[1]).read_text())
        mode = request.get("mode")
        if mode == "probe":
            result = {"items": [probe(Path(p)) for p in request["inputs"]]}
        elif mode == "validate":
            result = validate_artifacts(request)
        elif mode == "preview":
            source = Path(request["inputs"][0])
            if request.get("operation"):
                preview_path = Path.cwd() / "edited-preview.png"
                image_tool(
                    request["operation"],
                    [source],
                    preview_path,
                    validate_options(request["operation"], request.get("options", {})),
                )
                source = preview_path
            image = load_image(source)
            image.thumbnail((640, 640))
            image = image.convert("RGBA")
            path = Path.cwd() / "preview.rgba"
            path.write_bytes(image.tobytes())
            result = {"width": image.width, "height": image.height, "path": str(path)}
        else:
            result = execute(request)
        emit("result", **result)
        return 0
    except Exception as exc:
        emit("error", message=str(exc)[:4096])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
