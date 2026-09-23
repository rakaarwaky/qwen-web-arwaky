"""Unit tests for utility_core_response functions."""

from __future__ import annotations

from modules.shared.src.utility_core_response import (
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
    assert _result_exit_code(result) == 2


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
