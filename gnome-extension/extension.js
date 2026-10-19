import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

// No file data or parsing runs in GNOME Shell. A real GTK drop target acquires
// the offered data after the companion positions its window under the drag.
export default class MandarinExtension extends Extension {
    enable() {
        this._drag = false;
        this._invoked = false;
        this._lastModifiers = 0;
        this._anchor = null;
        this._signals = [];
        this._pendingFrames = new Map();
        const dnd = global.backend.get_dnd();
        this._signals.push([dnd, dnd.connect('dnd-enter', () => {
            this._drag = true;
            this._invoked = false;
            this._lastModifiers = global.get_pointer()[2];
        })]);
        this._signals.push([dnd, dnd.connect('dnd-leave', () => {
            this._drag = false;
            this._invoked = false;
        })]);
        this._signals.push([global.display, global.display.connect('window-created', (_, window) => {
            if (!this._anchor) return;
            const actor = window.get_compositor_private();
            if (actor) {
                const id = actor.connect('first-frame', () => {
                    actor.disconnect(id);
                    this._pendingFrames.delete(actor);
                    this._position(window);
                });
                this._pendingFrames.set(actor, id);
            }
        })]);
        this._poll = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 30, () => {
            if (!this._drag) return GLib.SOURCE_CONTINUE;
            const [x, y, modifiers] = global.get_pointer();
            const pressed = modifiers & ~this._lastModifiers;
            this._lastModifiers = modifiers;
            if (!(modifiers & Clutter.ModifierType.BUTTON1_MASK)) return GLib.SOURCE_CONTINUE;
            let mode = null;
            if (pressed & Clutter.ModifierType.SHIFT_MASK) mode = 'convert';
            else if (pressed & Clutter.ModifierType.CONTROL_MASK) mode = 'tools';
            else if (pressed & Clutter.ModifierType.MOD1_MASK) mode = 'actions';
            if (mode) this._summon(mode, x, y);
            return GLib.SOURCE_CONTINUE;
        });
    }

    _summon(mode, x, y) {
        this._anchor = [x, y];
        this._invoked = true;
        Gio.DBus.session.call('org.mandarin.Converter', '/org/mandarin/Converter',
            'org.gtk.Actions', 'Activate',
            new GLib.Variant('(sava{sv})', ['summon', [new GLib.Variant('s', mode)], {}]),
            null, Gio.DBusCallFlags.NONE, 3000, null, (connection, result) => {
                try {
                    connection.call_finish(result);
                    for (const actor of global.get_window_actors()) this._position(actor.meta_window);
                } catch (error) {
                    console.warn(`Mandarin could not open: ${error.message}`);
                }
            });
    }

    _position(window) {
        if (!this._anchor || window.get_wm_class() !== 'org.mandarin.Converter') return;
        const [x, y] = this._anchor;
        const frame = window.get_frame_rect();
        const monitor = global.display.get_monitor_geometry(window.get_monitor());
        const left = Math.max(monitor.x, Math.min(x - frame.width / 2, monitor.x + monitor.width - frame.width));
        const top = Math.max(monitor.y, Math.min(y - frame.height / 2, monitor.y + monitor.height - frame.height));
        window.move_frame(true, Math.round(left), Math.round(top));
        window.raise();
        this._anchor = null;
    }

    disable() {
        if (this._poll) GLib.source_remove(this._poll);
        this._poll = null;
        for (const [actor, id] of this._pendingFrames ?? []) {
            try { actor.disconnect(id); } catch (_) { /* Actor may have been destroyed. */ }
        }
        this._pendingFrames = null;
        for (const [object, id] of this._signals ?? []) object.disconnect(id);
        this._signals = [];
        this._anchor = null;
        this._drag = false;
    }
}
