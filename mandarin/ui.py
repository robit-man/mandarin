"""Native GTK4 application, radial target, parameter editor and queue."""

from __future__ import annotations

import gettext
import json
import math
import os
import subprocess
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from .capabilities import MenuItem, menu
from .jobs import Job, JobManager
from .operations import BY_ID, QUALITY, validate_options
from .platform import reveal, terminal
from .radial import RadialState
from .runtime import health, python_command, bundle_environment
from .theme import STYLE, colors
from .settings import Settings

_ = gettext.gettext


def display(value) -> str:
    return str(value).encode("utf-8", "replace").decode("utf-8")


def button(label: str, callback, icon: str | None = None) -> Gtk.Button:
    control = Gtk.Button(label=_(label))
    if icon:
        control.set_icon_name(icon)
        control.set_tooltip_text(_(label))
    control.connect("clicked", lambda *_: callback())
    return control


class Wheel(Gtk.Overlay):
    def __init__(self, on_operation, on_category):
        super().__init__()
        self.on_operation = on_operation
        self.on_category = on_category
        self.state = RadialState([])
        self.position = (0, 0)
        self.widgets = []
        self.mode = "radial"
        self.minimum_size = 420
        self.set_size_request(420, 420)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.canvas = Gtk.DrawingArea()
        self.canvas.set_draw_func(self.draw)
        self.set_child(self.canvas)
        self.fixed = Gtk.Fixed()
        self.add_overlay(self.fixed)
        self.canvas.connect("resize", lambda *_: self.rebuild())
        self.center = button("Add files", self.center_action)
        self.center.add_css_class("wheel-center")
        self.center.set_size_request(110, 110)
        self.fixed.put(self.center, 155, 155)
        self.controller = Gtk.EventControllerMotion()
        self.controller.connect("motion", self.motion)
        self.controller.connect("leave", lambda *_: self.leave())
        self.add_controller(self.controller)
        self.timer = GLib.timeout_add(50, self.tick)
        self.connect("unrealize", lambda *_: self.stop())

    def stop(self):
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = 0

    def center_action(self):
        if self.state.stack:
            self.state.back()
            self.rebuild()
            self.on_category(self.state.breadcrumb)
        else:
            self.on_category("add")

    def set_items(self, items: list[MenuItem]):
        self.state = RadialState(items)
        self.rebuild()

    def rebuild(self):
        for widget in self.widgets:
            self.fixed.remove(widget)
        self.widgets = []
        width = max(self.minimum_size, self.get_width())
        height = max(self.minimum_size, self.get_height())
        cx, cy = width / 2, height / 2
        distance = 137 * self.radius() / 192
        self.center.set_label(_("Back") if self.state.stack else _("Add files"))
        hub_width = self.center.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
        hub_height = self.center.measure(Gtk.Orientation.VERTICAL, hub_width)[1]
        self.fixed.move(self.center, cx - hub_width / 2, cy - hub_height / 2)
        items = self.state.visible()
        for index, item in enumerate(items):
            angle = -math.pi / 2 + 2 * math.pi * index / max(1, len(items))
            control = Gtk.Button()
            control.add_css_class("wheel-button")
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            image = Gtk.Image.new_from_icon_name(item.icon)
            image.set_pixel_size(20)
            label = Gtk.Label(label=_(item.label))
            label.set_wrap(True)
            label.set_max_width_chars(12)
            label.set_justify(Gtk.Justification.CENTER)
            content.append(image)
            content.append(label)
            control.set_child(content)
            control.set_size_request(100, 74)
            control.set_tooltip_text(_(item.description or item.label))
            control.connect("clicked", lambda _, i=index: self.activate(i))
            self.fixed.put(
                control,
                cx + distance * math.cos(angle) - 50,
                cy + distance * math.sin(angle) - 37,
            )
            self.widgets.append(control)
        self.canvas.queue_draw()

    def activate(self, index: int):
        selected = self.state.choose(index)
        if selected:
            self.on_operation(selected.id)
        else:
            self.rebuild()
            self.on_category(self.state.breadcrumb)

    def motion(self, controller, x, y):
        self.position = (x, y)
        index = self.state.hit(x, y, self.get_width() / 2, self.get_height() / 2, self.radius() + 4)
        if self.state.enter(index, x, y):
            self.rebuild()
            self.on_category(self.state.breadcrumb)
        self.canvas.queue_draw()

    def leave(self):
        self.state.hover = None
        self.state.armed = False
        self.canvas.queue_draw()

    def tick(self):
        if self.state.dragging:
            x, y = self.position
            index = self.state.hit(
                x, y, self.get_width() / 2, self.get_height() / 2, self.radius() + 4
            )
            if self.state.enter(index, x, y):
                self.rebuild()
                self.on_category(self.state.breadcrumb)
        return GLib.SOURCE_CONTINUE

    def radius(self):
        return min(192, (max(self.minimum_size, min(self.get_width(), self.get_height())) - 36) / 2)

    def draw(self, area, context, width, height):
        palette = colors()
        cx, cy = width / 2, height / 2
        count = len(self.state.visible())
        dark = Adw.StyleManager.get_default().get_dark()
        for index in range(count):
            angle = -math.pi / 2 + 2 * math.pi * index / count
            start, end = (
                angle - math.pi / count + 0.035,
                angle + math.pi / count - 0.035,
            )
            context.new_path()
            context.arc(cx, cy, self.radius(), start, end)
            context.arc_negative(cx, cy, 72, end, start)
            context.close_path()
            if self.state.hover == index:
                rgb = palette["mandarin_soft"] if not dark else (0.34, 0.23, 0.16)
            else:
                rgb = (0.94, 0.925, 0.9) if not dark else (0.18, 0.18, 0.18)
            context.set_source_rgb(*rgb)
            context.fill()


