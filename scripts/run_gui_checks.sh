#!/bin/sh
set -eu
gui_runtime=$(mktemp -d /tmp/mandarin-gui-runtime.XXXXXX)
trap 'fusermount3 -u "$gui_runtime/doc" 2>/dev/null || true; rm -rf "$gui_runtime"' EXIT HUP INT TERM
export XDG_RUNTIME_DIR="$gui_runtime"
export XDG_CONFIG_HOME="$gui_runtime/config"
export XDG_STATE_HOME="$gui_runtime/state"
export GDK_BACKEND=x11
export GSK_RENDERER=cairo
export GIO_USE_VFS=local
export NO_AT_BRIDGE=1
export MANDARIN_DISABLE_INDICATOR=1
dbus-run-session -- xvfb-run -a python3 scripts/gui_smoke.py
dbus-run-session -- xvfb-run -a python3 scripts/drag_smoke.py
dbus-run-session -- xvfb-run -a python3 scripts/indicator_smoke.py
