#!/usr/bin/env python3
"""Exercise the native GTK workflow in an isolated display and capture it."""

import os
import sys
import subprocess
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["GSK_RENDERER"] = "cairo"
os.environ["GDK_BACKEND"] = "x11"
temporary = tempfile.TemporaryDirectory()
runtime = Path(temporary.name) / "runtime"
runtime.mkdir(mode=0o700)
os.environ["XDG_RUNTIME_DIR"] = str(runtime)
os.environ["XDG_CONFIG_HOME"] = str(Path(temporary.name) / "config")
os.environ["GIO_USE_VFS"] = "local"
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gsk", "4.0")
from gi.repository import GLib
from PIL import Image
from mandarin.ui import Application

os.environ["XDG_STATE_HOME"] = temporary.name
source = Path(temporary.name) / "sample.png"
Image.new("RGB", (320, 200), (232, 131, 53)).save(source)
app = Application()
app.register(None)
app.activate()
window = app.window
window.set_files([source])
loop = GLib.MainLoop()
started = time.monotonic()
submitted = False
captured = False
capture_scheduled = False


def capture(name="gui-smoke"):
    global captured
    identifier = subprocess.check_output(
        ["xdotool", "search", "--name", "^Mandarin$"], text=True
    ).splitlines()[-1]
    target = Path("build") / (name + ".png")
    target.parent.mkdir(exist_ok=True)
    subprocess.run(["import", "-window", identifier, str(target)], check=True, timeout=10)
    captured = True


def capture_views():
    from mandarin.ui import ParameterDialog

    try:
        capture()
        window.list_toggle.set_active(False)
        window.wheel.set_items(window.wheel.state.root)

        def radial():
            capture("gui-radial")
            window.set_compact(True)

            def compact():
                capture("gui-compact")
                dialog = ParameterDialog(window, "resize")
                dialog.present()

                def editor():
                    identifier = subprocess.check_output(
                        ["xdotool", "search", "--name", "^Conversion settings$"], text=True
                    ).splitlines()[-1]
                    subprocess.run(
                        ["import", "-window", identifier, "build/gui-editor.png"],
                        check=True,
                        timeout=10,
                    )
                    dialog.close()
                    print("PASS: native workflow, radial/list/compact/editor captures.")
                    loop.quit()
                    return False

                GLib.timeout_add(800, editor)
                return False

            GLib.timeout_add(400, compact)
            return False

        GLib.timeout_add(400, radial)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        loop.quit()
    return False


def poll():
    global submitted, capture_scheduled
    if time.monotonic() - started > 30:
        print("GUI workflow timed out", file=sys.stderr)
        loop.quit()
        return False
    if window.items and not submitted:
        window.wheel.activate(0)
        window.submit("convert:jpg", {})
        window.list_toggle.set_active(True)
        submitted = True
    jobs = list(window.manager.jobs.values())
    if jobs and jobs[0].state in {"succeeded", "failed"}:
        if capture_scheduled:
            return True
        if jobs[0].state != "succeeded":
            print(jobs[0].error, file=sys.stderr)
            loop.quit()
            return False
        capture_scheduled = True
        GLib.timeout_add(400, capture_views)
    return True


GLib.timeout_add(100, poll)
loop.run()
jobs = list(window.manager.jobs.values())
success = bool(jobs and jobs[0].state == "succeeded" and captured)
window.manager.close()
window.destroy()
temporary.cleanup()
raise SystemExit(0 if success else 1)
