"""Explicit engine locations and reproducible packaged/development profiles."""

from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "runtime"
PACKAGED = (ROOT / "runtime-manifest.json").is_file()

ENGINE_PATHS = {
    "ffmpeg": "/usr/bin/ffmpeg",
    "ffprobe": "/usr/bin/ffprobe",
    "convert": "/usr/bin/convert",
    "identify": "/usr/bin/identify",
    "soffice": "/usr/lib/libreoffice/program/soffice.bin",
    "pdftoppm": "/usr/bin/pdftoppm",
    "pdftotext": "/usr/bin/pdftotext",
    "pdfinfo": "/usr/bin/pdfinfo",
    "qpdf": "/usr/bin/qpdf",
    "pandoc": "/usr/bin/pandoc",
    "bsdtar": "/usr/bin/bsdtar",
    "rsvg": "/usr/bin/rsvg-convert",
    "exiftool": "/usr/bin/exiftool",
    "perl": "/usr/bin/perl",
    "tesseract": "/usr/bin/tesseract",
    "zbarimg": "/usr/bin/zbarimg",
    "gs": "/usr/bin/gs",
}


def engine_path(name: str) -> Path:
    if name not in ENGINE_PATHS:
        raise ValueError(f"Unknown engine: {name}")
    path = BUNDLE / ENGINE_PATHS[name].lstrip("/") if PACKAGED else Path(ENGINE_PATHS[name])
    if not path.is_file():
        raise RuntimeError(
            f"Required {name} engine is missing from {'the package' if PACKAGED else 'the development environment'}."
        )
    return path


def engine(name: str) -> list[str]:
    path = engine_path(name)
    if name == "exiftool":
        return engine("perl") + [str(path)]
    return native_command(path)


def native_command(path: Path) -> list[str]:
    if not PACKAGED:
        return [str(path)]
    loader = BUNDLE / "lib64/ld-linux-x86-64.so.2"
    if not loader.is_file():
        raise RuntimeError("The bundled dynamic loader is missing. Reinstall Mandarin.")
    return [
        str(loader),
        "--library-path",
        bundle_environment()["LD_LIBRARY_PATH"],
        str(path),
    ]


def sandbox_path() -> Path:
    path = ROOT / ("bin/mandarin-sandbox" if PACKAGED else "build/mandarin-sandbox")
    if not path.is_file():
        raise RuntimeError(
            "Worker isolation is unavailable. Run make, or reinstall the complete Mandarin package."
        )
    return path


def worker_environment(workspace: Path) -> dict[str, str]:
    env = {
        "PATH": str(BUNDLE / "usr/bin") if PACKAGED else "/usr/bin:/bin",
        "HOME": str(workspace),
        "TMPDIR": str(workspace),
        "XDG_CACHE_HOME": str(workspace / "cache"),
        "XDG_CONFIG_HOME": str(workspace / "config"),
        "XDG_RUNTIME_DIR": str(workspace),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "OMP_NUM_THREADS": "2",
        "OPENBLAS_NUM_THREADS": "1",
        "MAGICK_THREAD_LIMIT": "2",
        "MAGICK_MEMORY_LIMIT": "256MiB",
        "MAGICK_MAP_LIMIT": "512MiB",
        "SAL_USE_VCLPLUGIN": "svp",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LOK_ALLOWLIST_LANGUAGES": "en-US",
        "PYTHONPATH": str(ROOT),
        "MANDARIN_WORKER": "1",
    }
    if PACKAGED:
        env.update(bundle_environment())
        env["HOME"] = str(workspace)
    return env


