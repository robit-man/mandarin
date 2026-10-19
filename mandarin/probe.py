"""Content identification; executed only inside the worker boundary."""

from __future__ import annotations

import json
import re
import subprocess
import zipfile
from pathlib import Path

from .runtime import engine


def probe(path: Path) -> dict:
    if path.is_dir():
        return {
            "path": str(path),
            "name": path.name,
            "format": "folder",
            "family": "folder",
            "size": 0,
        }
    size = path.stat().st_size
    with path.open("rb") as stream:
        head = stream.read(8192)
    extension = path.suffix.lower().lstrip(".")
    kind, family = "unknown", "unknown"
    if head.startswith(b"%PDF-"):
        kind, family = "pdf", "pdf"
    elif head.startswith(b"PK\x03\x04"):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) > 100000:
                raise ValueError("Archive has too many entries.")
            if any(x.startswith("word/") for x in names):
                kind, family = "docx", "document"
            elif any(x.startswith("ppt/") for x in names):
                kind, family = "pptx", "presentation"
            elif any(x.startswith("xl/") for x in names):
                kind, family = "xlsx", "spreadsheet"
            elif "mimetype" in names and archive.getinfo("mimetype").file_size < 256:
                mime = archive.read("mimetype").decode("ascii", "replace")
                if mime == "application/epub+zip":
                    kind, family = "epub", "document"
                elif "spreadsheet" in mime:
                    kind, family = "ods", "spreadsheet"
            elif extension == "pages" and any(x.startswith("Index/") for x in names):
                kind, family = "pages", "document"
            if kind == "unknown":
                kind, family = "zip", "archive"
    elif head.startswith(b"\x1f\x8b"):
        kind, family = "gz", "archive"
    elif head.startswith(b"Rar!\x1a\x07"):
        kind, family = "rar", "archive"
    elif len(head) > 262 and head[257:262] == b"ustar":
        kind, family = "tar", "archive"
    elif head.startswith(b"{\\rtf"):
        kind, family = "rtf", "document"
    elif head.startswith(b"\xd0\xcf\x11\xe0"):
        kind, family = (
            ("xls", "spreadsheet")
            if extension == "xls"
            else ("ppt", "presentation")
            if extension == "ppt"
            else ("doc", "document")
        )
    elif b"<svg" in head[:4096].lower():
        kind, family = "svg", "image"
    elif (
        head.startswith((b"\x89PNG", b"\xff\xd8\xff", b"II*\x00", b"MM\x00*", b"BM"))
        or head[8:12] == b"WEBP"
        or (head[4:8] == b"ftyp" and head[8:12] in (b"heic", b"heix", b"mif1", b"avif", b"avis"))
    ):
        result = subprocess.run(
            engine("identify") + ["-ping", "-format", "%m %w %h", str(path) + "[0]"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode:
            raise ValueError("The image could not be decoded.")
        parts = result.stdout.split()
        kind = {
            "JPEG": "jpg",
            "PNG": "png",
            "TIFF": "tiff",
            "BMP": "bmp",
            "WEBP": "webp",
            "HEIC": "heic",
            "AVIF": "avif",
        }.get(parts[0], "unknown")
        if kind != "unknown":
            family = "image"
            width, height = int(parts[1]), int(parts[2])
            if width * height > 100000000:
                raise ValueError("The image exceeds the 100-megapixel safety limit.")
            frames = 1
            if kind in {"png", "tiff", "webp"}:
                from PIL import Image

                with Image.open(path) as decoded:
                    frames = getattr(decoded, "n_frames", 1)
                if frames > 1000:
                    raise ValueError("The image exceeds the 1,000-frame safety limit.")
            return {
                "path": str(path),
                "name": path.name,
                "format": kind,
                "family": family,
                "size": size,
                "width": width,
                "height": height,
                "frames": frames,
            }
    if kind == "unknown" and (
        extension in {"txt", "md", "markdown", "html", "csv", "tsv", "srt", "vtt"}
    ):
        text = head.decode("utf-8-sig")
        if "\0" in text:
            raise ValueError("This file is not supported text.")
        if extension == "vtt" and text.startswith("WEBVTT"):
            kind, family = "vtt", "subtitle"
        elif extension == "srt" and re.search(r"\d\d:\d\d:\d\d[,.]\d{3}\s*-->", text):
            kind, family = "srt", "subtitle"
        elif extension in {"csv", "tsv"}:
            kind, family = extension, "spreadsheet"
        else:
            kind, family = ("md" if extension == "markdown" else extension), "document"
    if kind == "unknown":
        result = subprocess.run(
            engine("ffprobe")
            + [
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-probesize",
                "2000000",
                "-analyzeduration",
                "2000000",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode == 0:
            media = json.loads(result.stdout)
            streams = media.get("streams", [])
            video = any(
                s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
                for s in streams
            )
            audio = any(s.get("codec_type") == "audio" for s in streams)
            known = {
                "jpeg": "jpg",
                "aif": "aiff",
                "wave": "wav",
                "oga": "ogg",
                "m4v": "mp4",
            }.get(extension, extension)
            if video:
                kind, family = (
                    known if known in {"mp4", "mov", "mkv", "webm", "avi", "wmv", "gif"} else "mp4",
                    "video",
                )
            elif audio:
                kind, family = (
                    known
                    if known in {"mp3", "m4a", "wav", "flac", "ogg", "opus", "aiff", "wma"}
                    else "wav",
                    "audio",
                )
            if family in {"video", "audio"}:
                return {
                    "path": str(path),
                    "name": path.name,
                    "format": kind,
                    "family": family,
                    "size": size,
                    "duration": float(media.get("format", {}).get("duration", 0)),
                    "streams": [
                        {
                            key: stream[key]
                            for key in (
                                "codec_type",
                                "codec_name",
                                "width",
                                "height",
                                "sample_rate",
                                "channels",
                            )
                            if key in stream
                        }
                        for stream in streams
                    ],
                }
    return {
        "path": str(path),
        "name": path.name,
        "format": kind,
        "family": family,
        "size": size,
    }
