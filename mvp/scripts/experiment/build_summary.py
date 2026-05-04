"""Build a presentation-friendly Markdown summary for Assignment 3 test runs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACTS = ROOT / "artifacts"
DEFAULT_OUTPUT = DEFAULT_ARTIFACTS / "summary.md"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "n/a"


def ms(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "n/a"


def count(value: Any) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return "n/a"


def infer_test_result(text: str) -> str:
    failed = re.search(r"(\d+)\s+failed", text)
    passed = re.search(r"(\d+)\s+passed", text)
    errors = re.search(r"(\d+)\s+errors?", text)
    if failed or errors:
        parts = []
        if passed:
            parts.append(f"{passed.group(1)} passed")
        if failed:
            parts.append(f"{failed.group(1)} failed")
        if errors:
            parts.append(f"{errors.group(1)} errors")
        return ", ".join(parts)
    if passed:
        return f"{passed.group(1)} passed"
    return "not available"


def collect_pytest_rows(artifacts: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    candidates = [
        ("Unit tests", artifacts / "unit" / "unit-results.txt"),
        ("Integration smoke", artifacts / "integration" / "integration-smoke-results.txt"),
    ]
    for suite, path in candidates:
        text = read_text(path)
        if text:
            rows.append([suite, infer_test_result(text), str(path.relative_to(ROOT))])

    if rows:
        return rows

    fallback = ROOT / "docs" / "assignment3" / "local_validation_summary.md"
    text = read_text(fallback)
    if not text:
        return [["Unit and integration tests", "not available", "run the defense script to populate artifacts"]]

    for suite in ("Unit tests", "Integration smoke"):
        pattern = rf"\|\s*{re.escape(suite)}\s*\|\s*([^|]+?)\s*\|"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            rows.append([suite, match.group(1).strip(), str(fallback.relative_to(ROOT))])

    return rows or [["Unit and integration tests", "not available", str(fallback.relative_to(ROOT))]]


def scenario_from_file(path: Path) -> str:
    name = path.stem
    name = name.removesuffix("-summary").removesuffix("_summary")
    name = name.replace("smoke-", "")
    return name.replace("-", " ").replace("_", " ").title()


def metric_value(metrics: dict[str, Any], metric: str, field: str) -> Any:
    value = metrics.get(metric)
    if isinstance(value, dict):
        return value.get(field)
    return None


def collect_performance_rows(artifacts: Path) -> list[list[str]]:
    perf_dir = artifacts / "performance"
    rows: list[list[str]] = []
    for path in sorted(perf_dir.glob("*.json")):
        data = read_json(path)
        if not data:
            continue
        metrics = data.get("metrics", {})
        if not isinstance(metrics, dict):
            continue
        checks = metric_value(metrics, "checks", "rate")
        failures = metric_value(metrics, "http_req_failed", "rate")
        duration = metrics.get("http_req_duration", {})
        p95 = duration.get("p(95)") if isinstance(duration, dict) else None
        requests = metric_value(metrics, "http_reqs", "count")
        rows.append(
            [
                scenario_from_file(path),
                pct(checks),
                pct(failures),
                ms(p95),
                count(requests),
                str(path.relative_to(ROOT)),
            ]
        )
    return rows or [["Performance", "not available", "not available", "not available", "not available", "run k6 scenarios"]]


def mutation_score(killed: int, survived: int, timeout: int, suspicious: int) -> str:
    denominator = killed + survived + timeout + suspicious
    if denominator <= 0:
        return "n/a"
    return f"{(killed / denominator) * 100:.1f}%"


def collect_mutation_from_json(path: Path) -> list[str] | None:
    data = read_json(path)
    if not data:
        return None
    totals = data.get("totals", data)
    if not isinstance(totals, dict):
        return None
    killed = int(totals.get("killed", 0) or 0)
    survived = int(totals.get("survived", 0) or 0)
    timeout = int(totals.get("timeout", totals.get("timeouts", 0)) or 0)
    suspicious = int(totals.get("suspicious", 0) or 0)
    return [
        path.parent.name,
        str(killed),
        str(survived),
        str(timeout),
        str(suspicious),
        mutation_score(killed, survived, timeout, suspicious),
        str(path.relative_to(ROOT)),
    ]


def collect_mutation_from_text(path: Path) -> list[str] | None:
    text = read_text(path)
    if not text:
        return None
    categories = {"killed": 0, "survived": 0, "timeout": 0, "suspicious": 0}
    aliases = {"timeouts": "timeout", "suspicious": "suspicious", "survived": "survived", "killed": "killed"}
    for label, amount in re.findall(r"^(Killed|Survived|Timeouts?|Suspicious).*?\((\d+)\)", text, flags=re.MULTILINE):
        key = aliases.get(label.lower())
        if key:
            categories[key] += int(amount)
    if not any(categories.values()):
        return None
    return [
        path.parent.name,
        str(categories["killed"]),
        str(categories["survived"]),
        str(categories["timeout"]),
        str(categories["suspicious"]),
        mutation_score(categories["killed"], categories["survived"], categories["timeout"], categories["suspicious"]),
        str(path.relative_to(ROOT)),
    ]


def collect_mutation_rows(artifacts: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    for path in sorted(artifacts.glob("mutation*/**/mutation-summary.json")):
        row = collect_mutation_from_json(path)
        if row:
            rows.append(row)
    if rows:
        return rows

    for path in sorted(artifacts.glob("mutation*/**/*results*.txt")):
        row = collect_mutation_from_text(path)
        if row:
            rows.append(row)

    return rows or [["Mutation testing", "not available", "not available", "not available", "not available", "not available", "run mutation workflow"]]


def collect_chaos_rows(artifacts: Path) -> list[list[str]]:
    path = artifacts / "chaos" / "chaos-summary.json"
    data = read_json(path)
    if not data:
        return [["Chaos testing", "not available", "not available", "not available", "not available", "run chaos workflow"]]
    rows: list[list[str]] = []
    for result in data.get("results", []):
        if not isinstance(result, dict):
            continue
        rows.append(
            [
                str(result.get("scenario", "unknown")).replace("_", " "),
                count(result.get("probes")),
                f"{count(result.get('recovered'))}/{count(result.get('probes'))}",
                pct(result.get("availability_rate")),
                f"{float(result.get('mean_recovery_seconds', 0) or 0):.2f}",
                str(path.relative_to(ROOT)),
            ]
        )
    return rows or [["Chaos testing", "not available", "not available", "not available", "not available", str(path.relative_to(ROOT))]]


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))
    header_line = "| " + " | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)) + " |"
    divider = "| " + " | ".join("-" * widths[index] for index in range(len(headers))) + " |"
    lines = [header_line, divider]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).ljust(widths[index]) for index, cell in enumerate(row)) + " |")
    return "\n".join(lines)


def build_summary(artifacts: Path) -> str:
    sections = [
        "# Assignment 3 Test Summary",
        "",
        "This file is generated from available test artifacts and is intended for quick defense/demo review.",
        "",
        "## Unit and Integration",
        markdown_table(["Suite", "Result", "Evidence"], collect_pytest_rows(artifacts)),
        "",
        "## Performance",
        markdown_table(["Scenario", "Checks", "HTTP failures", "p95 ms", "Requests", "Evidence"], collect_performance_rows(artifacts)),
        "",
        "## Mutation",
        markdown_table(["Scope", "Killed", "Survived", "Timeout", "Suspicious", "Score", "Evidence"], collect_mutation_rows(artifacts)),
        "",
        "## Chaos",
        markdown_table(["Scenario", "Probes", "Recovered", "Availability during fault", "Mean recovery s", "Evidence"], collect_chaos_rows(artifacts)),
        "",
    ]
    return "\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Assignment 3 summary.md from test artifacts.")
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    artifacts = args.artifacts_dir.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_summary(artifacts), encoding="utf-8")
    print(f"Summary written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
