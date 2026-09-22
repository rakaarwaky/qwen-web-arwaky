"""Regression tests for pipeline core functions — path resolution, input stripping, file filtering."""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.utility_core_path import (
    list_input_files as _list_input_files,
)
from modules.shared.src.utility_core_path import (
    should_process_file as _should_process_file,
)
from modules.shared.src.utility_core_prompt import (
    extract_prompt_text as _extract_prompt_text,
)
from modules.shared.src.utility_core_prompt import (
    strip_input_from_output as _strip_input_from_output,
)

# ─── _extract_prompt_text ───────────────────────────────────────────────────


class TestExtractPromptText:
    def test_no_frontmatter(self):
        assert _extract_prompt_text("Hello world") == "Hello world"

    def test_with_frontmatter(self):
        content = "---\ntitle: test\n---\nActual prompt here"
        assert _extract_prompt_text(content) == "Actual prompt here"

    def test_empty_content(self):
        assert _extract_prompt_text("") == ""

    def test_only_frontmatter_no_body(self):
        content = "---\ntitle: test\n---"
        assert _extract_prompt_text(content) == ""

    def test_frontmatter_with_surrounding_whitespace(self):
        content = "  ---\nkey: val\n---\n  Prompt text  "
        assert _extract_prompt_text(content) == "Prompt text"

    def test_single_dash_not_frontmatter(self):
        content = "- not frontmatter"
        assert _extract_prompt_text(content) == "- not frontmatter"

    def test_unclosed_frontmatter_treated_as_body(self):
        content = "---\nonly one dash pair\n"
        assert _extract_prompt_text(content) == content.strip()

    def test_multiline_prompt_after_frontmatter(self):
        content = "---\ntitle: task\n---\nLine 1\nLine 2\nLine 3"
        result = _extract_prompt_text(content)
        assert "Line 1" in result
        assert "Line 3" in result


# ─── _strip_input_from_output ───────────────────────────────────────────────


class TestStripInputFromOutput:
    def test_no_leak(self):
        text = "AI response text here"
        prompt = "user prompt"
        assert _strip_input_from_output(text, prompt) == text

    def test_prefix_leak_stripped(self):
        prompt = "Explain quantum computing"
        text = "Explain quantum computing\n\nQuantum computing is..."
        result = _strip_input_from_output(text, prompt)
        assert "Quantum computing is" in result
        assert "Explain quantum computing" not in result

    def test_empty_text_returns_empty(self):
        assert _strip_input_from_output("", "prompt") == ""
        assert _strip_input_from_output(None, "prompt") is None

    def test_empty_prompt_returns_text(self):
        assert _strip_input_from_output("text", "") == "text"
        assert _strip_input_from_output("text", None) == "text"

    def test_no_strip_when_candidate_too_short(self):
        prompt = "A" * 100
        text = prompt + "\nHi"
        result = _strip_input_from_output(text, prompt)
        assert result == text  # candidate "Hi" < 20 chars, no strip

    def test_line_matching_filter(self):
        lines = [f"Prompt line {i}" for i in range(10)]
        response_line = "This is the actual AI response"
        full_text = "\n".join(lines[:5]) + "\n" + response_line + "\n" + "\n".join(lines[5:])
        full_prompt = "\n".join(lines)
        result = _strip_input_from_output(full_text, full_prompt)
        assert response_line in result

    def test_whitespace_only_leak_not_stripped(self):
        prompt = "test prompt with enough chars"
        text = prompt + "\n   "
        result = _strip_input_from_output(text, prompt)
        assert result == text


# ─── _should_process_file ──────────────────────────────────────────────────


class TestShouldProcessFile:
    def test_valid_file(self, tmp_path):
        f = tmp_path / "role-architect" / "todo" / "task.md"
        f.parent.mkdir(parents=True)
        f.write_text("content")
        assert _should_process_file(f, tmp_path) is True

    def test_hidden_file_skipped(self, tmp_path):
        f = tmp_path / "role-architect" / "todo" / ".hidden.md"
        f.parent.mkdir(parents=True)
        f.write_text("content")
        assert _should_process_file(f, tmp_path) is False

    def test_prompt_md_skipped(self, tmp_path):
        f = tmp_path / "role-architect" / "todo" / "PROMPT.md"
        f.parent.mkdir(parents=True)
        f.write_text("content")
        assert _should_process_file(f, tmp_path) is False

    def test_not_role_prefix_skipped(self, tmp_path):
        f = tmp_path / "other-dir" / "task.md"
        f.parent.mkdir(parents=True)
        f.write_text("content")
        assert _should_process_file(f, tmp_path) is False

    def test_direct_file_not_in_role_skipped(self, tmp_path):
        f = tmp_path / "task.md"
        f.write_text("content")
        assert _should_process_file(f, tmp_path) is False

    def test_directory_returns_false(self, tmp_path):
        d = tmp_path / "role-architect" / "todo"
        d.mkdir(parents=True)
        assert _should_process_file(d, tmp_path) is False

    def test_dotfile_in_role_dir_skipped(self, tmp_path):
        f = tmp_path / "role-architect" / ".config"
        f.parent.mkdir(parents=True)
        f.write_text("content")
        assert _should_process_file(f, tmp_path) is False


# ─── _list_input_files ─────────────────────────────────────────────────────


class TestListInputFiles:
    def test_returns_valid_files(self, tmp_path):
        f = tmp_path / "role-dev" / "todo" / "a.md"
        f.parent.mkdir(parents=True)
        f.write_text("a")
        files = _list_input_files(tmp_path)
        assert len(files) == 1
        assert files[0][1] == Path("role-dev/todo/a.md")

    def test_excludes_prompt_md(self, tmp_path):
        f = tmp_path / "role-dev" / "todo" / "PROMPT.md"
        f.parent.mkdir(parents=True)
        f.write_text("prompt")
        assert _list_input_files(tmp_path) == []

    def test_excludes_hidden_files(self, tmp_path):
        f = tmp_path / "role-dev" / "todo" / ".env"
        f.parent.mkdir(parents=True)
        f.write_text("secret")
        assert _list_input_files(tmp_path) == []

    def test_empty_dir(self, tmp_path):
        assert _list_input_files(tmp_path) == []

    def test_nonexistent_dir(self, tmp_path):
        assert _list_input_files(tmp_path / "nonexistent") == []

    def test_multiple_roles(self, tmp_path):
        for role in ["role-dev", "role-design"]:
            f = tmp_path / role / "todo" / "task.md"
            f.parent.mkdir(parents=True)
            f.write_text("task")
        files = _list_input_files(tmp_path)
        assert len(files) == 2