def bundle_environment() -> dict[str, str]:
    if not PACKAGED:
        return {}
    machine = "x86_64-linux-gnu" if platform.machine() == "x86_64" else "aarch64-linux-gnu"
    libraries = [
        BUNDLE / "usr/lib/libreoffice/program",
        BUNDLE / "usr/lib" / machine,
        BUNDLE / "usr/lib" / machine / "pulseaudio",
        BUNDLE / "usr/lib" / machine / "blas",
        BUNDLE / "usr/lib" / machine / "lapack",
        BUNDLE / "lib" / machine,
        BUNDLE / "usr/lib",
    ]
    ghostscript = [
        path
        for version in (BUNDLE / "usr/share/ghostscript").glob("*")
        for path in (version / "Resource/Init", version / "Resource/Font", version / "lib")
        if path.is_dir()
    ]
    return {
        "LD_LIBRARY_PATH": ":".join(map(str, libraries)),
        "PYTHONHOME": str(BUNDLE / "usr"),
        "PYTHONNOUSERSITE": "1",
        "GI_TYPELIB_PATH": str(BUNDLE / "usr/lib" / machine / "girepository-1.0"),
        "GIO_EXTRA_MODULES": str(BUNDLE / "usr/lib" / machine / "gio/modules"),
        "GSETTINGS_SCHEMA_DIR": str(BUNDLE / "usr/share/glib-2.0/schemas"),
        "FONTCONFIG_PATH": str(ROOT / "etc/fonts"),
        "pandoc_datadir": str(BUNDLE / "usr/share/pandoc"),
        "TESSDATA_PREFIX": str(BUNDLE / "usr/share/tesseract-ocr/5/tessdata"),
        "MAGICK_CONFIGURE_PATH": str(BUNDLE / "etc/ImageMagick-6"),
        "LIBHEIF_PLUGIN_PATH": str(BUNDLE / "usr/lib" / machine / "libheif/plugins"),
        "GS_LIB": ":".join(map(str, ghostscript)),
        "PERL5LIB": ":".join(
            str(p)
            for p in [
                BUNDLE / "usr/share/perl5",
                BUNDLE / "usr/lib" / machine / "perl-base",
                BUNDLE / "usr/lib" / machine / "perl5/5.38",
                BUNDLE / "usr/lib" / machine / "perl/5.38",
                BUNDLE / "usr/share/perl/5.38",
            ]
            if p.is_dir()
        ),
        "MAGICK_CODER_MODULE_PATH": str(
            BUNDLE / "usr/lib" / machine / "ImageMagick-6.9.12/modules-Q16/coders"
        ),
    }


def python_command() -> list[str]:
    return (
        native_command(BUNDLE / "usr/bin/python3.12") + ["-P"]
        if PACKAGED
        else ["/usr/bin/python3", "-P"]
    )


def sandbox_command(
    workspace: Path, inputs: list[Path], command: list[str], timeout: int = 900
) -> list[str]:
    result = native_command(sandbox_path()) + [
        "--write",
        str(workspace),
        "--timeout",
        str(timeout),
    ]
    reads = [ROOT] if PACKAGED else [ROOT, Path("/usr"), Path("/lib"), Path("/bin")]
    reads += [
        Path("/etc/ld.so.cache"),
        Path("/etc/fonts"),
        Path("/etc/localtime"),
        Path("/etc/passwd"),
        Path("/etc/group"),
        Path("/dev/null"),
        Path("/dev/urandom"),
    ]
    if not PACKAGED:
        reads.append(Path("/etc/libreoffice"))
    for path in reads + inputs:
        if path.exists():
            result += [
                "--readwrite" if path == Path("/dev/null") else "--read",
                str(path.resolve()),
            ]
    return result + ["--"] + command


def health() -> dict:
    tools = {}
    for name in ENGINE_PATHS:
        try:
            tools[name] = str(engine_path(name))
        except RuntimeError:
            tools[name] = None
    try:
        result = subprocess.run(
            native_command(sandbox_path()) + ["--check"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        isolation = (
            json.loads(result.stdout)
            if result.returncode == 0
            else {"available": False, "error": result.stderr}
        )
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        isolation = {"available": False, "error": str(exc)}
    return {
        "version": "0.1.0",
        "profile": "bundled" if PACKAGED else "development",
        "engines": tools,
        "isolation": isolation,
    }
