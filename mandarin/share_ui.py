import threading

from .ui import Adw, GLib, Gtk, _, button, display
from .share import discover, inspect_peer, send


class ShareWindow(Adw.Window):
    def __init__(self, parent, paths):
        super().__init__(
            transient_for=parent,
            modal=True,
            title=_("Share nearby"),
            default_width=540,
            default_height=520,
        )
        self.paths = paths
        self.peer = None
        self.cancel = threading.Event()
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_start=24,
            margin_end=24,
            margin_top=12,
            margin_bottom=24,
        )
        box.append(Adw.HeaderBar())
        intro = Gtk.Label(
            label=_(
                "Send to a LocalSend device on your local network. The recipient must approve the transfer."
            ),
            wrap=True,
            xalign=0,
        )
        box.append(intro)
        self.peers_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self.peers_box)
        box.append(button("Find devices", self.search))
        box.append(Gtk.Label(label=_("Or enter the recipient's local IP address"), xalign=0))
        row = Gtk.Box(spacing=8)
        self.host = Gtk.Entry(placeholder_text="192.168.1.20", hexpand=True)
        row.append(self.host)
        self.port = Gtk.SpinButton.new_with_range(1, 65535, 1)
        self.port.set_value(53317)
        self.port.set_tooltip_text(_("Recipient port"))
        row.append(self.port)
        box.append(row)
        box.append(button("Check recipient", self.inspect))
        self.details = Gtk.Label(wrap=True, selectable=True, xalign=0)
        box.append(self.details)
        self.verified = Gtk.CheckButton(
            label=_("I verified this certificate fingerprint on the recipient")
        )
        box.append(self.verified)
        self.pin = Gtk.Entry(placeholder_text=_("Recipient PIN, if required"))
        self.pin.set_visibility(False)
        box.append(self.pin)
        self.progress = Gtk.ProgressBar()
        box.append(self.progress)
        self.send_button = button("Send files", self.start)
        self.send_button.add_css_class("suggested-action")
        box.append(self.send_button)
        box.append(button("Cancel", self.stop))
        self.set_content(box)
        self.connect("close-request", lambda *_: (self.cancel.set(), False)[1])
        self.host.connect("changed", lambda *_: self.invalidate())
        self.port.connect("value-changed", lambda *_: self.invalidate())

    def invalidate(self):
        self.peer = None
        self.verified.set_active(False)
        self.details.set_label("")

    def search(self):
        self.details.set_label(_("Finding devices…"))

        def work():
            try:
                peers = discover()
                GLib.idle_add(self.found, peers)
            except Exception as exc:
                GLib.idle_add(self.details.set_label, display(exc))

        threading.Thread(target=work, daemon=True).start()

    def found(self, peers):
        while child := self.peers_box.get_first_child():
            self.peers_box.remove(child)
        for peer in peers:
            self.peers_box.append(
                button(peer["alias"] + " · " + peer["host"], lambda p=peer: self.select(p))
            )
        self.details.set_label(
            _("Choose a device, then check its certificate.")
            if peers
            else _("No devices found. Enter the recipient's IP address instead.")
        )

    def select(self, peer):
        self.host.set_text(peer["host"])
        self.port.set_value(peer["port"])
        self.inspect()

    def inspect(self):
        host = self.host.get_text()
        port = self.port.get_value_as_int()
        self.invalidate()
        self.details.set_label(_("Connecting securely…"))

        def work():
            try:
                peer = inspect_peer(host, port)
                GLib.idle_add(self.inspected, peer)
            except Exception as exc:
                GLib.idle_add(self.details.set_label, display(exc))

        threading.Thread(target=work, daemon=True).start()

    def inspected(self, peer):
        if (
            peer["host"] != self.host.get_text().strip().strip("[]")
            or peer["port"] != self.port.get_value_as_int()
        ):
            return
        self.peer = peer
        digest = peer["fingerprint"]
        self.details.set_label(
            display(
                peer["alias"] + "\n" + " ".join(digest[i : i + 4] for i in range(0, len(digest), 4))
            )
        )

    def start(self):
        if not self.peer or not self.verified.get_active():
            self.details.set_label(
                _("Check the recipient and verify the fingerprint before sending.")
            )
            return
        peer = self.peer.copy()
        pin = self.pin.get_text()
        self.send_button.set_sensitive(False)
        self.details.set_label(_("Waiting for the recipient to accept…"))

        def work():
            try:
                send(
                    self.paths,
                    peer,
                    self.cancel,
                    lambda done, total: GLib.idle_add(
                        self.progress.set_fraction, done / max(1, total)
                    ),
                    pin,
                )
                GLib.idle_add(self.details.set_label, _("Transfer complete."))
            except Exception as exc:
                GLib.idle_add(self.details.set_label, display(exc))
            finally:
                GLib.idle_add(self.send_button.set_sensitive, True)

        threading.Thread(target=work, daemon=True).start()

    def stop(self):
        self.cancel.set()
        self.close()
