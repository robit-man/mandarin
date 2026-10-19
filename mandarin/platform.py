"""Desktop actions without shell command interpolation."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def host_environment() -> dict:
    env = dict(os.environ)
    for key in (
        "LD_LIBRARY_PATH",
        "PYTHONHOME",
        "PYTHONPATH",
        "GI_TYPELIB_PATH",
        "GIO_EXTRA_MODULES",
        "GSETTINGS_SCHEMA_DIR",
        "FONTCONFIG_PATH",
        "MAGICK_CONFIGURE_PATH",
    ):
        env.pop(key, None)
    return env


def reveal(path: Path):
    from gi.repository import Gio, GLib

    try:
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        connection.call(
            "org.freedesktop.FileManager1",
            "/org/freedesktop/FileManager1",
            "org.freedesktop.FileManager1",
            "ShowItems",
            GLib.Variant("(ass)", ([path.absolute().as_uri()], "")),
            None,
            Gio.DBusCallFlags.NONE,
            3000,
            None,
            None,
        )
    except Exception:
        subprocess.Popen(
            ["/usr/bin/xdg-open", str(path if path.is_dir() else path.parent)],
            env=host_environment(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def terminal(directory: Path):
    candidates = [
        ("/usr/bin/gnome-terminal", ["--working-directory", str(directory)]),
        ("/usr/bin/kgx", ["--working-directory", str(directory)]),
        ("/usr/bin/x-terminal-emulator", []),
    ]
    for executable, arguments in candidates:
        if Path(executable).is_file():
            subprocess.Popen(
                [executable] + arguments,
                cwd=directory,
                env=host_environment(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
    raise ValueError("No terminal application is installed.")
