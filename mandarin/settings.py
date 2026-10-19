"""Small validated preferences; never executable commands or engine paths."""

import json
import os
from pathlib import Path


class Settings:
    def __init__(self):
        self.path = (
            Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
            / "mandarin/settings.json"
        )
        self.values = {"dwell_ms": 250, "quality": 85}
        try:
            data = json.loads(self.path.read_text())
            for key in self.values:
                if (
                    key in data
                    and isinstance(data[key], (int, float))
                    and not isinstance(data[key], bool)
                ):
                    low, high = (150, 600) if key == "dwell_ms" else (10, 100)
                    if low <= data[key] <= high:
                        self.values[key] = int(data[key])
        except (OSError, ValueError, TypeError):
            pass

    def save(self, key, value):
        low, high = (150, 600) if key == "dwell_ms" else (10, 100)
        if key not in self.values or not low <= value <= high:
            raise ValueError("Invalid setting")
        self.values[key] = int(value)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w") as handle:
            os.chmod(temporary, 0o600)
            json.dump(self.values, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
