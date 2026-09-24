#!/usr/bin/env python3
"""Validate PRD/roadmap and feature FRD/backlog documentation contracts."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REQUIRED_SECTIONS = (
    "Current Condition",
    "Backlog",
    "Scenario Evidence",
    "Blockers",
    "Dependencies",
    "Release Readiness",
    "Deferred",
    "Change Log",
)
BACKLOG_COLUMNS = (
    "ID",
    "FRD Ref",
    "Work Item",
    "Priority",
    "State",
    "Actual Condition",
    "Owner",
    "Dependencies",
    "Updated",
)
COMMIT_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{7,40}(?![0-9a-f])", re.IGNORECASE)
COMMAND_RE = re.compile(r"`[^`]+`")
ID_RE = re.compile(r"^([A-Z][A-Z0-9]*)-\d{2,}$")
FR_RE = re.compile(r"^FR-\d{3}$")


@dataclass(frozen=True)
class Finding:
    code: str
    path: Path
    message: str

    def render(self, root: Path) -> str:
        try:
            location = self.path.relative_to(root)
        except ValueError:
            location = self.path
        return f"{self.code}: {location}: {self.message}"


def _section(text: str, heading: str) -> str:
    match = re.search(
        rf"^## {re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else ""


def _table(section: str) -> tuple[list[str], list[dict[str, str]]]:
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return [], []
    headers = [cell.strip() for cell in lines[0].strip("|").split("|")]
    separator = [cell.strip() for cell in lines[1].strip("|").split("|")]
    if len(separator) != len(headers) or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator):
        return [], []
    rows: list[dict[str, str]] = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells, strict=True)))
    return headers, rows


def _state_vocabulary(roadmap: Path) -> set[str]:
    if not roadmap.is_file():
        return set()
    headers, rows = _table(_section(roadmap.read_text(encoding="utf-8"), "State Vocabulary"))
    if "State" not in headers:
        return set()
    return {row["State"] for row in rows}


def _feature_dirs(root: Path) -> set[Path]:
    modules = root / "modules"
    if not modules.is_dir():
        return set()
    return {member for member in modules.iterdir() if member.is_dir() and any(member.rglob("agent_*_orchestrator.*"))}


def _doc_dirs(root: Path) -> set[Path]:
    ignored = {".git", ".venv", "node_modules", "__pycache__"}
    result: set[Path] = set()
    for name in ("FRD.md", "BACKLOG.md"):
        for path in root.rglob(name):
            if not ignored.intersection(path.parts):
                result.add(path.parent)
    return result


def _check_pairing(root: Path, features: set[Path]) -> list[Finding]:
    findings: list[Finding] = []
    if (root / "PRD.md").is_file() != (root / "ROADMAP.md").is_file():
        findings.append(Finding("root-doc-pair", root, "PRD.md and ROADMAP.md must exist together"))
    for directory in sorted(features):
        frd = directory / "FRD.md"
        backlog = directory / "BACKLOG.md"
        if frd.is_file() and not backlog.is_file():
            findings.append(Finding("spec-without-backlog", directory, "FRD.md requires BACKLOG.md"))
        if backlog.is_file() and not frd.is_file():
            findings.append(Finding("backlog-without-spec", directory, "BACKLOG.md requires FRD.md"))
    for directory in sorted(_doc_dirs(root) - features):
        docs = ", ".join(path.name for path in (directory / "FRD.md", directory / "BACKLOG.md") if path.exists())
        findings.append(Finding("feature-doc-in-shared", directory, f"non-feature folder contains {docs}"))
    return findings


def _check_backlog(backlog: Path, states: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    text = backlog.read_text(encoding="utf-8")
    line_count = len(text.splitlines())
    if not 50 <= line_count <= 500:
        findings.append(Finding("backlog-length", backlog, f"expected 50-500 lines, found {line_count}"))
    for heading in REQUIRED_SECTIONS:
        if not re.search(rf"^## {re.escape(heading)}\s*$", text, re.MULTILINE):
            findings.append(Finding("missing-backlog-section", backlog, f"missing section: {heading}"))
    if re.search(r"^## (State Vocabulary|Health Vocabulary|Evidence Policy)\s*$", text, re.MULTILINE):
        findings.append(Finding("state-vocab-restated", backlog, "root policy must not be restated"))

    headers, rows = _table(_section(text, "Backlog"))
    if tuple(headers) != BACKLOG_COLUMNS:
        findings.append(Finding("backlog-columns", backlog, f"expected columns: {', '.join(BACKLOG_COLUMNS)}"))
        return findings
    prefixes: set[str] = set()
    frd_text = (backlog.parent / "FRD.md").read_text(encoding="utf-8")
    for row in rows:
        row_id = row["ID"]
        match = ID_RE.fullmatch(row_id)
        if not match:
            findings.append(Finding("invalid-backlog-id", backlog, f"invalid row ID: {row_id}"))
        else:
            prefixes.add(match.group(1))
        state = row["State"]
        if state not in states:
            findings.append(Finding("undefined-state-vocab", backlog, f"{row_id} uses unknown state: {state}"))
        ref = row["FRD Ref"]
        if FR_RE.fullmatch(ref) and ref not in frd_text:
            findings.append(Finding("orphan-fr-id", backlog, f"{row_id} cites absent {ref}"))
        if state in {"Done", "Released"}:
            evidence = row["Actual Condition"]
            if not COMMAND_RE.search(evidence) or not COMMIT_RE.search(evidence):
                findings.append(Finding("done-without-evidence", backlog, f"{row_id} needs a command and commit hash"))
    if len(prefixes) > 1:
        findings.append(Finding("mixed-id-scope", backlog, f"multiple ID prefixes: {', '.join(sorted(prefixes))}"))

    scenario_text = _section(text, "Scenario Evidence")
    scenario_source = _section(frd_text, "Test Scenarios / QA Checklist")
    for ref in sorted(set(re.findall(r"FR-\d{3}", scenario_source))):
        if ref not in scenario_text:
            findings.append(Finding("scenario-coverage", backlog, f"no scenario evidence for {ref}"))
    return findings


def check(root: Path) -> list[Finding]:
    root = root.resolve()
    features = _feature_dirs(root)
    findings = _check_pairing(root, features)
    states = _state_vocabulary(root / "ROADMAP.md")
    if not states:
        findings.append(Finding("undefined-state-vocab", root / "ROADMAP.md", "State Vocabulary table missing"))
    for feature in sorted(features):
        backlog = feature / "BACKLOG.md"
        if backlog.is_file():
            findings.extend(_check_backlog(backlog, states))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    findings = check(root)
    for finding in findings:
        print(finding.render(root))
    if findings:
        print(f"docs check failed: {len(findings)} finding(s)")
        return 1
    print("docs check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
