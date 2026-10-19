"""Toolkit-independent radial navigation and deliberate submenu re-arming."""

from __future__ import annotations

import math
import time

from .capabilities import MenuItem


class RadialState:
    def __init__(self, items: list[MenuItem], dwell: float = 0.25):
        self.root = items
        self.stack = []
        self.items = items
        self.hover = None
        self.hover_since = 0.0
        self.dwell = dwell
        self.arm_origin = None
        self.armed = False
        self.dragging = False

    def visible(self) -> list[MenuItem]:
        items = self.items
        if self.stack:
            items = [MenuItem("__back__", "Back", "go-previous-symbolic")] + items
        return items[:8]

    def hit(self, x: float, y: float, cx: float, cy: float, outer: float = 196) -> int | None:
        radius = math.hypot(x - cx, y - cy)
        count = len(self.visible())
        if radius < 66 or radius > outer or count == 0:
            return None
        angle = (math.atan2(y - cy, x - cx) + math.pi / 2 + math.pi / count) % (2 * math.pi)
        return int(angle / (2 * math.pi / count)) % count

    def enter(self, index: int | None, x: float, y: float, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        if self.arm_origin and math.hypot(x - self.arm_origin[0], y - self.arm_origin[1]) >= 8:
            self.arm_origin = None
        if index != self.hover:
            self.hover = index
            self.hover_since = now
            self.armed = False
        if index is None:
            return False
        item = self.visible()[index]
        self.armed = self.arm_origin is None
        if (
            (item.children or item.id == "__back__")
            and now - self.hover_since >= self.dwell
            and self.armed
        ):
            self.choose(index, transition=(x, y))
            return True
        return False

    def choose(self, index: int, transition: tuple | None = None) -> MenuItem | None:
        item = self.visible()[index]
        if item.id == "__back__":
            self.back()
        elif item.children:
            self.stack.append((self.items, item.label))
            self.items = item.children
        elif item.id in {"convert", "tools", "actions"}:
            return None
        else:
            return item
        self.hover = None
        self.armed = False
        self.arm_origin = transition
        return None

    def back(self):
        if self.stack:
            self.items, _ = self.stack.pop()
        self.hover = None
        self.armed = False

    def release(self, index: int | None) -> MenuItem | None:
        if index is None or not self.armed:
            return None
        return self.choose(index)

    @property
    def breadcrumb(self) -> str:
        return " / ".join(label for _, label in self.stack) or "Choose an action"