class ParameterDialog(Adw.Window):
    def __init__(self, parent, operation: str):
        super().__init__(
            transient_for=parent,
            modal=True,
            title=_("Conversion settings"),
            default_width=500,
            default_height=560,
        )
        self.parent = parent
        self.operation = operation
        self.paths = parent.paths.copy()
        self.fields = {}
        self.preview_generation = 0
        self.preview_cancel = threading.Event()
        self.preview_timer = 0
        self.closed = False
        definition = BY_ID.get(operation)
        title = (
            ("Convert to " + operation.split(":", 1)[1].upper())
            if operation.startswith("convert:")
            else definition.name
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        box.append(header)
        scroller = Gtk.ScrolledWindow(vexpand=True)
        form = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=16,
            margin_bottom=16,
            margin_start=24,
            margin_end=24,
        )
        label = Gtk.Label(label=_(title), xalign=0)
        label.add_css_class("title-2")
        form.append(label)
        help_label = Gtk.Label(
            label=_("Save a new copy. Your original files stay unchanged."),
            wrap=True,
            xalign=0,
        )
        help_label.add_css_class("subtitle")
        form.append(help_label)
        self.picture = Gtk.Picture(
            height_request=200, can_shrink=True, content_fit=Gtk.ContentFit.CONTAIN
        )
        image_operations = {
            "crop_image",
            "resize",
            "edit_image",
            "annotate",
            "background",
            "redact_image",
        }
        self.has_preview = operation in image_operations and len(parent.paths) == 1
        if self.has_preview:
            form.append(self.picture)
        parameters = (QUALITY,) if operation.startswith("convert:") else definition.parameters
        for parameter in parameters:
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            row.add_css_class("parameter-row")
            name = Gtk.Label(label=_(parameter.label), xalign=0)
            row.append(name)
            if parameter.kind == "number":
                default = parameter.default
                if (
                    operation
                    in {
                        "crop_image",
                        "crop_video",
                        "redact_image",
                        "redact_video",
                        "annotate",
                    }
                    and parameter.key in {"width", "height"}
                    and parent.items
                ):
                    info = parent.items[0]
                    dimensions = (
                        info
                        if "width" in info
                        else next(
                            (
                                stream
                                for stream in info.get("streams", [])
                                if stream.get("codec_type") == "video"
                            ),
                            {},
                        )
                    )
                    default = dimensions.get(parameter.key, default)
                adjustment = Gtk.Adjustment(
                    value=float(default),
                    lower=parameter.minimum,
                    upper=parameter.maximum,
                    step_increment=0.1 if parameter.maximum <= 10 else 1,
                    page_increment=10,
                )
                control = Gtk.SpinButton(
                    adjustment=adjustment, digits=2 if parameter.maximum <= 10 else 0
                )
            elif parameter.kind == "choice":
                control = Gtk.DropDown.new_from_strings([_(choice) for choice in parameter.choices])
                control.set_selected(parameter.choices.index(parameter.default))
            else:
                control = Gtk.Entry(text=str(parameter.default))
            name.set_mnemonic_widget(control)
            row.append(control)
            form.append(row)
            self.fields[parameter.key] = (parameter, control)
            if self.has_preview:
                signal_name = (
                    "value-changed"
                    if parameter.kind == "number"
                    else "notify::selected"
                    if parameter.kind == "choice"
                    else "changed"
                )
                control.connect(signal_name, lambda *_: self.schedule_preview())
        self.error = Gtk.Label(wrap=True, xalign=0)
        self.error.add_css_class("error")
        form.append(self.error)
        scroller.set_child(form)
        box.append(scroller)
        actions = Gtk.Box(
            spacing=12,
            halign=Gtk.Align.END,
            margin_top=12,
            margin_bottom=20,
            margin_start=24,
            margin_end=24,
        )
        actions.append(button("Cancel", self.close))
        self.apply = button("Create copy", self.submit)
        self.apply.add_css_class("suggested-action")
        actions.append(self.apply)
        box.append(actions)
        self.set_content(box)
        self.connect("close-request", self.closing)
        if self.has_preview:
            self.schedule_preview()

    def closing(self, *_):
        self.closed = True
        self.preview_cancel.set()
        if self.preview_timer:
            GLib.source_remove(self.preview_timer)
            self.preview_timer = 0
        return False

    def options(self):
        options = {}
        for key, (parameter, control) in self.fields.items():
            options[key] = (
                control.get_value()
                if parameter.kind == "number"
                else parameter.choices[control.get_selected()]
                if parameter.kind == "choice"
                else control.get_text()
            )
        return validate_options(self.operation, options)

    def schedule_preview(self):
        if self.preview_timer:
            GLib.source_remove(self.preview_timer)
        self.preview_cancel.set()
        self.preview_generation += 1
        self.preview_timer = GLib.timeout_add(250, self.update_preview)

    def update_preview(self):
        self.preview_timer = 0
        generation = self.preview_generation
        try:
            options = self.options()
        except Exception as exc:
            self.error.set_label(display(exc))
            return False
        self.preview_cancel = threading.Event()
        cancel = self.preview_cancel
        source = self.paths[0]

        def work():
            try:
                pixels = self.parent.manager.preview(source, self.operation, options, cancel)
                GLib.idle_add(self.preview_ready, generation, pixels, None)
            except Exception as exc:
                if not cancel.is_set():
                    GLib.idle_add(self.preview_ready, generation, None, display(exc))

        threading.Thread(target=work, daemon=True).start()
        return False

    def preview_ready(self, generation, pixels, error):
        if self.closed or generation != self.preview_generation:
            return
        if error:
            self.error.set_label(error)
            return
        texture = Gdk.MemoryTexture.new(
            pixels["width"],
            pixels["height"],
            Gdk.MemoryFormat.R8G8B8A8,
            GLib.Bytes.new(pixels["data"]),
            pixels["width"] * 4,
        )
        self.picture.set_paintable(texture)
        self.error.set_label("")

    def submit(self):
        try:
            options = self.options()
            self.parent.submit(self.operation, options, self.paths)
            self.close()
        except Exception as exc:
            self.error.set_label(display(exc))


