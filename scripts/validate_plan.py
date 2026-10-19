#!/usr/bin/env python3
"""Validate Mandarin's planning artifacts; this does not test an application."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        ERRORS.append(message)


def read_json(relative: str) -> dict:
    with (ROOT / relative).open(encoding="utf-8") as handle:
        return json.load(handle)


def check_ids(rows: list[dict], prefix: str, start: int = 1) -> None:
    expected = [f"{prefix}-{number:03d}" for number in range(start, start + len(rows))]
    check([row.get("id") for row in rows] == expected, f"Non-contiguous {prefix} IDs")


def main() -> int:
    inventory = read_json(".aiwg/requirements/parity-inventory.json")
    sources = read_json(".aiwg/research/sources.json")
    conversions = inventory["conversions"]
    tools = inventory["tools"]
    additional = inventory["additional_observed_tools"]
    actions = inventory["actions"]
    reference = inventory["reference"]
    check(inventory["schema_version"] == 1, "Unsupported inventory schema")
    check(inventory["baseline_date"] == sources["baseline_date"], "Baseline dates differ")
    check(
        len(conversions) == reference["conversion_count_advertised"] == 275,
        "Expected 275 baseline conversion pairs",
    )
    check(
        len(tools) == reference["tool_count_advertised"] == 26,
        "Expected 26 demo catalog tools",
    )
    check(
        len(additional) == 1 and additional[0]["id"] == "TOOL-027",
        "Keep additional QR observation separate from the 26-tool catalog",
    )
    check(
        len(actions) == reference["action_count_advertised"] == 6,
        "Expected six actions",
    )
    check_ids(conversions, "CONV")
    check_ids(tools, "TOOL")
    check_ids(additional, "TOOL", 27)
    check_ids(actions, "ACT")
    aggregate_tools = []
    batch_tools = []
    for tool in tools:
        observed = tool["reference_applicability"]
        check(
            observed["scope"] == "simulated-demo-only",
            f"Tool observation loses simulation boundary: {tool['id']}",
        )
        if observed["batch_supported_in_demo"]:
            batch_tools.append(tool["id"])
        if observed["operation_mode"] == "aggregate":
            aggregate_tools.append(tool["id"])
            check(
                observed["minimum_inputs_observed"] == 2,
                f"Aggregate cardinality differs: {tool['id']}",
            )
    check(len(batch_tools) == 11, "Expected 11 demo batch-eligible tool identifiers")
    check(len(aggregate_tools) == 4, "Expected four demo aggregate tool identifiers")

    pairs = [(row["input"], row["output"]) for row in conversions]
    check(len(set(pairs)) == len(pairs), "Duplicate conversion pair")
    check(all(source != target for source, target in pairs), "Identity conversion counted")
    input_only = {"svg", "rar", "ppt", "xls", "rtf", "rtfd", "textClipping"}
    check(
        not any(target in input_only for _, target in pairs),
        "Reference input-only format incorrectly used as output",
    )
    check(
        not any(source == "html" for source, _ in pairs),
        "Reference HTML output-only boundary changed",
    )
    check(
        sum(target == "pages" for _, target in pairs) == 8,
        "Native Pages export obligations changed",
    )

    source_ids = {row["id"] for row in sources["sources"]}
    check(len(source_ids) == len(sources["sources"]), "Duplicate source ID")
    tests = (ROOT / ".aiwg/testing/test-plan.md").read_text(encoding="utf-8")
    statuses = {"planned", "in-progress", "implemented", "verified", "blocked"}
    milestones = {f"M{number}" for number in range(7)}
    all_rows = conversions + tools + additional + actions
    for row in all_rows:
        identifier = row["id"]
        check(row["implementation_status"] in statuses, f"Invalid status: {identifier}")
        check(row["milestone"] in milestones, f"Invalid milestone: {identifier}")
        check(
            bool(row["evidence"]) and set(row["evidence"]) <= source_ids,
            f"Unknown or absent reference evidence: {identifier}",
        )
        check(row["acceptance_test"] in tests, f"Missing test suite: {identifier}")
        check(
            bool(row.get("reference_validation")),
            f"Missing reference observation classification: {identifier}",
        )
        if row["implementation_status"] == "verified":
            check(
                bool(row.get("certification_evidence")),
                f"Verified without certification evidence: {identifier}",
            )

    csv_path = ROOT / ".aiwg/requirements/conversion-matrix.csv"
    with csv_path.open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.DictReader(handle))
    columns = [
        "id",
        "input",
        "output",
        "milestone",
        "adapter",
        "risk",
        "implementation_status",
    ]
    check(
        csv_rows == [{key: row[key] for key in columns} for row in conversions],
        "CSV and JSON conversion inventories differ",
    )

    srs = (ROOT / ".aiwg/requirements/srs.md").read_text(encoding="utf-8")
    for prefix, count in [
        ("REQ-UI", 10),
        ("REQ-CTX", 5),
        ("REQ-JOB", 7),
        ("NFR", 12),
        ("UC", 8),
    ]:
        for number in range(1, count + 1):
            identifier = f"{prefix}-{number:03d}"
            check(f"| {identifier} |" in srs, f"Missing requirement: {identifier}")

    required_files = [
        "README.md",
        "PLAN.md",
        "SOP.md",
        ".aiwg/architecture/sad.md",
        ".aiwg/research/reports/tangerine-feature-review.md",
        ".aiwg/risks/risk-register.md",
        ".aiwg/testing/test-plan.md",
    ]
    for relative in required_files:
        check((ROOT / relative).is_file(), f"Missing document: {relative}")

    markdown_files = sorted(
        path
        for path in ROOT.rglob("*.md")
        if not ({"build", "dist", ".git", ".venv"} & set(path.relative_to(ROOT).parts))
    )
    checked_links = 0
    for path in markdown_files:
        content = path.read_text(encoding="utf-8")
        # Ignore fenced examples; validate actual inline Markdown file links.
        prose = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
        for match in re.finditer(r"\[[^\]]*\]\((<[^>]+>|[^\s)]+)\)", prose):
            target = match.group(1).strip("<>")
            if target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            clean = unquote(target.split("#", 1)[0])
            if not clean:
                continue
            check(
                (path.parent / clean).exists(),
                f"Broken file link in {path.relative_to(ROOT)}: {target}",
            )
            checked_links += 1

    index_path = ROOT / ".aiwg/reports/artifact-index.json"
    if index_path.is_file():
        index = read_json(".aiwg/reports/artifact-index.json")
        for artifact in index["artifacts"]:
            check(
                (ROOT / artifact["path"]).is_file(),
                f"Missing indexed artifact: {artifact['path']}",
            )
            for evidence in artifact.get("review_evidence", []):
                check((ROOT / evidence).is_file(), f"Missing review evidence: {evidence}")

    if ERRORS:
        print("Planning validation FAILED:")
        for error in ERRORS:
            print(f"- {error}")
        return 1
    planned = sum(row["implementation_status"] == "planned" for row in all_rows)
    print(
        f"PASS: {len(conversions)} directed conversion pairs, {len(tools)} catalog tools, "
        f"{len(additional)} additional tool, {len(actions)} actions."
    )
    print(
        f"PASS: CSV/JSON consistency, source/test references, 42 requirement/use-case IDs, "
        f"{len(markdown_files)} Markdown files, {checked_links} local links."
    )
    print(
        f"Status: {planned}/{len(all_rows)} inventory entries remain planned. "
        "No application, conversion, desktop or package tests were run by this validator."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Planning validation FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
