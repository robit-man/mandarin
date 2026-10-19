#!/usr/bin/env python3
"""Real GTK DnD through X11 input events on an isolated virtual display."""

import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["GSK_RENDERER"] = "cairo"
os.environ["GDK_BACKEND"] = "x11"
temporary = tempfile.TemporaryDirectory()
runtime = Path(temporary.name) / "runtime"
runtime.mkdir(mode=0o700)
os.environ["XDG_RUNTIME_DIR"] = str(runtime)
os.environ["GIO_USE_VFS"] = "local"
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk
from PIL import Image
from mandarin.ui import Application

root = Path(temporary.name)
os.environ["XDG_STATE_HOME"] = str(root / "state")
os.environ["XDG_CONFIG_HOME"] = str(root / "config")
path = root / "drag.png"
Image.new("RGB", (80, 60), "orange").save(path)
app = Application()
app.register(None)
app.activate()
window = app.window
source = Gtk.Window(title="Mandarin drag source", default_width=200, default_height=140)
control = Gtk.Box()
control.append(Gtk.Label(label="Drag this file", hexpand=True, vexpand=True))
drag = Gtk.DragSource(actions=Gdk.DragAction.COPY)
drag.connect(
    "prepare",
    lambda *_: Gdk.ContentProvider.new_for_value(
        Gdk.FileList.new_from_list([Gio.File.new_for_path(str(path))])
    ),
)
control.add_controller(drag)
source.set_child(control)
source.present()
loop = GLib.MainLoop()
error = []
events = {}
finished = threading.Event()
drag.connect("drag-begin", lambda *_: events.update(drag_started=True))


def xdo(*arguments):
    return subprocess.check_output(["xdotool", *map(str, arguments)], text=True).strip()


def update():
    bounds = window.wheel.compute_bounds(window)
    if bounds[0]:
        rectangle = bounds[1]
        events["center"] = (
            int(rectangle.get_x() + rectangle.get_width() / 2),
            int(rectangle.get_y() + rectangle.get_height() / 2),
        )
    events["probed"] = bool(window.items)
    events["stack"] = len(window.wheel.state.stack)
    events["jobs"] = len(window.manager.jobs)
    events["succeeded"] = sum(job.state == "succeeded" for job in window.manager.jobs.values())
    if finished.is_set():
        loop.quit()
        return False
    return True


def await_value(predicate, description, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise RuntimeError("Timed out: " + description + " " + str(events))


def drive():
    try:
        time.sleep(0.7)
        source_id = xdo("search", "--name", "^Mandarin drag source$").splitlines()[-1]
        target_id = xdo("search", "--name", "^Mandarin$").splitlines()[-1]
        xdo("windowmove", source_id, 0, 0)
        xdo("windowmove", target_id, 240, 20)
        xdo("windowraise", source_id)
        xdo("windowfocus", source_id)
        xdo("mousemove", "--window", source_id, 90, 70)
        xdo("mousedown", 1)
        time.sleep(0.1)
        for x in [95, 105, 115, 125]:
            xdo("mousemove", "--sync", "--window", source_id, x, 90)
            time.sleep(0.05)
        await_value(lambda: events.get("drag_started"), "native source drag started")
        time.sleep(0.1)
        xdo("mousemove", "--sync", "--window", target_id, 350, 250)
        time.sleep(0.1)
        xdo("mousemove", "--sync", "--window", target_id, 355, 255)
        await_value(lambda: events.get("probed"), "file payload preloaded during drag")
        cx, cy = events["center"]
        xdo("mousemove", "--sync", "--window", target_id, cx, cy - 137)
        await_value(lambda: events.get("stack", 0) > 0, "submenu during held drag")
        # The file remains held while moving to a newly exposed JPEG leaf.
        index = next(
            i for i, item in enumerate(window.wheel.state.visible()) if item.id == "convert:jpg"
        )
        import math

        angle = -math.pi / 2 + 2 * math.pi * index / len(window.wheel.state.visible())
        xdo(
            "mousemove",
            "--sync",
            "--window",
            target_id,
            int(cx + 137 * math.cos(angle)),
            int(cy + 137 * math.sin(angle)),
        )
        time.sleep(0.2)
        xdo("mouseup", 1)
        await_value(lambda: events.get("succeeded") == 1, "one real drop conversion")
        if events.get("jobs") != 1:
            raise RuntimeError("Drop submitted more than one job")
        if not (root / "drag.jpg").exists() or not path.exists():
            raise RuntimeError("Missing result or original")
        print(
            "PASS: real GTK file drag, payload preload, dwell submenu, leaf drop, exactly-one conversion, original retained.",
            flush=True,
        )
    except Exception as exc:
        error.append(str(exc))
        print(str(exc), file=sys.stderr, flush=True)
    finally:
        try:
            xdo("mouseup", 1)
        except Exception:
            pass
        finished.set()


GLib.timeout_add(50, update)
threading.Thread(target=drive, daemon=True).start()
loop.run()
window.manager.close()
source.destroy()
window.destroy()
temporary.cleanup()
raise SystemExit(bool(error))
