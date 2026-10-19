#!/usr/bin/env python3
"""Build a complete offline Ubuntu payload from an explicit dependency closure.

No engine is left as a host dependency. Missing roots/providers/files abort the
build. The resulting manifest records every staged package, binary and hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mandarin.runtime import ENGINE_PATHS

PREFIX = Path("opt/mandarin")
SYSTEM_PREFIX = "/opt/mandarin"


def command(arguments):
    return subprocess.check_output(arguments, text=True)


def package_database():
    rows = command(
        [
            "dpkg-query",
            "-W",
            "-f=${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Status}\t${Pre-Depends}, ${Depends}\t${Provides}\n",
        ]
    )
    packages = {}
    aliases = {}
    native = command(["dpkg", "--print-architecture"]).strip()
    for line in rows.splitlines():
        values = line.split("\t")
        if len(values) != 6 or values[3] != "installed" or values[2] not in {native, "all"}:
            continue
        name, version, architecture, _, depends, provides = values
        base = name.split(":", 1)[0]
        packages[name] = {
            "name": name,
            "version": version,
            "architecture": architecture,
            "depends": depends,
        }
        aliases.setdefault(base, name)
        aliases[name] = name
        for provided in provides.split(","):
            provider = re.split(r"\s|\(", provided.strip())[0]
            if provider:
                aliases.setdefault(provider, name)
    return packages, aliases


def dependency_closure(roots):
    packages, aliases = package_database()
    selected = {}
    pending = list(roots)
    while pending:
        requested = pending.pop()
        key = aliases.get(requested)
        if key is None:
            raise RuntimeError(
                f"Required package {requested} is not installed. Run scripts/bootstrap-build.sh first."
            )
        if key in selected:
            continue
        package = packages[key]
        selected[key] = package
        for clause in package["depends"].split(","):
            alternatives = []
            for alternative in clause.split("|"):
                name = re.split(r"\s|\(", alternative.strip())[0]
                if name:
                    alternatives.append(name.replace(":any", "").replace(":native", ""))
            if not alternatives:
                continue
            chosen = next((name for name in alternatives if name in aliases), None)
            if chosen is None:
                raise RuntimeError(f"Unresolved dependency of {key}: {clause}")
            pending.append(chosen)
    return [selected[key] for key in sorted(selected)]


def build(stage_only=False):
    (ROOT / "dist/verification.json").unlink(missing_ok=True)
    source_manifest = json.loads((ROOT / "packaging/runtime-packages.json").read_text())
    packages = dependency_closure(source_manifest["packages"])
    overrides = json.loads((ROOT / "packaging/runtime-overrides.json").read_text())
    for package in packages:
        override = overrides.get(package["name"].split(":")[0])
        if override:
            package["version"] = override["version"]
            directory = ROOT / "build/runtime-overrides"
            directory.mkdir(exist_ok=True)
            path = directory / (package["name"].split(":")[0] + ".deb")
            if not path.exists():
                with urlopen(override["url"], timeout=30) as source:
                    path.write_bytes(source.read())
            if hashlib.sha256(path.read_bytes()).hexdigest() != override["sha256"]:
                raise RuntimeError("Runtime override checksum mismatch: " + package["name"])
    stage = ROOT / "build/package-root"
    if stage.exists():
        shutil.rmtree(stage)
    application = stage / PREFIX
    runtime = application / "runtime"
    runtime.mkdir(parents=True)
    records = {}
    seen = set()

    def copy_path(source):
        source = Path(source)
        key = str(source)
        if key in seen:
            return
        seen.add(key)
        if not source.is_absolute() or str(source).startswith(
            ("/proc/", "/sys/", "/dev/", "/run/", "/var/")
        ):
            return
        target = runtime / str(source).lstrip("/")
        if source.is_symlink():
            target.parent.mkdir(parents=True, exist_ok=True)
            link = os.readlink(source)
            actual = (
                Path(os.path.normpath(str(source.parent / link)))
                if not link.startswith("/")
                else Path(link)
            )
            if actual.exists() or actual.is_symlink():
                copy_path(actual)
                translated = os.path.relpath(runtime / str(actual).lstrip("/"), target.parent)
                if target.exists() or target.is_symlink():
                    target.unlink()
                target.symlink_to(translated)
            return
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            return
        if not source.is_file():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    for index, package in enumerate(packages):
        if package["name"].split(":")[0] in overrides:
            archive = ROOT / "build/runtime-overrides" / (package["name"].split(":")[0] + ".deb")
            subprocess.run(["dpkg-deb", "--extract", str(archive), str(runtime)], check=True)
            continue
        files = command(["dpkg-query", "-L", package["name"]]).splitlines()
        for source in files:
            copy_path(source)
        if index % 40 == 0:
            print(
                f"Staging package {index + 1}/{len(packages)}: {package['name']}",
                flush=True,
            )
    # Alternatives symlinks and compiled configuration are not necessarily owned
    # by the package that supplies the real executable. Stage them explicitly.
    for path in ENGINE_PATHS.values():
        copy_path(path)
    for path in [
        "/usr/bin/python3.12",
        "/lib64/ld-linux-x86-64.so.2",
        "/etc/ld.so.cache",
        "/etc/fonts/fonts.conf",
        "/etc/ImageMagick-6/policy.xml",
    ]:
        copy_path(path)
    for source in [
        Path("/etc/fonts"),
        Path("/etc/libreoffice"),
        Path("/etc/ImageMagick-6"),
    ]:
        if source.is_dir():
            for member in source.rglob("*"):
                copy_path(member)

    # Canonical relocation of compiled cache/config paths. Private copies only.
    for path in runtime.rglob("*"):
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
            continue
        if path.suffix not in {
            ".conf",
            ".cfg",
            ".rc",
            ".ini",
            ".cache",
            ".xml",
            ".xcu",
            ".xcs",
        } and path.name not in {
            "fundamentalrc",
            "bootstraprc",
            "unorc",
            "lounorc",
            "fonts.conf",
            "loaders.cache",
        }:
            continue
        try:
            text = path.read_text()
        except (UnicodeError, OSError):
            continue
        for prefix in [
            "/usr/lib/libreoffice",
            "/usr/share/libreoffice",
            "/etc/libreoffice",
            "/usr/share/fonts",
            "/var/cache/fontconfig",
        ]:
            text = text.replace(prefix, SYSTEM_PREFIX + "/runtime" + prefix)
        if path.name == "loaders.cache":
            text = text.replace('"/usr/lib/', '"' + SYSTEM_PREFIX + "/runtime/usr/lib/")
        path.write_text(text)

    shutil.copytree(
        ROOT / "mandarin",
        application / "mandarin",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    (application / "bin").mkdir()
    shutil.copy2(ROOT / "build/mandarin-sandbox", application / "bin/mandarin-sandbox")
    shutil.copy2(ROOT / "build/mandarin-office", application / "bin/mandarin-office")
    (application / "etc/fonts").mkdir(parents=True)
    (application / "etc/fonts/fonts.conf").write_text(
        f"""<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><dir>{SYSTEM_PREFIX}/runtime/usr/share/fonts</dir><cachedir prefix="xdg">fontconfig</cachedir><config><rescan><int>0</int></rescan></config></fontconfig>"""
    )

    launcher = stage / "usr/bin/mandarin"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text("""#!/bin/sh
