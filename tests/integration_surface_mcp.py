"""Unit test suite for MCP server tools and configuration."""

import asyncio
import unittest
from unittest.mock import MagicMock, patch

import pytest

from modules.mcp.src.surface_mcp_tool_command import McpToolCommand
from modules.root_mcp_main_entry import (
    check_session,
    delete_session,
    process_direct_prompt,
    process_prompt_file_only,
    setup_session,
)


@pytest.fixture(autouse=True)
def _reset_event_loop():
    """Reset asyncio event loop before each test to avoid Playwright contamination."""
    try:
        if hasattr(asyncio, "_set_running_loop"):
            asyncio._set_running_loop(None)
    except Exception:
        pass
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception:
        pass
    yield


class TestMCPServerTools(unittest.TestCase):
    """Unit tests for MCP server tools."""

    def test_process_direct_prompt_mock(self) -> None:
        """Test process_direct_prompt tool execution with mocked tools."""
        mock_tools = MagicMock()
        mock_tools.process_direct_prompt.return_value = '{"success": true, "result": "Mocked AI Response"}'
        with patch("modules.root_mcp_main_entry._get_tools", return_value=mock_tools):
            result = asyncio.run(process_direct_prompt("Hello Qwen", timeout_sec=30, headless=True))
            self.assertIn("Mocked AI Response", result)

    def test_process_prompt_file_only_success(self) -> None:
        """Test process_prompt_file_only with valid file input."""
        mock_tools = MagicMock()
        mock_tools.process_prompt_file_only.return_value = (
            '{"success": true, "result": "Successfully processed prompt.md"}'
        )
        with patch("modules.root_mcp_main_entry._get_tools", return_value=mock_tools):
            res = asyncio.run(process_prompt_file_only("/tmp/prompt.md", "/tmp/output.md"))
            self.assertIn("Successfully processed", res)

    def test_setup_session(self) -> None:
        """Test setup_session manual login trigger."""
        mock_tools = MagicMock()
        mock_tools.setup_session.return_value = '{"success": true, "result": "Browser session saved to x"}'
        with patch("modules.root_mcp_main_entry._get_tools", return_value=mock_tools):
            res = asyncio.run(setup_session())
            self.assertIn("Browser session saved", res)

    def test_check_session(self) -> None:
        """Test check_session status query."""
        mock_tools = MagicMock()
        mock_tools.check_session.return_value = '{"success": true, "session_valid": true}'
        with patch("modules.root_mcp_main_entry._get_tools", return_value=mock_tools):
            res = asyncio.run(check_session())
            self.assertIn("session_valid", res)

    def test_delete_session(self) -> None:
        """Test delete_session with confirmation."""
        mock_tools = MagicMock()
        mock_tools.delete_session.return_value = '{"success": true, "message": "Saved browser session tokens deleted"}'
        with patch("modules.root_mcp_main_entry._get_tools", return_value=mock_tools):
            res = asyncio.run(delete_session(confirm=True))
            self.assertIn("deleted", res)

    def test_process_prompt_file_only_async(self) -> None:
        """Test process_prompt_file_only returns queued job in async mode."""
        mock_tools = MagicMock()
        mock_tools.process_prompt_file_only.return_value = (
            '{"success": true, "latest_event": "EVENT_DISPATCH_ACKNOWLEDGED", "job_id": "file_123"}'
        )
        with patch("modules.root_mcp_main_entry._get_tools", return_value=mock_tools):
            res = asyncio.run(process_prompt_file_only("/tmp/prompt.md", "/tmp/output.md", async_run=True))
            self.assertIn("EVENT_DISPATCH_ACKNOWLEDGED", res)
            self.assertIn("file_123", res)

    def test_get_job_status(self) -> None:
        """Test get_job_status tool execution."""
        from modules.root_mcp_main_entry import get_job_status

        mock_tools = MagicMock()
        mock_tools.get_job_status.return_value = (
            '{"success": true, "job_id": "file_123", "latest_event": "EVENT_GENERATION_FINISHED", "completed": true}'
        )
        with patch("modules.root_mcp_main_entry._get_tools", return_value=mock_tools):
            res = asyncio.run(get_job_status("file_123"))
            self.assertIn("EVENT_GENERATION_FINISHED", res)

    def test_list_jobs(self) -> None:
        """Test list_jobs tool execution."""
        from modules.root_mcp_main_entry import list_jobs

        mock_tools = MagicMock()
        mock_tools.list_jobs.return_value = '{"success": true, "total": 1, "jobs": [{"job_id": "file_123"}]}'
        with patch("modules.root_mcp_main_entry._get_tools", return_value=mock_tools):
            res = asyncio.run(list_jobs(limit=5))
            self.assertIn("file_123", res)

    def test_process_direct_prompt_empty_validation(self) -> None:
        """Test process_direct_prompt rejects empty prompt text."""
        cmd = McpToolCommand(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        res = cmd.process_direct_prompt("")
        self.assertIn("VALIDATION_ERROR", res)


if __name__ == "__main__":
    unittest.main()
