"""Unit tests: exception → structured error response mapping (issue #336)."""

from __future__ import annotations

from modules.core.src.utility_core_error_mapping import to_error_response
from modules.shared.src.taxonomy_core_error import AuthRequiredError, QwenCliError, RunCancelledError


class TestToErrorResponse:
    def test_auth_required_maps_to_stable_code(self) -> None:
        res = to_error_response(AuthRequiredError("login needed"))
        assert str(res).startswith("ERROR [AUTH_REQUIRED]:")

    def test_run_cancelled_maps_to_stable_code(self) -> None:
        res = to_error_response(RunCancelledError("stopped"))
        assert str(res).startswith("ERROR [RUN_CANCELLED]:")

    def test_subclass_keeps_stable_code(self) -> None:
        """A subclass must inherit the stable code (isinstance, not name compare)."""

        class HeadlessAuthChallenge(AuthRequiredError):
            pass

        res = to_error_response(HeadlessAuthChallenge("captcha wall"))
        assert str(res).startswith("ERROR [AUTH_REQUIRED]:")

    def test_unknown_error_falls_back_to_class_name(self) -> None:
        res = to_error_response(ValueError("boom"))
        assert str(res).startswith("ERROR [ValueError]:")

    def test_message_is_included(self) -> None:
        res = to_error_response(QwenCliError("pipeline blew up"))
        assert "pipeline blew up" in str(res)
