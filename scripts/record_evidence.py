#!/usr/bin/env python3
"""Freeze passing package evidence and update implementation, not certification."""

import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text())


def main():
    verification = read("dist/verification.json")
    package = read("build/package-qa-ubuntu-24.04/package-report.json")
    tools = read("build/package-qa-ubuntu-24.04/build/tool-report.json")
    if verification["status"] != "pass" or any(
        row["status"] != "pass" for row in package["results"]
    ):
        raise RuntimeError("The actual package has not passed.")
    if len(package["results"]) != verification["conversions"] or any(
        row["status"] != "succeeded" for row in tools["cases"]
    ):
        raise RuntimeError("Incomplete conversion/tool evidence.")
    with (ROOT / "dist" / verification["package"]).open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != verification["sha256"]:
            raise RuntimeError("The tested installer changed.")
    destination = ROOT / ".aiwg/testing/evidence/0.1.0"
    destination.mkdir(parents=True, exist_ok=True)
    for source, target in [
        ("dist/verification.json", "package-verification.json"),
        ("build/package-qa-ubuntu-24.04/package-report.json", "package-results.json"),
        ("build/package-qa-ubuntu-24.04/build/tool-report.json", "tool-results.json"),
        ("build/test-results.log", "application-tests.log"),
        ("build/gui-check.log", "native-gui-tests.log"),
        ("build/ui-static-audit.json", "ui-static-audit.json"),
        ("build/snap-report.json", "snap-results.json"),
        ("build/snap-desktop-report.json", "snap-desktop-results.json"),
        ("build/sources-report.json", "source-archive-results.json"),
        ("build/gui-radial.png", "radial.png"),
        ("build/gui-smoke.png", "keyboard.png"),
        ("build/gui-compact.png", "compact.png"),
        ("build/gui-editor.png", "editor.png"),
    ]:
        shutil.copyfile(ROOT / source, destination / target)
    fixtures = read("build/corpus/fixtures.json")
    fingerprints = {}
    for name, path in fixtures.items():
        with Path(path).open("rb") as handle:
            fingerprints[name] = {
                "name": Path(path).name,
                "sha256": hashlib.file_digest(handle, "sha256").hexdigest(),
            }
    (destination / "fixtures.json").write_text(json.dumps(fingerprints, indent=2) + "\n")
    inventory = read(".aiwg/requirements/parity-inventory.json")
    passing = {(row["input"], row["output"]) for row in package["results"]}
    reference = {(row["input"], row["output"]) for row in inventory["conversions"]}
    for row in inventory["conversions"]:
        pair = (row["input"], row["output"])
        if pair in passing:
            row["implementation_status"] = "implemented"
            row["development_evidence"] = ".aiwg/testing/evidence/0.1.0/package-results.json"
        elif row["output"] == "pages":
            row["implementation_status"] = "blocked"
            row["implementation_note"] = (
                "No native Pages writer; route is absent from runtime menus."
            )
        elif row["input"] == "pages" and row["output"] in {"docx", "pdf", "txt", "png", "jpg"}:
            row["implementation_status"] = "in-progress"
            row["implementation_note"] = (
                "Tentative LibreOffice import; authentic Pages fixture qualification is missing."
            )
    partial = {"TOOL-003", "TOOL-004", "TOOL-005", "TOOL-023", "TOOL-024", "TOOL-025"}
    for row in inventory["tools"] + inventory["additional_observed_tools"]:
        row["implementation_status"] = "in-progress" if row["id"] in partial else "implemented"
        row["development_evidence"] = ".aiwg/testing/evidence/0.1.0/tool-results.json"
        if row["id"] in partial:
            row["implementation_note"] = (
                "Basic modes run; complete advanced reference modes/fidelity remain open."
            )
    for row in inventory["actions"]:
        row["implementation_status"] = "implemented"
        row["development_evidence"] = ".aiwg/testing/evidence/0.1.0/application-tests.log"
        row["implementation_note"] = (
            "Native implementation; full desktop/source-app and recipient-device qualification remains open."
        )
    inventory["status"] = "0.1.0-preview-implemented-not-parity-certified"
    inventory["implementation_extras"] = [
        "Resize image",
        "Reveal output",
        "Taskbar indicator",
        "Typed CLI",
    ]
    (ROOT / ".aiwg/requirements/parity-inventory.json").write_text(
        json.dumps(inventory, indent=2) + "\n"
    )
    fields = ["id", "input", "output", "milestone", "adapter", "risk", "implementation_status"]
    with (ROOT / ".aiwg/requirements/conversion-matrix.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(inventory["conversions"])
    summary = {
        "version": "0.1.0",
        "package_sha256": verification["sha256"],
        "offline_conversion_cases_passed": len(passing),
        "reference_pairs_implemented_with_smoke_evidence": len(passing & reference),
        "additional_conversion_pairs": len(passing - reference),
        "source_formats": len(fingerprints),
        "tool_cases_passed": len(tools["cases"]),
        "operation_identifiers": tools["operations"],
        "conversion_status": dict(
            Counter(row["implementation_status"] for row in inventory["conversions"])
        ),
        "certifies_native_parity": False,
    }
    (destination / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
