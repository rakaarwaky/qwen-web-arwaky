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

from modules.shared.src.browser.contract_browser_protocol import IBrowserProtocol
from modules.shared.src.common.taxonomy_core_constant import CHAT_URL, DEFAULT_OUTPUT, SESSIONS_DIR
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_error import QwenCliError
from modules.shared.src.common.taxonomy_core_vo import AppConfig
from modules.shared.src.common.utility_core_session_backup import take_snapshot
from modules.shared.src.config.utility_config_app_factory import build_app_config
from modules.shared.src.logging.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.session.contract_session_aggregate import ISessionAggregate
from modules.shared.src.session.contract_session_protocol import (
    ISessionHealthCheckerProtocol,
    ISessionManagerProtocol,
    ISessionRenewalProtocol,
)
from modules.shared.src.session.taxonomy_session_vo import (
    SessionList,
    SessionRequest,
    SessionResponse,
)


class SessionOrchestrator(ISessionAggregate):
    """Orchestrates Qwen session checking, deletion, and manual login.

    Implements :class:`ISessionAggregate` (``execute``) for all three verbs:
    ``validate``, ``delete``, and ``login``. The ``login`` verb is the
    interactive manual-authentication flow; consumers call it via
    ``SessionRequest(verb="login", ...)`` on the single session aggregate
    seam.
    """

    def __init__(
        self,
        browser: IBrowserProtocol,
        observability: IObservabilityProtocol,
        sessions: ISessionManagerProtocol | None = None,
        renewer: ISessionRenewalProtocol | None = None,
        health_checker: ISessionHealthCheckerProtocol | None = None,
    ) -> None:
        self._browser = browser
        self._observability = observability
        self._sessions = sessions
        self._renewer = renewer
        self._health_checker = health_checker

    # Block 2: Protocol Method Implementation

    def execute(self, request: SessionRequest) -> SessionResponse:
        """Run the requested session verb and return its outcome.

        Routes on ``request.verb``: ``validate`` runs the headless auth
        check and returns the verdict; ``delete`` runs the path-safety
        guard then removes the profile; ``login`` mirrors the setup flow
        via the session-verb spelling; ``list_sessions`` returns the whole
        pool in pool order; ``remove_session`` drops one pool entry by
        path or name. All I/O is delegated to the capability seams —
        this agent only routes and wraps results.
        """
        if request.verb == "validate":
            valid, message = self._validate(request.session_path)
            return SessionResponse(valid=valid, message=message)
        if request.verb == "delete":
            message = self._delete(request.session_path, force=request.force)
            return SessionResponse(deleted=True, message=message)
        if request.verb == "login":
            outcome = self._login(
                request.session_path,
                request.name,
                wait_for_confirmation=request.wait_for_confirmation,
            )
            error_val: str | None = outcome["error"] if isinstance(outcome["error"], str) else None
            profile_val = outcome.get("profile_path")
            profile_val_typed: Path | str | None = profile_val if isinstance(profile_val, (Path, str)) else None
            return SessionResponse(
                valid=bool(outcome["success"]),
                message=str(outcome["message"] or outcome["error"] or ""),
                error=error_val,
                profile_path=profile_val_typed,
            )
        if request.verb == "list_sessions":
            pool = self._sessions.load_pool() if self._sessions is not None else None
            sessions = list(pool.sessions) if pool is not None else []
            return SessionResponse(sessions=SessionList(sessions), message=f"{len(sessions)} session(s)")
        if request.verb == "remove_session":
            if self._sessions is None:
                return SessionResponse(error="no session pool available")
            found = self._sessions.get_session_by_name(request.name) if request.name else None
            if found is None:
                return SessionResponse(error="session not found", removed=False)
            if not self._sessions.remove_session(found.session_id):
                return SessionResponse(error="could not remove session from pool", removed=False)
            return SessionResponse(
                removed=True,
                message=f"removed {found.name} ({found.session_id})",
                profile_path=found.path,
            )
        if request.verb == "check_health":
            if self._sessions is None or self._health_checker is None:
                return SessionResponse(error="session health checker not wired")
            pool = self._sessions.load_pool()
            results = self._health_checker.check_pool_sync(pool, self._sessions)
            healthy_count, total = self._health_checker.summarize_pool_results(results)
            return SessionResponse(
                message=f"{healthy_count}/{total} session(s) healthy",
                health_healthy=healthy_count,
                health_total=total,
            )
        return SessionResponse(error=f"unknown session verb: {request.verb!r}")

    def setup_session(
        self,
        wait_for_confirmation: Callable[[], bool] | None = None,
        session_path: Path | None = None,
    ) -> str:
        """Return the login outcome as text, delegating to the ``login`` verb.

        Thin convenience wrapper over the manual-login flow so callers that
        only need a string verdict do not have to build a ``SessionRequest``
        themselves. On failure the message and error are reported together,
        matching the setup flow's single-sentence guidance.
        """
        response = self.execute(
            SessionRequest(
                verb="login",
                session_path=session_path,
                wait_for_confirmation=wait_for_confirmation,
            )
        )
        if response.error is not None:
            return str(f"{response.message} {response.error}" if response.message else response.error)
        return str(response.message or response.profile_path or "")

    # Block 3: Dunder Methods, Factories, Helpers

    def _login(
        self,
        session_path: Path | None,
        name: str,
        wait_for_confirmation: Callable[[], bool] | None = None,
    ) -> dict[str, object]:
        """Run the interactive manual-login flow for the ``login`` session verb.

        Resolves the profile path (``session_path`` when set, otherwise
        ``SESSIONS_DIR / name``), then opens a **headed browser** (the
        ``login`` verb is the explicit (re)authentication flow and must always
        show a window — the headless "already valid" fast-path belongs to the
        ``validate``/``check``/``health`` verbs, not here), navigates to
        chat.qwen.ai, and waits for the browser to close or the confirmation
        callback to fire.  On success the profile is snapshotted and
        registered in the session pool so rotation and ``session list`` see
        it.

        Returns the result in the dict shape the session-verb route in
        :meth:`execute` wraps into a ``SessionResponse``.
        """
        profile_path = session_path
        if profile_path is None:
            profile_path = SESSIONS_DIR / name

        # Manual login requires a visible browser window (AES205: the user
        # types credentials, so a hidden browser makes no sense). Force
        # headless=False unconditionally.
        cfg = build_app_config(
            mode="login",
            input_path=DEFAULT_OUTPUT,
            output_path=DEFAULT_OUTPUT,
            session_path=profile_path,
            headless=False,
        )

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
                    if wait_for_confirmation is not None and wait_for_confirmation():
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
            if self._sessions is not None:
                try:
                    self._sessions.add_session(name, cfg.session_path)
                except Exception as exc:
                    self._observability.get_logger().warning(
                        "session_pool_register_failed", error=str(exc), session_path=str(cfg.session_path)
                    )
            return {
                "success": True,
                "message": "Manual login completed successfully.",
                "error": None,
                "profile_path": str(cfg.session_path),
            }

        return {
            "success": False,
            "message": "Manual login did not produce a valid Qwen session.",
            "error": "Please run 'qwen-web-arwaky session login --name <name>' again and finish the login or CAPTCHA.",
            "profile_path": None,
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