class JobRow(Gtk.Box):
    def __init__(self, window, job: Job):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.window = window
        self.job = job
        self.add_css_class("job-row")
        top = Gtk.Box(spacing=12)
        self.name = Gtk.Label(xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.MIDDLE)
        self.name.add_css_class("job-name")
        top.append(self.name)
        self.action = button("Cancel", self.act)
        top.append(self.action)
        self.append(top)
        self.progress = Gtk.ProgressBar()
        self.append(self.progress)
        self.detail = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.append(self.detail)
        self.update(job)

    def act(self):
        try:
            if self.job.outputs:
                if not self.job.outputs[0].exists():
                    raise ValueError("This output no longer exists at the recorded location.")
                reveal(self.job.outputs[0])
            elif self.job.state in {"failed", "canceled", "interrupted"}:
                self.window.manager.retry(self.job.id)
            else:
                self.window.manager.cancel(self.job.id)
        except Exception as exc:
            self.window.status_message(display(exc), True)

    def update(self, job: Job):
        self.job = job
        label = job.operation.replace("convert:", "Convert to ").replace("_", " ")
        self.name.set_label(
            display(
                label
                + " · "
                + job.inputs[0].name
                + (f" +{len(job.inputs) - 1}" if len(job.inputs) > 1 else "")
            )
        )
        self.progress.set_fraction(job.progress)
        self.detail.set_label(
            display(
                _(
                    {"succeeded": "Completed", "failed": "Failed", "canceled": "Canceled"}.get(
                        job.state, job.state.capitalize()
                    )
                )
                + " · "
                + (job.error or (str(job.outputs[0]) if job.outputs else job.message))
            )
        )
        self.detail.remove_css_class("error")
        if job.error:
            self.detail.add_css_class("error")
        self.action.set_label(
            _("Reveal")
            if job.outputs
            else _("Retry")
            if job.state in {"failed", "canceled", "interrupted"}
            else _("Cancel")
        )
        self.action.set_sensitive(job.state != "publishing")


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, application, popup: bool = False):
        super().__init__(
            application=application,
            title="Mandarin",
            default_width=1000,
            default_height=760,
        )
        self.add_css_class("mandarin")
        self.paths = []
        self.items = []
        self.generation = 0
        self.destination = None
        self.rows = {}
        self.popup = popup
        self.manager = JobManager(callback=lambda job: GLib.idle_add(self.job_changed, job))
        self.settings = Settings()
        self.health = health()
        self.toast = Adw.ToastOverlay()
        self.set_content(self.toast)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast.set_child(outer)
        header = Adw.HeaderBar()
        title = Gtk.Label(label="Mandarin")
        title.add_css_class("brand")
        header.set_title_widget(title)
        header.pack_start(button("Add files", self.pick_files, "list-add-symbolic"))
        header.pack_end(button("Package health", self.show_health, "emblem-system-symbolic"))
        outer.append(header)
        content = Gtk.Box(spacing=20, vexpand=True)
        content.add_css_class("workspace")
        outer.append(content)
        self.files_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.files_panel.set_size_request(240, -1)
        self.files_panel.add_css_class("file-panel")
        content.append(self.files_panel)
        heading = Gtk.Label(label=_("Your files"), xalign=0)
        heading.add_css_class("title-3")
        self.files_panel.append(heading)
        self.selection = Gtk.Label(
            label=_("Drop files here, or choose Add files."), wrap=True, xalign=0
        )
        self.selection.add_css_class("subtitle")
        self.files_panel.append(self.selection)
        file_scroll = Gtk.ScrolledWindow(vexpand=True)
        self.file_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        file_scroll.set_child(self.file_list)
        self.files_panel.append(file_scroll)
        self.files_panel.append(button("Add files", self.pick_files))
        self.files_panel.append(button("Clear selection", lambda: self.set_files([])))
        self.files_panel.append(Gtk.Separator())
        self.output_label = Gtk.Label(label=_("Output: beside the original"), wrap=True, xalign=0)
        self.output_label.add_css_class("subtitle")
        self.files_panel.append(self.output_label)
        self.files_panel.append(button("Choose output folder", self.pick_destination))
        center = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12, hexpand=True, vexpand=True
        )
        content.append(center)
        self.center_column = center
        self.compact_context = button("Selected files and output", self.show_selection)
        self.compact_context.get_child().set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.compact_context.get_child().set_max_width_chars(38)
        self.compact_context.set_visible(popup)
        center.append(self.compact_context)
        self.breadcrumb = Gtk.Label(label=_("Add a file to see what it can become"), wrap=True)
        center.append(self.breadcrumb)
        self.wheel = Wheel(self.activate, self.category_changed)
        self.view_stack = Gtk.Stack(vexpand=True, hexpand=True)
        self.view_stack.add_named(self.wheel, "radial")
        center.append(self.view_stack)
        self.status = Gtk.Label(
            label=_("Everything is processed on this computer."), wrap=True, xalign=0
        )
        self.status.add_css_class("status")
        center.append(self.status)
        self.list_toggle = Gtk.CheckButton(label=_("Show keyboard-friendly list"))
        self.list_toggle.connect(
            "toggled",
            lambda w: self.set_operation_view(w.get_active()),
        )
        center.append(self.list_toggle)
        self.operation_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.operation_list.add_css_class("operation-list")
        op_scroll = Gtk.ScrolledWindow(vexpand=True)
        op_scroll.set_child(self.operation_list)
        self.view_stack.add_named(op_scroll, "list")
        self.job_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        jobs_scroll = Gtk.ScrolledWindow(
            min_content_height=110,
            max_content_height=180,
            propagate_natural_height=True,
        )
        jobs_scroll.set_child(self.job_list)
        self.jobs_scroll = jobs_scroll
        outer.append(jobs_scroll)
        self.add_drop_target()
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.key_pressed)
        self.add_controller(keys)
        self.connect("close-request", self.on_close)
        if popup:
            self.set_compact(True)
        self.refresh_menu()
        self.wheel.state.dwell = self.settings.values["dwell_ms"] / 1000
        for job in list(self.manager.jobs.values())[:30]:
            self.job_changed(job)

    def category_changed(self, value):
        if value == "add":
            self.pick_files()
        else:
            if not self.list_toggle.get_active():
                self.breadcrumb.set_label(_(value))

    def set_operation_view(self, listing):
        self.view_stack.set_visible_child_name("list" if listing else "radial")
        self.breadcrumb.set_label(
            _("All available operations") if listing else _(self.wheel.state.breadcrumb)
        )

    def set_compact(self, value):
        self.popup = value
        self.files_panel.set_visible(not value)
        self.compact_context.set_visible(value)
        (self.add_css_class if value else self.remove_css_class)("compact")
        self.wheel.minimum_size = 340 if value else 420
        self.wheel.set_size_request(self.wheel.minimum_size, self.wheel.minimum_size)
        self.center_column.set_spacing(8 if value else 12)
        self.jobs_scroll.set_min_content_height(110)
        self.jobs_scroll.set_max_content_height(110 if value else 180)
        self.jobs_scroll.set_propagate_natural_height(not value)
        self.set_default_size(480 if value else 1000, 720 if value else 760)
        self.update_compact_context()

    def update_compact_context(self):
        selection = (
            self.paths[0].name if len(self.paths) == 1 else _("%d files selected") % len(self.paths)
        )
        destination = str(self.destination) if self.destination else _("beside originals")
        self.compact_context.set_label(display(selection + " · " + _("Output: ") + destination))
        self.compact_context.set_tooltip_text(_("Review selected files and output folder"))

    def show_selection(self):
        dialog = Adw.Window(
            transient_for=self,
            modal=True,
            title=_("Files and output"),
            default_width=420,
            default_height=420,
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.append(Adw.HeaderBar())
        contents = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_start=20,
            margin_end=20,
            margin_bottom=20,
        )
        scroller = Gtk.ScrolledWindow(vexpand=True)
        names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for path in self.paths:
            names.append(Gtk.Label(label=display(path), xalign=0, wrap=True, selectable=True))
        if not self.paths:
            names.append(Gtk.Label(label=_("No files selected")))
        scroller.set_child(names)
        contents.append(scroller)
        contents.append(
            Gtk.Label(
                label=display(
                    str(self.destination) if self.destination else _("Output: beside originals")
                ),
                xalign=0,
                wrap=True,
            )
        )

        def choose(callback):
            dialog.close()
            callback()

        contents.append(button("Choose files", lambda: choose(self.pick_files)))
        contents.append(button("Choose output folder", lambda: choose(self.pick_destination)))
        contents.append(button("Clear selection", lambda: choose(lambda: self.set_files([]))))
        box.append(contents)
        dialog.set_content(box)
        dialog.present()

    def status_message(self, message, error=False):
        self.status.set_label(display(message))
        self.status.remove_css_class("error")
        if error:
            self.status.add_css_class("error")

    def key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            if self.wheel.state.stack:
                self.wheel.state.back()
                self.wheel.rebuild()
                self.set_operation_view(self.list_toggle.get_active())
            elif self.popup:
                self.close()
            return True
        if keyval == Gdk.KEY_o and state & Gdk.ModifierType.CONTROL_MASK:
            self.pick_files()
            return True
        return False

    def pick_files(self):
        dialog = Gtk.FileDialog(title=_("Choose files"))

        def chosen(dialog, result):
            try:
                files = dialog.open_multiple_finish(result)
                self.set_files(
                    self.paths
                    + [
                        Path(files.get_item(i).get_path())
                        for i in range(files.get_n_items())
                        if files.get_item(i).get_path()
                    ]
                )
            except GLib.Error:
                pass

        dialog.open_multiple(self, None, chosen)

    def pick_destination(self):
        dialog = Gtk.FileDialog(title=_("Choose output folder"))

        def chosen(dialog, result):
            try:
                value = dialog.select_folder_finish(result).get_path()
                if value:
                    self.destination = Path(value)
                    self.output_label.set_label(display("Output: " + value))
                    self.update_compact_context()
            except GLib.Error:
                pass

        dialog.select_folder(self, None, chosen)

    def set_files(self, paths: list[Path]):
        self.generation += 1
        generation = self.generation
        self.paths = list(dict.fromkeys(Path(path).absolute() for path in paths))[:1000]
        self.items = []
        while row := self.file_list.get_first_child():
            self.file_list.remove(row)
        for path in self.paths:
            row = Gtk.Box(spacing=8)
            row.add_css_class("file-row")
            row.append(Gtk.Image.new_from_icon_name("text-x-generic-symbolic"))
            name = Gtk.Label(
                label=display(path.name),
                xalign=0,
                ellipsize=Pango.EllipsizeMode.MIDDLE,
                hexpand=True,
            )
            name.set_tooltip_text(display(path))
            row.append(name)
            row.append(
                button(
                    "Remove file",
                    lambda p=path: self.set_files([v for v in self.paths if v != p]),
                    "window-close-symbolic",
                )
            )
            self.file_list.append(row)
        self.selection.set_label(
            _("No files selected") if not self.paths else _("%d files selected") % len(self.paths)
        )
        self.update_compact_context()
        if not self.paths:
            self.refresh_menu()
            return
        self.status_message(_("Reading file types…"))
        self.wheel.set_items([])

        def inspect():
            try:
                items = self.manager.inspect(self.paths.copy())
                GLib.idle_add(self.probed, generation, items, None)
            except Exception as exc:
                GLib.idle_add(self.probed, generation, [], display(exc))

        threading.Thread(target=inspect, daemon=True).start()

    def probed(self, generation, items, error):
        if generation != self.generation:
            return GLib.SOURCE_REMOVE
        self.items = items
        self.refresh_menu()
        pending = getattr(self, "pending_mode", None)
        if pending and self.wheel.state.root:
            for index, item in enumerate(self.wheel.state.root):
                if item.id == pending:
                    self.wheel.state.choose(index)
                    self.wheel.rebuild()
                    self.set_operation_view(self.list_toggle.get_active())
                    break
            self.pending_mode = None
        if error:
            self.status_message(error, True)
        elif items:
            self.status_message(_("Choose a category. Continue dragging to open its submenu."))
        return GLib.SOURCE_REMOVE

    def refresh_menu(self):
        tree = menu(self.items, self.health["engines"]) if self.items else []
        self.wheel.set_items(tree)
        self.wheel.state.dwell = self.settings.values["dwell_ms"] / 1000
        while child := self.operation_list.get_first_child():
            self.operation_list.remove(child)

        def add(nodes, trail=""):
            for item in nodes:
                if item.children:
                    heading = Gtk.Label(label=_(trail + item.label), xalign=0)
                    heading.add_css_class("heading")
                    heading.set_margin_top(12)
                    self.operation_list.append(heading)
                    add(item.children, trail + item.label + " / ")
                elif item.id not in {"convert", "tools", "actions"}:
                    self.operation_list.append(
                        button(item.label, lambda ident=item.id: self.activate(ident))
                    )

        add(tree)
        if self.paths:
            self.set_operation_view(self.list_toggle.get_active())
        else:
            self.breadcrumb.set_label(_("Add a file to see what it can become"))

    def activate(self, operation):
        if operation.startswith("action:"):
            self.file_action(operation.split(":", 1)[1])
            return
        if not self.paths:
            return
        if operation.startswith("convert:"):
            self.submit(operation, {})
        else:
            ParameterDialog(self, operation).present()

    def submit(self, operation, options, paths=None):
        try:
            if paths is None and not self.items:
                raise ValueError("Wait for file type detection before starting.")
            if operation.startswith("convert:") and not options:
                options = {"quality": self.settings.values["quality"]}
            self.manager.submit(
                self.paths if paths is None else paths, operation, options, self.destination
            )
            self.status_message(_("Queued. Your original files are preserved."))
        except Exception as exc:
            self.status_message(display(exc), True)
            raise

    def job_changed(self, job):
        if job.id not in self.rows:
            self.rows[job.id] = JobRow(self, job)
            self.job_list.prepend(self.rows[job.id])
        else:
            self.rows[job.id].update(job)
        if job.state == "succeeded":
            self.status_message(_("Completed. Your new copy is ready to reveal."))
        elif job.state in {"failed", "partial", "interrupted"}:
            self.status_message(
                job.error or _("This job needs attention. Review its result below."), True
            )
        elif job.state == "canceled":
            self.status_message(_("Canceled. Your original files are preserved."))
        active = sum(
            j.state in {"queued", "running", "validating", "publishing"}
            for j in self.manager.jobs.values()
        )
        action = self.get_application().lookup_action("status")
        if action:
            action.set_state(
                GLib.Variant(
                    "s", _("%d active conversions") % active if active else _("Mandarin is ready")
                )
            )
        return GLib.SOURCE_REMOVE

    def file_action(self, action):
        if not self.paths:
            return
        try:
            clipboard = self.get_display().get_clipboard()
            if action == "path":
                clipboard.set("\n".join(str(p) for p in self.paths))
            elif action == "copy":
                files = Gdk.FileList.new_from_list(
                    [Gio.File.new_for_path(str(p)) for p in self.paths]
                )
                clipboard.set_content(Gdk.ContentProvider.new_for_value(files))
            elif action == "reveal":
                reveal(self.paths[0])
            elif action == "terminal":
                parents = list(dict.fromkeys(p if p.is_dir() else p.parent for p in self.paths))
                if len(parents) > 1:
                    dialog = Adw.MessageDialog(
                        transient_for=self,
                        heading=_("Choose a terminal folder"),
                        body=_("Open one folder from this selection."),
                    )
                    dialog.add_response("cancel", _("Cancel"))
                    for index, parent in enumerate(parents[:10]):
                        dialog.add_response(str(index), display(parent))
                    dialog.connect(
                        "response",
                        lambda d, r: terminal(parents[int(r)]) if r.isdigit() else None,
                    )
                    dialog.present()
                else:
                    terminal(parents[0])
            elif action == "shelf":
                self.show_shelf()
            elif action == "move":
                self.choose_move_destination()
            elif action == "share":
                self.show_share()
            self.status_message(_("Ready"))
        except Exception as exc:
            self.status_message(display(exc), True)

    def choose_move_destination(self):
        picker = Gtk.FileDialog(title=_("Move files to"))

        def chosen(dialog, result):
            try:
                destination = Path(dialog.select_folder_finish(result).get_path())
                confirm = Adw.MessageDialog(
                    transient_for=self,
                    heading=_("Move selected files?"),
                    body=_(
                        "Their original paths will be relocated. Verified recovery copies will be kept beside the source folders."
                    )
                    + "\n\n"
                    + display(destination),
                )
                confirm.add_response("cancel", _("Cancel"))
                confirm.add_response("move", _("Move files"))
                confirm.set_default_response("cancel")

                def accepted(d, response):
                    if response != "move":
                        return
                    paths = self.paths.copy()
                    self.status_message(_("Moving and verifying files…"))

                    def work():
                        try:
                            from .move import move_files

                            result = move_files(paths, destination, self.manager.state_dir)
                            locations = "\n".join(item["recovery"] for item in result["items"])
                            GLib.idle_add(
                                self.status_message,
                                _("Move complete. Recovery data retained at: ") + locations,
                            )
                            GLib.idle_add(
                                self.set_files,
                                [Path(item["destination"]) for item in result["items"]],
                            )
                        except Exception as exc:
                            GLib.idle_add(self.status_message, display(exc), True)

                    threading.Thread(target=work, daemon=True).start()

                confirm.connect("response", accepted)
                confirm.present()
            except GLib.Error:
                pass

        picker.select_folder(self, None, chosen)

    def show_share(self):
        from .share_ui import ShareWindow

        ShareWindow(self, self.paths.copy()).present()

    def show_shelf(self):
        shelf = Adw.Window(
            transient_for=self,
            title=_("Floating files"),
            default_width=320,
            default_height=240,
        )
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_start=16,
            margin_end=16,
            margin_top=16,
            margin_bottom=16,
        )
        box.append(Adw.HeaderBar())
        for path in self.paths:
            control = Gtk.Button(label=display(path.name))
            control.connect("clicked", lambda _, p=path: reveal(p))
            source = Gtk.DragSource(actions=Gdk.DragAction.COPY)
            source.connect(
                "prepare",
                lambda _, x, y, p=path: Gdk.ContentProvider.new_for_value(
                    Gdk.FileList.new_from_list([Gio.File.new_for_path(str(p))])
                ),
            )
            control.add_controller(source)
            box.append(control)
        shelf.set_content(box)
        shelf.present()

    def show_health(self):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Settings and package health"),
            body=_(
                "Conversion tools are bundled in the installed application. No file data is uploaded during conversion."
            ),
        )
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for key, label, low, high in [
            ("dwell_ms", "Submenu dwell (milliseconds)", 150, 600),
            ("quality", "Default image quality", 10, 100),
        ]:
            row = Gtk.Box(spacing=12)
            row.append(Gtk.Label(label=_(label), xalign=0, hexpand=True))
            control = Gtk.SpinButton.new_with_range(low, high, 1)
            control.set_value(self.settings.values[key])
            row.append(control)

            def changed(widget, setting=key):
                self.settings.save(setting, widget.get_value_as_int())
                self.wheel.state.dwell = self.settings.values["dwell_ms"] / 1000

            control.connect("value-changed", changed)
            content.append(row)
        total = len(self.health["engines"])
        present = sum(bool(value) for value in self.health["engines"].values())
        content.append(
            Gtk.Label(label=_("%d of %d conversion engines available") % (present, total), xalign=0)
        )
        content.append(
            Gtk.Label(
                label=_("Worker isolation: ready")
                if self.health["isolation"].get("available")
                else _("Worker isolation unavailable; conversions are blocked"),
                wrap=True,
                xalign=0,
            )
        )
        integration = Gtk.Label(label=_("Checking GNOME drag integration…"), wrap=True, xalign=0)
        content.append(integration)
        enable = button("Enable GNOME drag shortcut", lambda: self.enable_extension(integration))
        content.append(enable)

        def inspect():
            try:
                connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                result = connection.call_sync(
                    "org.gnome.Shell.Extensions",
                    "/org/gnome/Shell/Extensions",
                    "org.gnome.Shell.Extensions",
                    "GetExtensionInfo",
                    GLib.Variant("(s)", ("mandarin@local",)),
                    None,
                    Gio.DBusCallFlags.NONE,
                    3000,
                    None,
                )
                info = result.unpack()[0]
                state = info.get("state", 0)
                message = (
                    _(
                        "GNOME drag shortcut enabled: Shift for formats, Control for tools, Alt for actions."
                    )
                    if state == 1
                    else _(
                        "GNOME companion is disabled. Enable it to invoke the wheel during a drag."
                    )
                    if info
                    else _(
                        "Sign out and back in once after installation so GNOME can load the bundled companion."
                    )
                )
                GLib.idle_add(integration.set_label, message)
            except GLib.Error:
                GLib.idle_add(
                    integration.set_label,
                    _(
                        "GNOME integration is not available in this session. File drops, picker and keyboard actions still work."
                    ),
                )

        threading.Thread(target=inspect, daemon=True).start()
        content.append(button("Clear completed job history", lambda: self.manager.clear_history()))
        dialog.set_extra_child(content)
        dialog.add_response("close", _("Close"))
        dialog.present()

    def enable_extension(self, label):
        def enable():
            try:
                connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                result = connection.call_sync(
                    "org.gnome.Shell.Extensions",
                    "/org/gnome/Shell/Extensions",
                    "org.gnome.Shell.Extensions",
                    "EnableExtension",
                    GLib.Variant("(s)", ("mandarin@local",)),
                    None,
                    Gio.DBusCallFlags.NONE,
                    3000,
                    None,
                )
                message = (
                    _("Drag shortcut enabled. Start a file drag, then tap Shift.")
                    if result.unpack()[0]
                    else _("Sign out and back in, then enable the Mandarin companion.")
                )
                GLib.idle_add(label.set_label, message)
            except GLib.Error as exc:
                GLib.idle_add(label.set_label, display(exc))

        threading.Thread(target=enable, daemon=True).start()

    def add_drop_target(self):
        target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        target.set_preload(True)
        self.last_offer = None

        def receive(controller, value):
            if value is None:
                return False
            paths = [Path(f.get_path()) for f in value.get_files() if f.get_path()]
            key = tuple(str(p) for p in paths)
            if paths and key != self.last_offer:
                self.last_offer = key
                self.set_files(paths)
            return bool(paths)

        target.connect(
            "notify::value",
            lambda controller, _: receive(controller, controller.get_value()),
        )

        def enter(controller, x, y):
            self.wheel.state.dragging = True
            self.add_css_class("drop-active")
            receive(controller, controller.get_value())
            return Gdk.DragAction.COPY

        def motion(controller, x, y):
            bounds = self.wheel.compute_bounds(self)
            if bounds[0]:
                rectangle = bounds[1]
                self.wheel.motion(None, x - rectangle.get_x(), y - rectangle.get_y())
                self.wheel.state.dragging = True
            return Gdk.DragAction.COPY

        def dropped(controller, value, x, y):
            if not receive(controller, value):
                return False
            self.wheel.state.dragging = False
            self.remove_css_class("drop-active")
            selected = self.wheel.state.release(self.wheel.state.hover)
            if selected:
                self.activate(selected.id)
            else:
                self.wheel.rebuild()
                self.status_message(_("Files selected. Choose an operation to continue."))
            self.last_offer = None
            return True

        target.connect("enter", enter)
        target.connect("motion", motion)
        target.connect("drop", dropped)
        target.connect(
            "leave",
            lambda *_: (
                self.remove_css_class("drop-active"),
                setattr(self.wheel.state, "dragging", False),
            ),
        )
        self.add_controller(target)

    def on_close(self, *_):
        if self.get_application().tray_connected:
            self.set_visible(False)
            return True
        active = [
            j
            for j in self.manager.jobs.values()
            if j.state in {"queued", "running", "validating", "publishing"}
        ]
        if active:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading=_("Cancel active conversions?"),
                body=_("Published outputs and original files will be kept."),
            )
            dialog.add_response("keep", _("Keep working"))
            dialog.add_response("cancel", _("Cancel and close"))
            dialog.set_default_response("keep")
            dialog.connect("response", lambda d, r: self.shutdown() if r == "cancel" else None)
            dialog.present()
            return True
        self.manager.close()
        return False

    def shutdown(self):
        self.manager.close()
        self.destroy()


