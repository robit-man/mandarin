#!/usr/bin/env python3
"""Probe a private headless GNOME46 compositor; never changes the user's Shell.

Run: dbus-run-session -- env MANDARIN_PRIVATE_BUS=1 python3 scripts/wayland_smoke.py
Test-only Shell Eval enables geometry/input observation in this private session.
"""

import json
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    if os.environ.get("MANDARIN_PRIVATE_BUS") != "1":
        raise RuntimeError("Run this probe inside dbus-run-session as documented.")
    root = Path(tempfile.mkdtemp(prefix="wayland-qa-", dir=ROOT / "build"))
    for name in ["runtime", "data", "config", "state", "cache"]:
        (root / name).mkdir(mode=0o700)
        os.environ[
            "XDG_"
            + (
                "DATA_HOME"
                if name == "data"
                else "RUNTIME_DIR"
                if name == "runtime"
                else name.upper() + "_HOME"
            )
        ] = str(root / name)
    os.environ.update(
        GDK_BACKEND="wayland",
        LIBGL_ALWAYS_SOFTWARE="1",
        PYTHONPATH=str(ROOT),
        XDG_SESSION_TYPE="wayland",
    )
    os.environ.pop("DISPLAY", None)
    os.environ.pop("WAYLAND_DISPLAY", None)
    subprocess.run(
        [
            "dbus-update-activation-environment",
            "XDG_RUNTIME_DIR",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_STATE_HOME",
            "XDG_CACHE_HOME",
            "GDK_BACKEND",
            "PYTHONPATH",
            "XDG_SESSION_TYPE",
        ],
        check=True,
    )
    extension = root / "data/gnome-shell/extensions/mandarin@local"
    shutil.copytree(ROOT / "gnome-extension", extension)
    code = (
        (extension / "extension.js")
        .read_text()
        .replace(
            "enable() {",
            "enable() {\n        global.context.unsafe_mode = true; // Private QA compositor only.",
        )
    )
    (extension / "extension.js").write_text(code)
    services = root / "data/dbus-1/services"
    services.mkdir(parents=True)
    application = root / "application.py"
    application.write_text(
        """import json,os,sys
from pathlib import Path
sys.path.insert(0, """
        + repr(str(ROOT))
        + """)
from gi.repository import GLib
from mandarin.ui import Application
root=Path("""
        + repr(str(root))
        + """)
app=Application(popup=True,service=True)
def observe():
 if app.window:
  w=app.window
  ok,rect=w.wheel.compute_bounds(w)
  value={'pid':os.getpid(),'paths':[str(p) for p in w.paths], 'items':len(w.items),'depth':len(w.wheel.state.stack),'visible':[item.id for item in w.wheel.state.visible()],'jobs':len(w.manager.jobs),'succeeded':sum(j.state=='succeeded' for j in w.manager.jobs.values())}
  if ok:value['center']=[rect.get_x()+rect.get_width()/2,rect.get_y()+rect.get_height()/2]
  (root/'ui-state.tmp').write_text(json.dumps(value)); (root/'ui-state.tmp').replace(root/'ui-state.json')
 return True
GLib.timeout_add(50,observe)
app.run([])
"""
    )
    (services / "org.mandarin.Converter.service").write_text(
        "[D-BUS Service]\nName=org.mandarin.Converter\nExec=/usr/bin/python3 "
        + str(application)
        + "\n"
    )
    subprocess.run(
        ["gsettings", "set", "org.gnome.shell", "enabled-extensions", "['mandarin@local']"],
        check=True,
    )
    subprocess.run(
        ["gsettings", "set", "org.gnome.shell", "disable-user-extensions", "false"], check=True
    )
    log = (root / "shell.log").open("w")
    shell = subprocess.Popen(
        [
            "gnome-shell",
            "--headless",
            "--wayland",
            "--no-x11",
            "--virtual-monitor=1280x900",
            "--wayland-display=mandarin-qa",
            "--sm-disable",
            "--mode=user",
        ],
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
    report = {
        "session": "private headless GNOME46 Wayland",
        "host_shell_modified": False,
        "test_instrumentation": "Shell Eval enabled only in private extension copy",
        "status": "fail",
    }
    source_process = None
    application_pid = None
    try:
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

        def call(destination, path, interface, method, signature=None, arguments=()):
            return bus.call_sync(
                destination,
                path,
                interface,
                method,
                GLib.Variant(signature, arguments) if signature else None,
                None,
                Gio.DBusCallFlags.NONE,
                5000,
                None,
            ).unpack()

        deadline = time.monotonic() + 30
        while not (root / "runtime/mandarin-qa").exists():
            if shell.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError(
                    "Private GNOME did not start: " + (root / "shell.log").read_text()[-3000:]
                )
            time.sleep(0.2)
        os.environ["WAYLAND_DISPLAY"] = "mandarin-qa"
        subprocess.run(["dbus-update-activation-environment", "WAYLAND_DISPLAY"], check=True)
        time.sleep(3)
        call(
            "org.gnome.Shell",
            "/org/gnome/Shell",
            "org.gnome.Shell.Extensions",
            "EnableExtension",
            "(s)",
            ("mandarin@local",),
        )
        time.sleep(1)
        extension_state = call(
            "org.gnome.Shell",
            "/org/gnome/Shell",
            "org.gnome.Shell.Extensions",
            "GetExtensionInfo",
            "(s)",
            ("mandarin@local",),
        )
        report["extension"] = str(extension_state)

        def evaluate(script):
            ok, result = call(
                "org.gnome.Shell", "/org/gnome/Shell", "org.gnome.Shell", "Eval", "(s)", (script,)
            )
            if not ok:
                raise RuntimeError("Private Shell evaluation failed: " + result)
            return json.loads(result) if result else None

        report["pointer"] = evaluate("global.get_pointer()")
        remote = call(
            "org.gnome.Mutter.RemoteDesktop",
            "/org/gnome/Mutter/RemoteDesktop",
            "org.gnome.Mutter.RemoteDesktop",
            "CreateSession",
        )[0]
        call(
            "org.gnome.Mutter.RemoteDesktop",
            remote,
            "org.gnome.Mutter.RemoteDesktop.Session",
            "Start",
        )
        report["input_session"] = remote

        def notify(method, signature, arguments):
            return call(
                "org.gnome.Mutter.RemoteDesktop",
                remote,
                "org.gnome.Mutter.RemoteDesktop.Session",
                method,
                signature,
                arguments,
            )

        def move(x, y):
            current = evaluate("global.get_pointer()")
            notify(
                "NotifyPointerMotionRelative",
                "(dd)",
                (float(x - current[0]), float(y - current[1])),
            )
            time.sleep(0.1)

        def await_value(predicate, description, seconds=15):
            until = time.monotonic() + seconds
            while time.monotonic() < until:
                value = predicate()
                if value:
                    return value
                time.sleep(0.1)
            raise RuntimeError("Timed out: " + description)

        def windows():
            return evaluate(
                "global.get_window_actors().map(a=>{let w=a.meta_window,r=w.get_frame_rect();return [w.get_title(),r.x,r.y,r.width,r.height]})"
            )

        def window(title):
            return next(
                (item for item in windows() if item[0] == title and item[3] > 0 and item[4] > 0),
                None,
            )

        def ui_state():
            path = root / "ui-state.json"
            return json.loads(path.read_text()) if path.exists() else {}

        from PIL import Image

        sample = root / "wayland-source.png"
        Image.new("RGB", (80, 60), "orange").save(sample)
        source_script = root / "source.py"
        source_script.write_text(
            """import gi
gi.require_version('Gtk','4.0');gi.require_version('Gdk','4.0')
from gi.repository import Gtk,Gdk,Gio
from pathlib import Path
app=Gtk.Application(application_id='org.mandarin.QASource')
def activate(app):
 w=Gtk.ApplicationWindow(application=app,title='Wayland file source',default_width=320,default_height=200)
 box=Gtk.Box();box.append(Gtk.Label(label='Drag file',hexpand=True,vexpand=True));w.set_child(box)
 drag=Gtk.DragSource(actions=Gdk.DragAction.COPY)
 drag.connect('prepare',lambda *_:Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_list([Gio.File.new_for_path("""
            + repr(str(sample))
            + """)])))
 drag.connect('drag-begin',lambda *_:Path("""
            + repr(str(root / "drag-started"))
            + """).write_text('yes'))
 box.add_controller(drag);w.present()
app.connect('activate',activate);app.run([])
"""
        )
        evaluate("Main.overview.hide();true")
        source_process = subprocess.Popen(
            ["/usr/bin/python3", str(source_script)], stdout=log, stderr=log
        )
        await_value(lambda: window("Wayland file source"), "native Wayland source window")
        evaluate(
            "(()=>{let w=global.get_window_actors().map(a=>a.meta_window).find(w=>w.get_title()==='Wayland file source');w.move_frame(true,80,120);w.activate(global.get_current_time());return true})()"
        )
        time.sleep(0.5)
        source_window = window("Wayland file source")
        report["source_window"] = source_window
        move(source_window[1] + 120, source_window[2] + 100)
        report["pointer_before_press"] = evaluate("global.get_pointer()")
        notify("NotifyPointerButton", "(ib)", (272, True))
        time.sleep(0.1)
        for offset in [125, 135, 145, 155, 165]:
            move(source_window[1] + offset, source_window[2] + 100)
        report["pointer_after_press"] = evaluate("global.get_pointer()")
        await_value(lambda: (root / "drag-started").exists(), "held native file drag")
        move(800, 450)
        notify("NotifyKeyboardKeycode", "(ub)", (42, True))
        time.sleep(0.4)
        notify("NotifyKeyboardKeycode", "(ub)", (42, False))
        target_window = await_value(lambda: window("Mandarin"), "global Shift invocation")
        await_value(lambda: ui_state().get("items"), "pre-drop file context")
        state = ui_state()
        application_pid = state["pid"]
        await_value(lambda: ui_state().get("depth") == 1, "invoked Convert menu")
        cx = target_window[1] + state["center"][0]
        cy = target_window[2] + state["center"][1]
        move(cx, cy - 105)
        await_value(lambda: ui_state().get("depth") == 0, "dwell Back while held")
        move(cx + 20, cy - 105)
        await_value(lambda: ui_state().get("depth") == 1, "dwell Convert submenu while held")
        state = ui_state()
        index = state["visible"].index("convert:jpg")
        angle = -math.pi / 2 + 2 * math.pi * index / len(state["visible"])
        move(cx + 105 * math.cos(angle), cy + 105 * math.sin(angle))
        notify("NotifyPointerButton", "(ib)", (272, False))
        await_value(lambda: ui_state().get("succeeded") == 1, "validated leaf-drop conversion", 30)
        if (
            ui_state().get("jobs") != 1
            or not sample.with_suffix(".jpg").exists()
            or not sample.exists()
        ):
            raise RuntimeError("Unexpected duplicate job or missing source/result")
        report["checks"] = [
            "native-Wayland-source",
            "global-held-drag-Shift",
            "pre-drop-content",
            "held-Back-and-submenu-dwell",
            "leaf-release",
            "exactly-one-validated-conversion",
            "original-preserved",
        ]
        report["status"] = "pass"
        print(json.dumps(report, indent=2), flush=True)
    except Exception as error:
        report["error"] = str(error)
        try:
            report["final_windows"] = windows()
            report["final_pointer"] = evaluate("global.get_pointer()")
            call(
                "org.gnome.Shell.Screenshot",
                "/org/gnome/Shell/Screenshot",
                "org.gnome.Shell.Screenshot",
                "Screenshot",
                "(bbs)",
                (False, False, str(ROOT / "build/wayland-stage.png")),
            )
        except Exception:
            pass
        print(str(error), file=sys.stderr, flush=True)
    finally:
        (ROOT / "build/wayland-probe-report.json").write_text(json.dumps(report, indent=2) + "\n")
        if application_pid:
            try:
                os.kill(application_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if source_process and source_process.poll() is None:
            source_process.terminate()
            source_process.wait(timeout=3)
        if shell.poll() is None:
            os.killpg(shell.pid, signal.SIGTERM)
            try:
                shell.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(shell.pid, signal.SIGKILL)
                shell.wait(timeout=3)
        log.close()
    return report["status"] != "pass"


if __name__ == "__main__":
    raise SystemExit(main())
