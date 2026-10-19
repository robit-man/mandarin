#!/usr/bin/env python3
"""Wrap the same complete payload for strict-confinement Snap qualification."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.package_policy import sanitize, violations


def main():
    payload = ROOT / "build/package-root"
    if not (payload / "opt/mandarin/runtime-manifest.json").exists():
        raise RuntimeError("Build the complete Ubuntu payload first.")
    target = ROOT / "build/snap-root"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        payload,
        target,
        copy_function=os.link,
        symlinks=True,
        ignore=shutil.ignore_patterns("DEBIAN"),
    )
    metadata = target / "meta"
    metadata.mkdir()
    shutil.copy2(ROOT / "packaging/snap.yaml", metadata / "snap.yaml")
    gui = metadata / "gui"
    gui.mkdir()
    shutil.copy2(ROOT / "mandarin/resources/org.mandarin.Converter.svg", gui / "icon.svg")
    desktop = (ROOT / "packaging/org.mandarin.Converter.desktop").read_text()
    desktop = desktop.replace("Icon=org.mandarin.Converter", "Icon=${SNAP}/meta/gui/icon.svg")
    (gui / "mandarin.desktop").write_text(desktop)
    sanitize(target)
    if violations(target):
        raise RuntimeError("Unsafe Snap payload permissions or extended attributes.")
    subprocess.run(["snap", "pack", "--check-skeleton", str(target)], check=True)
    subprocess.run(
        ["snap", "pack", "--compression=xz", str(target), str(ROOT / "dist")], check=True
    )


if __name__ == "__main__":
    main()
