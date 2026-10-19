#!/usr/bin/env python3
"""Real GTK3 indicator/GTK4 application integration on a private D-Bus."""

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.pop("MANDARIN_DISABLE_INDICATOR", None)
temporary = tempfile.TemporaryDirectory()
os.environ["XDG_STATE_HOME"] = temporary.name
os.environ["XDG_CONFIG_HOME"] = temporary.name
os.environ["GDK_BACKEND"] = "x11"
os.environ["GSK_RENDERER"] = "cairo"

from mandarin.ui import Application, Gio, GLib

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
registered = []
info = Gio.DBusNodeInfo.new_for_xml("""<node><interface name="org.kde.StatusNotifierWatcher">
<method name="RegisterStatusNotifierItem"><arg type="s" direction="in"/></method>
<method name="RegisterStatusNotifierHost"><arg type="s" direction="in"/></method>
<property name="RegisteredStatusNotifierItems" type="as" access="read"/>
<property name="IsStatusNotifierHostRegistered" type="b" access="read"/>
<property name="ProtocolVersion" type="i" access="read"/>
<signal name="StatusNotifierItemRegistered"><arg type="s"/></signal>
<signal name="StatusNotifierHostRegistered"/>
</interface></node>""")


def method(connection, sender, path, interface, name, parameters, invocation):
    if name == "RegisterStatusNotifierItem":
        service = parameters.unpack()[0]
        registered.append((sender, service))
        connection.emit_signal(
            None,
            path,
            interface,
            "StatusNotifierItemRegistered",
            GLib.Variant("(s)", (sender + service,)),
        )
    invocation.return_value(None)


def property_value(connection, sender, path, interface, name):
    return {
        "RegisteredStatusNotifierItems": GLib.Variant(
            "as", [sender + service for sender, service in registered]
        ),
        "IsStatusNotifierHostRegistered": GLib.Variant("b", True),
        "ProtocolVersion": GLib.Variant("i", 0),
    }[name]


bus.register_object("/StatusNotifierWatcher", info.interfaces[0], method, property_value, None)
owner = Gio.bus_own_name_on_connection(
    bus, "org.kde.StatusNotifierWatcher", Gio.BusNameOwnerFlags.NONE, None, None
)
app = Application()
errors = []


def await_value(predicate, description, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise RuntimeError("Timed out: " + description)


def call(destination, path, interface, name, signature, arguments):
    return bus.call_sync(
        destination,
        path,
        interface,
        name,
        GLib.Variant(signature, arguments),
        None,
        Gio.DBusCallFlags.NONE,
        3000,
        None,
    ).unpack()


def drive():
    try:
        await_value(lambda: registered and app.tray_connected, "native taskbar registration")
        sender, service = registered[0]
        candidates = (
            [service]
            if service.startswith("/")
            else ["/StatusNotifierItem", "/org/ayatana/NotificationItem/mandarin"]
        )
        properties = None
        for path in candidates:
            try:
                properties = call(
                    sender,
                    path,
                    "org.freedesktop.DBus.Properties",
                    "GetAll",
                    "(s)",
                    ("org.kde.StatusNotifierItem",),
                )[0]
                if properties.get("Menu"):
                    break
            except GLib.Error:
                continue
        if not properties or not properties.get("Menu"):
            raise RuntimeError("Taskbar item did not export its menu")
        menu_path = properties["Menu"]

        def labels():
            layout = call(
                sender, menu_path, "com.canonical.dbusmenu", "GetLayout", "(iias)", (0, -1, [])
            )[1]
            result = {}

            def visit(node):
                if isinstance(node, GLib.Variant):
                    node = node.unpack()
                identifier, values, children = node
                if "label" in values:
                    result[values["label"]] = identifier
                for child in children:
                    visit(child)

            visit(layout)
            return result

        items = labels()
        for text in ["Open Mandarin", "Add files…", "Conversion jobs", "Quit Mandarin"]:
            if text not in items:
                raise RuntimeError("Missing taskbar action: " + text)
        GLib.idle_add(app.window.close)
        await_value(lambda: not app.window.get_visible(), "close-to-indicator")
        call(
            sender,
            menu_path,
            "com.canonical.dbusmenu",
            "Event",
            "(isvu)",
            (items["Open Mandarin"], "clicked", GLib.Variant("s", ""), 0),
        )
        await_value(lambda: app.window.get_visible(), "reopen from taskbar")
        GLib.idle_add(
            lambda: app.lookup_action("status").set_state(GLib.Variant("s", "2 active conversions"))
        )
        await_value(lambda: "2 active conversions" in labels(), "live conversion status")
        call(
            sender,
            menu_path,
            "com.canonical.dbusmenu",
            "Event",
            "(isvu)",
            (items["Quit Mandarin"], "clicked", GLib.Variant("s", ""), 0),
        )
        print(
            "PASS: taskbar registration, icon/menu export, close-to-tray, menu reopen, live job status and Quit.",
            flush=True,
        )
    except Exception as error:
        errors.append(str(error))
        print(str(error), file=sys.stderr, flush=True)
        GLib.idle_add(app.quit)


threading.Thread(target=drive, daemon=True).start()
app.run([])
Gio.bus_unown_name(owner)
temporary.cleanup()
raise SystemExit(bool(errors))
