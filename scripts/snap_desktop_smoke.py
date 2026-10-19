#!/usr/bin/env python3
"""Check the installed Snap on a real Ubuntu desktop and taskbar host."""

import json
import subprocess
import time
from pathlib import Path

from gi.repository import Gio, GLib

ROOT = Path(__file__).resolve().parents[1]
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)


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


def owned():
    return call(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "NameHasOwner",
        "(s)",
        ("org.mandarin.Converter",),
    )[0]


def await_value(predicate, description):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    raise RuntimeError("Timed out: " + description)


def mandarin_item():
    items = call(
        "org.kde.StatusNotifierWatcher",
        "/StatusNotifierWatcher",
        "org.freedesktop.DBus.Properties",
        "Get",
        "(ss)",
        ("org.kde.StatusNotifierWatcher", "RegisteredStatusNotifierItems"),
    )[0]
    for item in items:
        if "@" in item:
            service, path = item.split("@", 1)
        elif "/" in item:
            service, suffix = item.split("/", 1)
            path = "/" + suffix
        else:
            service, path = item, "/StatusNotifierItem"
        try:
            values = call(
                service,
                path,
                "org.freedesktop.DBus.Properties",
                "GetAll",
                "(s)",
                ("org.kde.StatusNotifierItem",),
            )[0]
            if values.get("Id") == "mandarin" and values.get("Menu"):
                return service, values
        except GLib.Error:
            continue
    return None


def main():
    if owned():
        raise RuntimeError("Close the existing Mandarin application before this check.")
    report = {"distribution": "installed strict Snap", "desktop": "Ubuntu 24.04 GNOME 46 Wayland"}
    with (ROOT / "build/snap-desktop-runtime.log").open("w") as log:
        process = subprocess.Popen(["snap", "run", "mandarin"], stdout=log, stderr=log)
        try:
            await_value(owned, "application D-Bus registration")
            service, properties = await_value(mandarin_item, "real taskbar registration")
            layout = call(
                service,
                properties["Menu"],
                "com.canonical.dbusmenu",
                "GetLayout",
                "(iias)",
                (0, -1, []),
            )[1]
            labels = {}

            def visit(node):
                if isinstance(node, GLib.Variant):
                    node = node.unpack()
                identifier, values, children = node
                if "label" in values:
                    labels[values["label"]] = identifier
                for child in children:
                    visit(child)

            visit(layout)
            for label in ("Open Mandarin", "Add files…", "Conversion jobs", "Quit Mandarin"):
                if label not in labels:
                    raise RuntimeError("Missing taskbar menu action: " + label)
            for label in ("Open Mandarin", "Conversion jobs", "Quit Mandarin"):
                call(
                    service,
                    properties["Menu"],
                    "com.canonical.dbusmenu",
                    "Event",
                    "(isvu)",
                    (labels[label], "clicked", GLib.Variant("s", ""), 0),
                )
                time.sleep(0.3)
            await_value(lambda: process.poll() is not None, "taskbar Quit")
            if process.returncode:
                raise RuntimeError(f"Snap GUI exited {process.returncode}")
            await_value(lambda: not owned(), "application shutdown")
            report.update(status="pass", actions=list(labels), indicator_id=properties["Id"])
            print(
                "PASS: installed strict Snap GUI, real GNOME indicator, menu, Open, Jobs and Quit."
            )
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    (ROOT / "build/snap-desktop-report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
