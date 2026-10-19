"""Native Ayatana indicator in a separate GTK3 process from the GTK4 UI."""

import argparse
import gettext
import json
import os
import signal

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3, Gio, GLib, Gtk

from .runtime import ROOT

_ = gettext.gettext


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=int, required=True)
    arguments = parser.parse_args()
    Gtk.init([])
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    actions = Gio.DBusActionGroup.get(
        connection, "org.mandarin.Converter", "/org/mandarin/Converter"
    )
    actions.list_actions()
    indicator = AyatanaAppIndicator3.Indicator.new_with_path(
        "mandarin",
        "org.mandarin.Converter",
        AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        str(ROOT / "mandarin/resources"),
    )
    indicator.set_title("Mandarin")
    indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
    menu = Gtk.Menu()
    status = Gtk.MenuItem(label=_("Mandarin is ready"))
    status.set_sensitive(False)
    menu.append(status)

    def activate(action):
        actions.activate_action(action, None)

    for label, action in [
        ("Open Mandarin", "show"),
        ("Add files…", "add-files"),
        ("Conversion jobs", "jobs"),
    ]:
        item = Gtk.MenuItem(label=_(label))
        item.connect("activate", lambda _, name=action: activate(name))
        menu.append(item)
    menu.append(Gtk.SeparatorMenuItem())
    quit_item = Gtk.MenuItem(label=_("Quit Mandarin"))
    quit_item.connect("activate", lambda *_: activate("quit"))
    menu.append(quit_item)
    menu.show_all()
    indicator.set_menu(menu)

    def connected(*_):
        print(
            json.dumps({"event": "indicator", "connected": indicator.get_property("connected")}),
            flush=True,
        )

    indicator.connect("connection-changed", connected)
    connected()

    def tick():
        try:
            os.kill(arguments.parent, 0)
        except ProcessLookupError:
            Gtk.main_quit()
            return False
        state = actions.get_action_state("status")
        if state:
            status.set_label(state.get_string())
        return True

    GLib.timeout_add_seconds(2, tick)
    for number in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, number, lambda: (Gtk.main_quit(), False)[1])
    Gtk.main()
    indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.PASSIVE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
