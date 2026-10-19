"""Conservative directed routes, filtered by actual engine health."""

from __future__ import annotations

from dataclasses import dataclass, field

from .operations import OPERATIONS

IMAGE = ("jpg", "png", "webp", "heic", "tiff", "avif", "bmp")
AUDIO = ("mp3", "m4a", "wav", "flac", "ogg", "opus", "aiff", "wma")
VIDEO = ("mp4", "mov", "mkv", "webm", "avi", "wmv")
DOCUMENT = ("docx", "md", "txt", "html", "epub")
SHEETS = ("xlsx", "ods", "csv", "tsv")
ARCHIVES = ("zip", "tar", "gz")


def targets(item: dict, engines: dict) -> list[str]:
    kind, family = item.get("format"), item.get("family")
    if family == "image" and engines.get("convert"):
        choices = list(IMAGE) + ["pdf"]
    elif family == "audio" and engines.get("ffmpeg"):
        choices = list(AUDIO)
    elif family == "video" and engines.get("ffmpeg"):
        choices = list(VIDEO) if kind == "gif" else list(VIDEO) + ["gif", "mp3"]
    elif family == "pdf":
        choices = ["jpg", "png", "txt", "md"] if engines.get("pdftoppm") else []
    elif family == "document":
        choices = (
            list(DOCUMENT) + ["pdf", "png", "jpg"]
            if engines.get("soffice") and engines.get("pandoc")
            else []
        )
        if kind == "pages":
            choices = ["docx", "pdf", "txt", "png", "jpg"] if engines.get("soffice") else []
    elif family == "presentation" and engines.get("soffice"):
        choices = ["pdf", "jpg", "png"]
    elif family == "spreadsheet" and engines.get("soffice"):
        choices = list(SHEETS) + ["pdf"]
    elif family == "subtitle":
        choices = ["srt", "vtt", "txt"]
    elif family == "archive" and engines.get("bsdtar"):
        choices = list(ARCHIVES)
    else:
        choices = []
    return [target for target in choices if target != kind]


def common_targets(items: list[dict], engines: dict) -> list[str]:
    if not items:
        return []
    choices = set(targets(items[0], engines))
    for item in items[1:]:
        choices.intersection_update(targets(item, engines))
    return sorted(choices)


def available_tools(items: list[dict], engines: dict) -> list:
    if not items:
        return []
    families = {item.get("family") for item in items}
    return [
        op
        for op in OPERATIONS
        if len(items) >= op.minimum_inputs
        and families <= set(op.families)
        and bool(engines.get(op.engine))
        and (
            op.id in {"images_pdf", "metadata", "compress"}
            or all(item.get("frames", 1) == 1 for item in items)
        )
    ]


@dataclass
class MenuItem:
    id: str
    label: str
    icon: str = "document-convert-symbolic"
    children: list["MenuItem"] = field(default_factory=list)
    description: str = ""


def menu(items: list[dict], engines: dict) -> list[MenuItem]:
    formats = [
        MenuItem(f"convert:{target}", target.upper(), "document-save-as-symbolic")
        for target in common_targets(items, engines)
    ]
    if len(formats) > 7:
        formats = [
            MenuItem("formats:common", "Common", children=formats[:6]),
            MenuItem("formats:more", "More formats", children=formats[6:]),
        ]
    tools = [
        MenuItem(op.id, op.name, "applications-graphics-symbolic", description=op.description)
        for op in available_tools(items, engines)
    ]
    if len(tools) > 7:
        tools = [
            MenuItem(
                f"tools:{i}",
                "Edit & compose" if i == 0 else "More tools",
                children=tools[i : i + 6],
            )
            for i in range(0, len(tools), 6)
        ]
    actions = [
        MenuItem("action:copy", "Copy files", "edit-copy-symbolic"),
        MenuItem("action:move", "Move files", "folder-move-symbolic"),
        MenuItem("action:share", "Share nearby", "send-to-symbolic"),
        MenuItem("action:path", "Copy path", "edit-copy-symbolic"),
        MenuItem("action:shelf", "Float", "view-pin-symbolic"),
        MenuItem("action:terminal", "Terminal", "utilities-terminal-symbolic"),
        MenuItem("action:reveal", "Reveal", "folder-open-symbolic"),
    ]
    return [
        MenuItem("convert", "Convert", "document-save-as-symbolic", formats),
        MenuItem("tools", "Tools", "applications-graphics-symbolic", tools),
        MenuItem("actions", "Actions", "folder-symbolic", actions),
    ]
