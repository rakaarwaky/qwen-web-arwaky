"""Unit tests for utility_response_normalizer functions."""

from __future__ import annotations

from modules.shared.src.common.utility_response_normalizer import (
    detect_processing_failure,
    safe_handle,
    success_response,
)


def test_detect_processing_failure_error_prefix():
    res = "ERROR [AUTH_REQUIRED]: Not authenticated to chat.qwen.ai"
    assert detect_processing_failure(res) == res


def test_detect_processing_failure_failed_count():
    res = "Processed 5 files. Failed: 2"
    assert detect_processing_failure(res) == res


def test_detect_processing_failure_clean_success():
    res = "Processed 5 files. Failed: 0"
    assert detect_processing_failure(res) is None


def test_detect_processing_failure_normal_text():
    res = "This is a normal assistant response text."
    assert detect_processing_failure(res) is None


def test_safe_handle_decorator():
    @safe_handle
    def ok_fn():
        return success_response("all good")

    @safe_handle
    def fail_fn():
        raise RuntimeError("something went wrong")

    assert ok_fn()["success"] is True
    assert fail_fn()["success"] is False
    assert "something went wrong" in str(fail_fn()["error"])


def test_exit_code_for_auth_required():
    from modules.root_cli_main_entry import _result_exit_code

    result = {
        "success": False,
        "error": "ERROR [AUTH_REQUIRED]: Not authenticated to chat.qwen.ai",
        "category": "processing_failed",
        "ref": "cli-422",
    }
    assert _result_exit_code(result) == 3


def test_exit_code_for_raised_auth_required_error():
    """A raised AuthRequiredError exits 3, leaving 2 to argparse (SA-3-02)."""
    from modules.shared.src.common.taxonomy_core_error import AuthRequiredError
    from modules.shared.src.common.utility_core_exit import exit_code_for

    assert exit_code_for(AuthRequiredError("Not authenticated to chat.qwen.ai")) == 3


def test_argparse_usage_error_exits_2():
    """argparse's usage signal stays deterministically 2 (SA-3-02)."""
    import pytest

    from modules.root_cli_main_entry import _parse_args

    with pytest.raises(SystemExit) as exc_info:
        _parse_args(["--definitely-not-a-real-flag"])

    assert exc_info.value.code == 2


def test_exit_code_for_generic_failure():
    from modules.root_cli_main_entry import _result_exit_code

    assert _result_exit_code({"success": False, "error": "boom"}) == 1


def test_json_output_prints_envelope():
    import io
    import json as json_lib
    from contextlib import redirect_stdout

    from modules.root_cli_main_entry import _result_exit_code

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = _result_exit_code({"success": True, "message": "all good"}, json_output=True)
    assert code == 0
    parsed = json_lib.loads(buf.getvalue())
    assert parsed["success"] is True
    assert parsed["message"] == "all good"