set -eu
APP=/opt/mandarin
export PYTHONHOME="$APP/runtime/usr"
export PYTHONPATH="$APP"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export LD_LIBRARY_PATH="$APP/runtime/usr/lib/libreoffice/program:$APP/runtime/usr/lib/x86_64-linux-gnu:$APP/runtime/usr/lib/x86_64-linux-gnu/pulseaudio:$APP/runtime/usr/lib/x86_64-linux-gnu/blas:$APP/runtime/usr/lib/x86_64-linux-gnu/lapack:$APP/runtime/lib/x86_64-linux-gnu:$APP/runtime/usr/lib"
export GI_TYPELIB_PATH="$APP/runtime/usr/lib/x86_64-linux-gnu/girepository-1.0"
export GIO_EXTRA_MODULES="$APP/runtime/usr/lib/x86_64-linux-gnu/gio/modules"
export GSETTINGS_SCHEMA_DIR="$APP/runtime/usr/share/glib-2.0/schemas"
export XDG_DATA_DIRS="$APP/runtime/usr/share:/usr/local/share:/usr/share"
export FONTCONFIG_PATH="$APP/etc/fonts"
export GTK_PATH="$APP/runtime/usr/lib/x86_64-linux-gnu/gtk-4.0"
export GDK_PIXBUF_MODULE_FILE="$APP/runtime/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache"
export GSK_RENDERER="${GSK_RENDERER:-cairo}"
exec "$APP/runtime/lib64/ld-linux-x86-64.so.2" --library-path "$LD_LIBRARY_PATH" "$APP/runtime/usr/bin/python3.12" -P -m mandarin "$@"
""")
    launcher.chmod(0o755)
    # Explicitly compiled toolkit data is part of the payload too.
    schema = runtime / "usr/share/glib-2.0/schemas"
    if schema.is_dir():
        subprocess.run(["/usr/bin/glib-compile-schemas", str(schema)], check=True)
    icon = stage / "usr/share/icons/hicolor/scalable/apps"
    icon.mkdir(parents=True)
    shutil.copy2(ROOT / "mandarin/resources/org.mandarin.Converter.svg", icon)
    for source, target in [
        ("org.mandarin.Converter.desktop", "usr/share/applications"),
        ("org.mandarin.Converter.service", "usr/share/dbus-1/services"),
    ]:
        destination = stage / target
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "packaging" / source, destination)
    extension = stage / "usr/share/gnome-shell/extensions/mandarin@local"
    shutil.copytree(ROOT / "gnome-extension", extension)
    # Preserve all third-party copyright/notices from each staged Debian package.
    documentation = stage / "usr/share/doc/mandarin"
    documentation.mkdir(parents=True)
    shutil.copy2(ROOT / "README.md", documentation / "README.md")
    shutil.copy2(ROOT / "SOP.md", documentation / "SOP.md")
    shutil.copy2(ROOT / "LICENSE", documentation / "copyright")
    shutil.copy2(ROOT / "THIRD-PARTY.md", documentation / "THIRD-PARTY.md")
    (documentation / "NOTICE").write_text(
        "Mandarin testing preview. Third-party package versions/notices are under /opt/mandarin/runtime/usr/share/doc. Exact corresponding-source archives are provided beside the installer at https://github.com/robit-man/mandarin/releases/tag/v0.1.0. No Tangerine source, artwork or binary is included.\n"
    )
    for path in runtime.rglob("*"):
        if path.is_file() and not path.is_symlink():
            with path.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            records[str(path.relative_to(application))] = {
                "sha256": digest,
                "bytes": path.stat().st_size,
            }
    for name, path in ENGINE_PATHS.items():
        target = runtime / path.lstrip("/")
        if not target.is_file():
            raise RuntimeError(f"Missing required bundled engine {name}: {target}")
    manifest = {
        "schema_version": 1,
        "version": "0.1.0",
        "profile": "full-payload-preview",
        "baseline": "Ubuntu 24.04 amd64",
        "host_converter_dependencies": [],
        "first_run_downloads": False,
        "required_engines": ENGINE_PATHS,
        "packages": [{k: p[k] for k in ("name", "version", "architecture")} for p in packages],
        "runtime_overrides": overrides,
        "files": records,
    }
    (application / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    control = stage / "DEBIAN"
    control.mkdir()
    size = (
        sum(p.stat().st_size for p in stage.rglob("*") if p.is_file() and not p.is_symlink())
        // 1024
    )
    (control / "control").write_text(f"""Package: mandarin
Version: 0.1.0
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Mandarin project <mandarin@localhost>
Depends: libc6 (>= 2.39)
Installed-Size: {size}
Description: Offline contextual file conversion for Ubuntu
 Complete private runtime, conversion engines, codecs, office filters,
 fonts and local recognition assets. No converter dependency downloads.
 GNOME companion requires explicit user enablement.
""")
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    (output / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"Staged {len(packages)} pinned packages, {len(records)} runtime files, {size // 1024} MiB.",
        flush=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_runtime.py"), str(application)], check=True
    )
    if not stage_only:
        artifact = output / "mandarin_0.1.0_amd64.deb"
        subprocess.run(
            [
                "dpkg-deb",
                "--root-owner-group",
                "--threads-max=2",
                "-Zzstd",
                "-z10",
                "--build",
                str(stage),
                str(artifact),
            ],
            check=True,
        )
        with artifact.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        (output / "SHA256SUMS").write_text(f"{digest}  {artifact.name}\n")
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_package.py"), str(artifact)], check=True
        )
        print(f"Built and verified {artifact} ({artifact.stat().st_size // 1024 // 1024} MiB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-only", action="store_true")
    args = parser.parse_args()
    try:
        build(args.stage_only)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Package build failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
