"""Read Cairo colors from the canonical GTK stylesheet."""

import re
from pathlib import Path

STYLE = Path(__file__).parent / "resources/style.css"


def colors():
    text = STYLE.read_text()
    result = {}
    for name, value in re.findall(r"@define-color\s+(mandarin_\w+)\s+(#[0-9a-fA-F]{6});", text):
        result[name] = tuple(int(value[index : index + 2], 16) / 255 for index in (1, 3, 5))
    return result
