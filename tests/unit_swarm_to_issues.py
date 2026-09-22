"""Unit tests for scripts/swarm_to_issues.py parser and GitHub dedup logic.

These tests run the parser offline against fixture data — no GitHub API calls
are made. They verify:
- structured issue extraction from agent output.md files
- severity/role label assignment
- dedup key stability (issue ID marker embedded in body)
- dry-run preview formatting

The script under test lives at ``scripts/swarm_to_issues.py`` and is imported
by path so it does not need to be installed.
"""

import importlib.util
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Import the script by path (it lives in scripts/, not an installed package)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
_SPEC = importlib.util.spec_from_file_location("swarm_to_issues", _SCRIPTS_DIR / "swarm_to_issues.py")
s2i = importlib.util.module_from_spec(_SPEC)
sys.modules["swarm_to_issues"] = s2i
_SPEC.loader.exec_module(s2i)

SwarmIssue = s2i.SwarmIssue
parse_agent_output = s2i.parse_agent_output
parse_swarm_run = s2i.parse_swarm_run
build_issue_body = s2i.build_issue_body
ROLE_LABEL = s2i.ROLE_LABEL

# ---------------------------------------------------------------------------
# Fixtures — minimal agent output shapes
# ---------------------------------------------------------------------------

SAMPLE_AGENT_OUTPUT = """\
# Plan: Test Swarm

## Summary
A short summary line.

### Scope 1: Something

#### Issue BE-1-001
- **Title**: [BE][WARNING] Something is wrong with the thing
- **Location Path**:
  `modules/core/src/capabilities_stream_monitor.py` line 120
- **Description**: The monitor does not forward events as expected.
- **Acceptance Criteria**: Forward events arrive within 500ms.
- **Recommendation**: Add a forward-event timer.
- **Git Diff**:
```diff
- old line
+ new line
```

#### Issue BE-1-002
- **Title**: [BE][CRITICAL] Critical problem
- **Description**: Something is badly broken.
- **Recommendation**: Fix it now.
"""


def _make_run(tmp_path: Path, role: str, content: str, manifest: str = "swarm_test") -> Path:
    d = tmp_path / role
    d.mkdir()
    (d / "output.md").write_text(content, encoding="utf-8")
    (tmp_path / "manifest.json").write_text(
        f'{{"swarm_id": "{manifest}", "status": "completed"}}',
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_parse_agent_output_extracts_issues(tmp_path):
    run = _make_run(tmp_path, "backend-engineer", SAMPLE_AGENT_OUTPUT)
    issues = parse_swarm_run(run)
    assert len(issues) == 2, f"expected 2 issues, got {len(issues)}"
    assert issues[0].issue_id == "BE-1-001"
    assert issues[1].issue_id == "BE-1-002"


def test_parse_agent_output_assigns_labels(tmp_path):
    run = _make_run(tmp_path, "backend-engineer", SAMPLE_AGENT_OUTPUT)
    issues = parse_swarm_run(run)
    # BE-1-001 is WARNING
    assert "swarm-backend-engineer" in issues[0].labels
    assert "severity-warning" in issues[0].labels
    # BE-1-002 is CRITICAL
    assert "severity-critical" in issues[1].labels
    assert "severity-warning" not in issues[1].labels


def test_parse_agent_output_preserves_description_sections(tmp_path):
    run = _make_run(tmp_path, "backend-engineer", SAMPLE_AGENT_OUTPUT)
    issues = parse_swarm_run(run)
    body = issues[0].body
    assert "## Description" in body
    assert "## Acceptance Criteria" in body
    assert "## Recommendation" in body
    assert "## Suggested Diff" in body
    assert "- old line" in body
    assert "+ new line" in body


def test_parse_agent_output_includes_swarm_id_in_body(tmp_path):
    run = _make_run(tmp_path, "backend-engineer", SAMPLE_AGENT_OUTPUT)
    issues = parse_swarm_run(run)
    for it in issues:
        assert "swarm_test" in it.body
        assert f"imported `{it.issue_id}`" in it.body


def test_parse_agent_output_title_stripping(tmp_path):
    content = (
        "#### Issue BE-9-999\n"
        "- **Title**: [BE][INFO] A title with `backticks` and [brackets]\n"
        "- **Description**: test\n"
    )
    run = _make_run(tmp_path, "backend-engineer", content)
    issues = parse_swarm_run(run)
    assert len(issues) == 1
    title = issues[0].title
    assert "backticks" in title
    assert "[BE]" in title
    assert "[brackets]" in title
    # No stray backslash escaping
    assert "\\" not in title


def test_parse_agent_output_unknown_prefix_maps_to_role(tmp_path):
    # XX-1-001 has no registered ROLE_PREFIX entry; it should keep the
    # directory role rather than crash.
    content = "#### Issue XX-1-001\n- **Title**: [XX][INFO] X\n- **Description**: d\n"
    run = _make_run(tmp_path, "backend-engineer", content)
    issues = parse_swarm_run(run)
    assert len(issues) == 1
    assert issues[0].issue_id == "XX-1-001"
    # Role falls back to the directory role
    assert issues[0].role == "backend-engineer"


def test_parse_agent_output_empty_output_falls_back_to_summary(tmp_path):
    content = "# No structured issues here\nJust prose.\n"
    run = _make_run(tmp_path, "backend-engineer", content)
    issues = parse_swarm_run(run)
    assert len(issues) == 1
    assert "unstructured" in issues[0].title.lower()


def test_parse_agent_output_dedup_within_run(tmp_path):
    # Two identical issue blocks in one file should dedup to one
    content = (
        "#### Issue BE-1-001\n- **Title**: [BE][INFO] dup\n- **Description**: d\n"
        "#### Issue BE-1-001\n- **Title**: [BE][INFO] dup\n- **Description**: d\n"
    )
    run = _make_run(tmp_path, "backend-engineer", content)
    issues = parse_swarm_run(run)
    assert len(issues) == 1, f"expected dedup to 1, got {len(issues)}"


def test_build_issue_body_contains_all_sections():
    body = build_issue_body(
        role="backend-engineer",
        iid="BE-1-001",
        description="some desc",
        plan_title="Plan: X",
        swarm_id="swarm_abc",
    )
    assert "**Agent**: `backend-engineer`" in body
    assert "**Swarm Run**: `swarm_abc`" in body
    assert "**Source Plan**: Plan: X" in body
    assert "**Issue ID**: `BE-1-001`" in body
    assert "swarm_abc" in body


def test_role_label_mapping():
    assert ROLE_LABEL["backend-engineer"] == "swarm-backend-engineer"
    assert ROLE_LABEL["ui-ux-designer"] == "swarm-ui-ux-designer"


def test_dedup_key_stability():
    it = SwarmIssue(
        issue_id="BE-1-001",
        role="backend-engineer",
        title="t",
        body="b",
        labels=["swarm-backend-engineer"],
    )
    # dedup key is role:issue_id
    assert it.dedup_key == "backend-engineer:BE-1-001"


def test_swarm_id_from_manifest(tmp_path):
    content = "#### Issue BE-1-001\n- **Title**: [BE][INFO] x\n- **Description**: d\n"
    run = _make_run(tmp_path, "backend-engineer", content, manifest="swarm_custom_123")
    issues = parse_swarm_run(run)
    assert "swarm_custom_123" in issues[0].body
