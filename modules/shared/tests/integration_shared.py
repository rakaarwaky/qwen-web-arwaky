"""Integration tests for shared module — tests modules working together."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from modules.shared.src import AppConfig, RunContext
from modules.shared.src.utility_core_path import list_input_files, should_process_file
from modules.shared.src.utility_core_prompt import extract_prompt_text


class TestSharedIntegration:
    """Integration tests for shared module components."""

    def test_config_with_run_context(self):
        cfg = AppConfig(base_url="http://test.com", timeout=30)
        ctx = RunContext(session_id="s1", config=cfg)
        assert ctx.config.base_url == "http://test.com"
        assert ctx.session_id == "s1"

    def test_prompt_extraction_with_file(self, tmp_path: Path):
        test_file = tmp_path / "prompt.md"
        test_file.write_text("---\ntitle: test\n---\nHello world", encoding="utf-8")
        content = test_file.read_text(encoding="utf-8")
        assert extract_prompt_text(content) == "Hello world"

    def test_file_filtering_integration(self, tmp_path: Path):
        (tmp_path / "doc1.md").write_text("content1")
        (tmp_path / "doc2.txt").write_text("content2")
        (tmp_path / "image.jpg").write_text("binary")
        files = list_input_files(tmp_path)
        assert len(files) == 2
        assert all(should_process_file(f.name) for f in files)

    def test_error_category_mapping(self):
        from modules.shared.src.taxonomy_core_error import ErrorCategory, QwenCliError
        err = QwenCliError("test error", category=ErrorCategory.BROWSER_ERROR)
        assert err.category == ErrorCategory.BROWSER_ERROR
        assert "BROWSER" in str(err)