class Application(Adw.Application):
    def __init__(self, popup=False, service=False):
        flags = Gio.ApplicationFlags.HANDLES_OPEN | (
            Gio.ApplicationFlags.IS_SERVICE if service else Gio.ApplicationFlags.FLAGS_NONE
        )
        super().__init__(application_id="org.mandarin.Converter", flags=flags)
        self.window = None
        self.popup = popup
        self.tray_connected = False
        self.indicator_process = None
        self.indicator_held = False

    def do_startup(self):
        Adw.Application.do_startup(self)
        summon = Gio.SimpleAction.new("summon", GLib.VariantType.new("s"))
        summon.connect("activate", self.summon)
        self.add_action(summon)
        self.add_action(
            Gio.SimpleAction.new_stateful("status", None, GLib.Variant("s", _("Mandarin is ready")))
        )
        for name, callback in [
            ("show", self.show_main),
            ("add-files", self.add_files),
            ("jobs", self.show_main),
            ("quit", self.quit_requested),
        ]:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
        provider = Gtk.CssProvider()
        provider.load_from_path(str(STYLE))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        if os.environ.get("MANDARIN_DISABLE_INDICATOR") != "1":
            self.start_indicator()

    def start_indicator(self):
        environment = dict(os.environ)
        environment.update(bundle_environment())
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        environment.pop("GTK_PATH", None)
        try:
            self.indicator_process = subprocess.Popen(
                python_command() + ["-m", "mandarin.indicator", "--parent", str(os.getpid())],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                start_new_session=True,
            )
        except OSError:
            return

        def observe():
            for line in self.indicator_process.stdout:
                try:
                    data = json.loads(line[:4096])
                    GLib.idle_add(self.indicator_changed, data.get("connected") is True)
                except (ValueError, TypeError):
                    continue
            GLib.idle_add(self.indicator_changed, False)

        threading.Thread(target=observe, daemon=True).start()

    def indicator_changed(self, connected):
        self.tray_connected = connected
        if connected and not self.indicator_held:
            self.hold()
            self.indicator_held = True
        elif not connected and self.indicator_held:
            self.release()
            self.indicator_held = False
            if self.window and not self.window.get_visible():
                self.window.present()
        return GLib.SOURCE_REMOVE

    def show_main(self, *_):
        self.do_activate()
        self.window.set_compact(False)

    def add_files(self, *_):
        self.show_main()
        self.window.pick_files()

    def quit_requested(self, *_):
        if self.window and any(
            j.state in {"queued", "running", "validating", "publishing"}
            for j in self.window.manager.jobs.values()
        ):
            dialog = Adw.MessageDialog(
                transient_for=self.window,
                heading=_("Cancel conversions and quit?"),
                body=_("Original files and published results will be kept."),
            )
            dialog.add_response("keep", _("Keep working"))
            dialog.add_response("quit", _("Cancel and quit"))
            dialog.set_default_response("keep")
            dialog.connect(
                "response", lambda _, response: self.quit() if response == "quit" else None
            )
            dialog.present()
            return
        self.quit()

    def do_shutdown(self):
        if self.window:
            self.window.manager.close()
        if self.indicator_process and self.indicator_process.poll() is None:
            self.indicator_process.terminate()
            try:
                self.indicator_process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.indicator_process.kill()
                self.indicator_process.wait(timeout=1)
        Adw.Application.do_shutdown(self)

    def do_activate(self):
        if not self.window:
            self.window = MainWindow(self, self.popup)
        self.window.present()

    def summon(self, action, parameter):
        self.popup = True
        self.do_activate()
        self.window.set_compact(True)
        self.window.pending_mode = parameter.get_string()
        self.window.set_files([])

    def do_open(self, files, n_files, hint):
        self.do_activate()
        self.window.set_files([Path(f.get_path()) for f in files if f.get_path()])
