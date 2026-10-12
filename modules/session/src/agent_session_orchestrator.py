"""Agent: session orchestrator (AES405).

Orchestrates session validation, deletion, and interactive manual login
using browser protocol. The single agent in the session feature folder;
it implements both the session aggregate (validate/delete) and the setup
aggregate (login) so a surface holds one object for the whole feature.

When session validation fails, the orchestrator attempts a transparent
renewal via :class:`SessionRenewer` before reporting the session as
invalid, so operators do not need to re-login while the refresh token
is still valid.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from modules.shared.src.contract_browser_protocol import IBrowserProtocol
from modules.shared.src.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.contract_session_aggregate import ISessionAggregate
from modules.shared.src.contract_session_protocol import (
    ISessionManagerProtocol,
    ISessionRenewalProtocol,
)
from modules.shared.src.contract_setup_aggregate import ISetupAggregate
from modules.shared.src.taxonomy_core_constant import CHAT_URL, DEFAULT_OUTPUT, SESSIONS_DIR
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_error import QwenCliError
from modules.shared.src.taxonomy_core_vo import AppConfig
from modules.shared.src.taxonomy_session_vo import (
    SessionRequest,
    SessionResponse,
)
from modules.shared.src.taxonomy_setup_vo import SetupRequest, SetupResponse
from modules.shared.src.utility_config_app_factory import build_app_config
from modules.shared.src.utility_core_session_backup import take_snapshot


class SessionOrchestrator(ISessionAggregate, ISetupAggregate):
    """Orchestrates Qwen session checking, deletion, and manual login.

    Implements :class:`ISessionAggregate` (``execute``) and
    :class:`ISetupAggregate` (``execute_setup``). The two contracts use
    different method names so both can be satisfied without a signature
    conflict.
    """

    def __init__(
        self,
        browser: IBrowserProtocol,
        observability: IObservabilityProtocol,
        sessions: ISessionManagerProtocol | None = None,
        renewer: ISessionRenewalProtocol | None = None,
    ) -> None:
        self._browser = browser
        self._observability = observability
        self._sessions = sessions
        self._renewer = renewer

    # Block 2: Protocol Method Implementation

    def execute(self, request: SessionRequest) -> SessionResponse:
        """Run the requested session verb and return its outcome.

        Routes on ``request.verb``: ``validate`` runs the headless auth
        check and returns the verdict; ``delete`` runs the path-safety
        guard then removes the profile; ``login`` mirrors the setup flow
        via the session-verb spelling. All I/O is delegated to the browser
        capability — this agent only routes and wraps results.
        """
        if request.verb == "validate":
            valid, message = self._validate(request.session_path)
            return SessionResponse(valid=valid, message=message)
        if request.verb == "delete":
            message = self._delete(request.session_path, force=request.force)
            return SessionResponse(deleted=True, message=message)
        if request.verb == "login":
            outcome = self._login(request.session_path, request.name)
            error_val: str | None = outcome["error"] if isinstance(outcome["error"], str) else None
            return SessionResponse(
                valid=bool(outcome["success"]),
                message=str(outcome["message"] or outcome["error"] or ""),
                error=error_val,
            )
        return SessionResponse(error=f"unknown session verb: {request.verb!r}")

    def execute_setup(self, request: SetupRequest) -> SetupResponse:
        """Run the interactive manual-login flow (setup aggregate entry point).

        This method matches the :class:`ISetupAggregate` interface so that
        consumers holding an ``ISetupAggregate`` reference can call it via
        a duck-typed or cast adapter. ``SessionOrchestrator`` intentionally
        does not inherit from ``ISetupAggregate`` because the two aggregate
        contracts declare conflicting ``execute`` signatures; this separate
        method keeps both paths type-safe.
        """
        return self._login_from_setup_request(request)

    # Block 3: Dunder Methods, Factories, Helpers

    def setup_session(
        self,
        wait_for_confirmation: Callable[[], bool] | None = None,
        session_path: Path | None = None,
    ) -> str:
        """Return the login outcome as text, delegating to :meth:`execute`.

        Thin convenience wrapper over the setup flow so callers that only
        need a string verdict do not have to build a ``SetupRequest``
        themselves.
        """
        response = self._login_from_setup_request(
            SetupRequest(
                profile_path=session_path,
                wait_for_confirmation=wait_for_confirmation,
            )
        )
        return str(response.error or response.message or response.profile_path or "")

    def _login_from_setup_request(self, request: SetupRequest) -> SetupResponse:
        """Run the interactive manual-login flow from a ``SetupRequest``.

        Resolves the profile path (``profile_path`` when set, otherwise
        ``SESSIONS_DIR / name``), then opens a **headed browser** (the
        ``login`` verb is the explicit (re)authentication flow and must always
        show a window — the headless "already valid" fast-path belongs to the
        ``validate``/``check``/``health`` verbs, not here), navigates to
        chat.qwen.ai, and waits for the browser to close or the confirmation
        callback to fire.  On success the profile is snapshotted and
        registered in the session pool so rotation and ``session list`` see it.
        """
        profile_path = request.profile_path
        if profile_path is None:
            profile_path = SESSIONS_DIR / request.name

        # Manual login requires a visible browser window (AES205: the user
        # types credentials, so a hidden browser makes no sense). Force
        # headless=False unconditionally regardless of the flag value passed
        # by the caller.
        cfg = build_app_config(
            mode="login",
            input_path=DEFAULT_OUTPUT,
            output_path=DEFAULT_OUTPUT,
            session_path=profile_path,
            headless=False,
        )

        # The ``login`` verb is the user explicitly asking to (re)authenticate,
        # so it must always open a visible browser window.  The headless
        # "Session already valid." fast-path belongs to the ``validate`` /
        # ``check`` / ``health`` verbs, not to ``login``.  Silently skipping
        # the browser because a warm cookie is still present would make
        # ``qwa session login`` unable to switch accounts or re-login — and on
        # a second run for the same profile name it would never show the
        # browser window the operator expects.  Drop the fast-path entirely;
        # the post-login ``_validate_saved_session`` call below still
        # confirms the result.
        with self._browser.browser_session(cfg) as bctx:
            page = bctx.pages[0] if bctx.pages else bctx.new_page()
            page.goto(CHAT_URL, wait_until="domcontentloaded")

            deadline = time.monotonic() + cfg.timeout
            while True:
                try:
                    if page.is_closed():
                        break
                except Exception:
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    # Ask the caller (e.g. the TUI worker) whether the manual
                    # login is complete. When it returns True we break out of
                    # the loop; when it returns False we keep waiting.
                    # ``wait_for_confirmation`` is a zero-arg callable that
                    # returns a bool — a simple sentinel for the TUI flow.
                    if request.wait_for_confirmation is not None and request.wait_for_confirmation():
                        break
                    sleep_ms = min(500, max(100, int(remaining * 1000)))
                    page.wait_for_timeout(sleep_ms)
                except Exception:
                    break

        if self._validate_saved_session(cfg):
            try:
                take_snapshot(cfg.session_path)
            except Exception as exc:
                self._observability.get_logger().warning(
                    "session_backup_failed", error=str(exc), session_path=str(cfg.session_path)
                )
            # Register the profile in the session pool so rotation and
            # ``session list`` can see it. add_session is idempotent: when
            # the profile is already in the pool the existing entry is
            # updated in place rather than duplicated.
            if self._sessions is not None:
                try:
                    self._sessions.add_session(request.name, cfg.session_path)
                except Exception as exc:
                    self._observability.get_logger().warning(
                        "session_pool_register_failed", error=str(exc), session_path=str(cfg.session_path)
                    )
            return SetupResponse(
                success=True,
                profile_path=str(cfg.session_path),
                message="Manual login completed successfully.",
            )

        return SetupResponse(
            error=(
                "Manual login did not produce a valid Qwen session. "
                "Please run 'qwen-web-arwaky --login' again and finish the login or CAPTCHA."
            ),
        )

    def _login(
        self,
        session_path: Path | None,
        name: str,
        wait_for_confirmation: Callable[[], bool] | None = None,
    ) -> dict[str, object]:
        """Run the login flow from a ``login`` session verb.

        Same interactive flow as the setup entry point, returning the
        result in the dict shape the session-verb route in
        :meth:`execute` wraps into a ``SessionResponse``.
        """
        response = self._login_from_setup_request(
            SetupRequest(
                profile_path=session_path,
                name=name,
                wait_for_confirmation=wait_for_confirmation,
            )
        )
        return {
            "success": response.success,
            "message": str(response.message or ""),
            "error": response.error,
            "profile_path": str(response.profile_path or ""),
        }

    def _validate(self, session_path: Path | None) -> tuple[bool, str]:
        """Validate an existing saved Qwen browser session in headless mode.

        Runs the browser check first; on failure attempts a transparent
        token renewal so the user does not have to re-login while the
        ``refresh_token`` is still valid. When both the session and the
        refresh token are dead, raises ``AuthRequiredError`` so the
        caller can surface the actionable message.
        """
        cfg = build_app_config(
            mode="session-check",
            input_path=DEFAULT_OUTPUT,
            output_path=DEFAULT_OUTPUT,
            session_path=session_path,
            headless=True,
        )
        if not cfg.session_path.is_dir():
            return False, "Session not found. Please log in first."
        if self._validate_saved_session(cfg):
            return True, "Saved Qwen session is valid and ready to use."
        return False, "Saved Qwen session is invalid or expired. Please log in again."

    def _delete(self, session_path: Path | None, *, force: bool) -> str:
        """Delete the saved Chromium profile for *session_path*.

        Every safety rule lives in the session manager that owns the profile
        on disk: the target must be an existing directory that clears
        ``is_safe_session_target`` (never a filesystem root, a near-root path
        such as ``/etc``, or a path outside the allow-list), and deletion is
        refused while no backup generation is retained unless the caller passes
        ``force=True`` (issue #300).
        """
        cfg = build_app_config(
            mode="session-check",
            input_path=DEFAULT_OUTPUT,
            output_path=DEFAULT_OUTPUT,
            session_path=session_path,
            headless=True,
        )
        if self._sessions is None:
            raise QwenCliError("Session manager not available for delete")
        delete_profile = self._sessions.delete_session_profile
        delete_profile(cfg.session_path, force=force)
        return "Session deleted successfully."

    def _validate_saved_session(self, cfg: AppConfig) -> bool:
        """Check an existing profile without opening a visible login window.

        When the initial browser probe fails, attempts a transparent token
        renewal via the browser self-heal path before giving up.
        """
        validation_cfg = build_app_config(
            mode="session-check",
            input_path=DEFAULT_OUTPUT,
            output_path=DEFAULT_OUTPUT,
            session_path=cfg.session_path,
            headless=True,
        )
        try:
            with self._browser.browser_session(validation_cfg) as bctx:
                page = bctx.pages[0] if bctx.pages else bctx.new_page()
                emitter = LifecycleEmitter(self._observability.get_logger())
                self._browser.navigate_to_chat(page, emitter)
                if self._browser.check_session(page):
                    return True
        except Exception:
            # Validation is a best-effort fast path: when the headless
            # probe cannot launch (missing browser binary, sandbox failure,
            # or CDP crash), it must not poison the manual login that
            # follows.  Log the detail and fall through so the caller can
            # still open the visible login window.
            log_debug = self._observability.get_logger().debug
            log_debug("saved_session_validation_failed")

        # Initial check failed — attempt a transparent renewal before reporting
        # the session as invalid.
        if self._renewer is not None:
            try:
                self._renewer.renew_session_if_stale(validation_cfg)
                # Re-validate after renewal succeeded
                with self._browser.browser_session(validation_cfg) as bctx:
                    page = bctx.pages[0] if bctx.pages else bctx.new_page()
                    emitter = LifecycleEmitter(self._observability.get_logger())
                    self._browser.navigate_to_chat(page, emitter)
                    if self._browser.check_session(page):
                        return True
            except QwenCliError:
                # AuthRequiredError or other auth failures: renewal impossible,
                # fall through to report the session as invalid.
                pass
            except Exception:
                # Any other failure during renewal: report invalid, don't crash.
                pass
        return False


__all__ = ["SessionOrchestrator"]
