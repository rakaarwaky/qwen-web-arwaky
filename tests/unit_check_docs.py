from __future__ import annotations

from pathlib import Path

from scripts.check_docs import check

REQUIRED_TAIL = """
## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| FR-001 scenario | Automated | tests/test_feature.py | test_feature | abc1234 |

## Blockers

None.

## Dependencies

None.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | command passed at abc1234 |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-09-24 | Created. | @test |
"""


def _write_valid_tree(root: Path, *, evidence: str = "`pytest -q` passed at `abc1234`") -> None:
    (root / "PRD.md").write_text("# PRD\n", encoding="utf-8")
    (root / "ROADMAP.md").write_text(
        """# Roadmap

## State Vocabulary

| State | Meaning |
|---|---|
| New | Recorded. |
| Ready | Refined. |
| In Progress | Active. |
| Blocked | Blocked. |
| Done | Verified. |
| Released | Shipped. |
""",
        encoding="utf-8",
    )
    feature = root / "modules" / "feature"
    feature.mkdir(parents=True)
    (feature / "agent_demo_orchestrator.py").write_text("", encoding="utf-8")
    (feature / "FRD.md").write_text(
        """# FRD

### FR-001: Demo

## Test Scenarios / QA Checklist

- [ ] FR-001: demo works.
""",
        encoding="utf-8",
    )
    backlog = f"""# Feature Backlog: Demo

FRD: [FRD.md](FRD.md)
State / Health: values from root ROADMAP.md.
Last Updated: 2026-09-24

## Current Condition

- Done: {evidence}.

## Backlog

| ID | FRD Ref | Work Item | Priority | State | Actual Condition | Owner | Dependencies | Updated |
|---|---|---|---:|---|---|---|---|---|
| DEMO-01 | FR-001 | Demo work. | P0 | Done | {evidence} | @test | None | 2026-09-24 |
{REQUIRED_TAIL}
"""
    padding = "\n".join(f"<!-- padding {index} -->" for index in range(20))
    (feature / "BACKLOG.md").write_text(backlog + padding + "\n", encoding="utf-8")


def test_repository_documentation_contract_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    assert check(root) == []


def test_non_feature_frd_is_rejected(tmp_path: Path) -> None:
    _write_valid_tree(tmp_path)
    shared = tmp_path / "modules" / "shared"
    shared.mkdir()
    (shared / "FRD.md").write_text("# Invalid\n", encoding="utf-8")

    assert "feature-doc-in-shared" in {finding.code for finding in check(tmp_path)}


def test_done_row_requires_command_and_commit(tmp_path: Path) -> None:
    _write_valid_tree(tmp_path, evidence="implemented")

    assert "done-without-evidence" in {finding.code for finding in check(tmp_path)}


def test_feature_docs_must_be_paired(tmp_path: Path) -> None:
    _write_valid_tree(tmp_path)
    (tmp_path / "modules" / "feature" / "BACKLOG.md").unlink()

    assert "spec-without-backlog" in {finding.code for finding in check(tmp_path)}
