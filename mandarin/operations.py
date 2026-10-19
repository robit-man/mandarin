"""One typed operation registry shared by radial, list, CLI and workers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Parameter:
    key: str
    label: str
    kind: str = "number"
    default: object = 0
    minimum: float = 0
    maximum: float = 100000
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Operation:
    id: str
    name: str
    families: tuple[str, ...]
    engine: str
    parameters: tuple[Parameter, ...] = ()
    minimum_inputs: int = 1
    aggregate: bool = False
    description: str = ""


QUALITY = Parameter("quality", "Quality", default=85, minimum=10, maximum=100)
START = Parameter("start", "Start (seconds)", default=0, minimum=0, maximum=86400)
END = Parameter("end", "End (seconds; 0 means the end)", default=0, minimum=0, maximum=86400)
WIDTH = Parameter("width", "Width (pixels)", default=1280, minimum=1, maximum=16000)
HEIGHT = Parameter("height", "Height (pixels)", default=720, minimum=1, maximum=16000)
X = Parameter("x", "Left (pixels)", default=0, maximum=16000)
Y = Parameter("y", "Top (pixels)", default=0, maximum=16000)
COLOR = Parameter("color", "Color", "text", "#202020")
TEXT = Parameter("text", "Text", "text", "")

OPERATIONS = [
    Operation(
        "compress",
        "Compress",
        ("image", "video", "audio", "pdf"),
        "ffmpeg",
        (
            QUALITY,
            Parameter("percent", "Reduce size by (%)", default=40, minimum=0, maximum=95),
            Parameter(
                "target_kb",
                "Maximum size (KB; 0 uses quality)",
                default=0,
                maximum=4000000,
            ),
        ),
        description="Save a smaller copy. Impossible targets fail explicitly.",
    ),
    Operation(
        "metadata",
        "Edit metadata",
        ("image", "video", "audio", "pdf"),
        "exiftool",
        (
            Parameter(
                "mode",
                "Metadata operation",
                "choice",
                "remove",
                choices=("remove", "inspect", "edit"),
            ),
            Parameter("title", "Title", "text", ""),
            Parameter("author", "Author", "text", ""),
        ),
        description="Inspect, edit or remove supported metadata in a new copy.",
    ),
    Operation("crop_image", "Crop image", ("image",), "convert", (X, Y, WIDTH, HEIGHT)),
    Operation("resize", "Resize image", ("image",), "convert", (WIDTH, HEIGHT)),
    Operation(
        "edit_image",
        "Adjust photo",
        ("image",),
        "convert",
        (
            Parameter("brightness", "Brightness", default=1, minimum=0.1, maximum=3),
            Parameter("contrast", "Contrast", default=1, minimum=0.1, maximum=3),
            Parameter("saturation", "Saturation", default=1, minimum=0, maximum=3),
            Parameter("sharpness", "Sharpness", default=1, minimum=0, maximum=5),
        ),
    ),
    Operation(
        "annotate",
        "Annotate image",
        ("image",),
        "convert",
        (
            TEXT,
            X,
            Y,
            Parameter("font_size", "Text size", default=32, minimum=8, maximum=300),
            Parameter(
                "shape",
                "Shape",
                "choice",
                "text",
                choices=("text", "rectangle", "ellipse", "arrow"),
            ),
            WIDTH,
            HEIGHT,
            COLOR,
        ),
    ),
    Operation(
        "background",
        "Add background",
        ("image",),
        "convert",
        (
            Parameter("padding", "Padding (pixels)", default=48, maximum=2000),
            Parameter("radius", "Corner radius (pixels)", default=20, maximum=1000),
            Parameter("color", "Background color", "text", "#f3e9d9"),
        ),
    ),
    Operation(
        "collage",
        "Make a collage",
        ("image",),
        "convert",
        (
            Parameter("columns", "Columns", default=2, minimum=1, maximum=12),
            Parameter("cell", "Cell size (pixels)", default=600, minimum=64, maximum=4000),
            Parameter("spacing", "Spacing (pixels)", default=16, maximum=300),
            COLOR,
        ),
        2,
        True,
    ),
    Operation("images_pdf", "Create PDF", ("image",), "convert", (), 1, True),
    Operation("trim_video", "Trim video", ("video",), "ffmpeg", (START, END)),
    Operation("crop_video", "Crop video", ("video",), "ffmpeg", (X, Y, WIDTH, HEIGHT)),
    Operation(
        "speed",
        "Change video speed",
        ("video",),
        "ffmpeg",
        (Parameter("speed", "Speed multiplier", default=2, minimum=0.25, maximum=4),),
    ),
    Operation("mute", "Remove audio", ("video",), "ffmpeg"),
    Operation("snapshot", "Save video frame", ("video",), "ffmpeg", (START,)),
    Operation(
        "split_video",
        "Split video",
        ("video",),
        "ffmpeg",
        (Parameter("parts", "Equal parts", default=2, minimum=2, maximum=50),),
    ),
    Operation("join", "Join videos", ("video",), "ffmpeg", (), 2, True),
    Operation(
        "normalize",
        "Normalize audio",
        ("audio",),
        "ffmpeg",
        (
            Parameter(
                "loudness",
                "Integrated loudness (LUFS)",
                default=-16,
                minimum=-40,
                maximum=-5,
            ),
            Parameter("peak", "True peak (dBTP)", default=-1.5, minimum=-9, maximum=0),
            Parameter("range", "Loudness range (LU)", default=11, minimum=1, maximum=30),
        ),
    ),
    Operation("trim_audio", "Trim audio", ("audio",), "ffmpeg", (START, END)),
    Operation(
        "channels",
        "Convert audio channels",
        ("audio",),
        "ffmpeg",
        (
            Parameter("channels", "Channels", "choice", "stereo", choices=("mono", "stereo")),
            Parameter("left_gain", "Left volume", default=1, minimum=0, maximum=2),
            Parameter("right_gain", "Right volume", default=1, minimum=0, maximum=2),
        ),
    ),
    Operation(
        "visualizer",
        "Create audio visualizer",
        ("audio",),
        "ffmpeg",
        (WIDTH, HEIGHT, COLOR),
    ),
    Operation("bleep", "Bleep audio", ("audio",), "ffmpeg", (START, END)),
    Operation(
        "redact_image",
        "Redact image",
        ("image",),
        "convert",
        (
            X,
            Y,
            WIDTH,
            HEIGHT,
            COLOR,
            Parameter(
                "detect",
                "Suggest regions",
                "choice",
                "manual",
                choices=("manual", "faces", "text"),
            ),
        ),
    ),
    Operation(
        "redact_video",
        "Redact video",
        ("video",),
        "ffmpeg",
        (X, Y, WIDTH, HEIGHT, START, END, COLOR),
    ),
    Operation("merge_pdf", "Merge PDFs", ("pdf",), "qpdf", (), 2, True),
    Operation(
        "split_pdf",
        "Split PDF",
        ("pdf",),
        "qpdf",
        (Parameter("pages", "Page ranges (for example 1-3,5)", "text", "all"),),
    ),
    Operation(
        "organize_pdf",
        "Organize PDF pages",
        ("pdf",),
        "qpdf",
        (
            Parameter("pages", "Page order (for example 3,1,2)", "text", "all"),
            Parameter(
                "rotation",
                "Rotate clockwise",
                "choice",
                "0",
                choices=("0", "90", "180", "270"),
            ),
        ),
    ),
    Operation("extract", "Extract archive", ("archive",), "bsdtar"),
    Operation("qr", "Read QR code", ("image",), "zbarimg"),
]
BY_ID = {operation.id: operation for operation in OPERATIONS}


def validate_options(operation_id: str, options: dict) -> dict:
    if operation_id.startswith("convert:"):
        target = operation_id.split(":", 1)[1]
        if target not in {
            "jpg",
            "png",
            "webp",
            "heic",
            "tiff",
            "avif",
            "bmp",
            "pdf",
            "mp3",
            "m4a",
            "wav",
            "flac",
            "ogg",
            "opus",
            "aiff",
            "wma",
            "mp4",
            "mov",
            "mkv",
            "webm",
            "avi",
            "wmv",
            "gif",
            "docx",
            "md",
            "txt",
            "html",
            "epub",
            "xlsx",
            "ods",
            "csv",
            "tsv",
            "srt",
            "vtt",
            "zip",
            "tar",
            "gz",
        }:
            raise ValueError("This output format is not available in this build.")
        parameters = (QUALITY,)
    else:
        if operation_id not in BY_ID:
            raise ValueError("Unknown operation")
        parameters = BY_ID[operation_id].parameters
    if not isinstance(options, dict) or set(options) - {p.key for p in parameters}:
        raise ValueError("Unknown operation settings")
    clean = {}
    for parameter in parameters:
        value = options.get(parameter.key, parameter.default)
        if parameter.kind == "number":
            if isinstance(value, bool):
                raise ValueError(f"{parameter.label} must be a number.")
            value = float(value)
            if not parameter.minimum <= value <= parameter.maximum:
                raise ValueError(
                    f"{parameter.label} must be between {parameter.minimum} and {parameter.maximum}."
                )
        elif parameter.kind == "choice":
            if value not in parameter.choices:
                raise ValueError(f"Choose a valid {parameter.label.lower()}.")
        elif not isinstance(value, str) or len(value) > 8192 or "\0" in value:
            raise ValueError(f"Invalid {parameter.label.lower()}.")
        clean[parameter.key] = value
    if "end" in clean and clean["end"] and clean["end"] <= clean.get("start", 0):
        raise ValueError("The end must be after the start.")
    return clean
