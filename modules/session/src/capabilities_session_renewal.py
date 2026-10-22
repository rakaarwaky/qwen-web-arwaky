"""Session renewal capability — transparent token refresh for expired auth sessions.

When the short-lived ``auth-session`` cookie in a saved profile has expired
but the long-lived ``refresh_token`` is still valid, the site's own JavaScript
can exchange the refresh token for a new session cookie on page load. This
capability drives that flow through the browser seam: it opens the chat page
on the master profile (login mode) so the browser can self-heal, then asserts
the session is healthy. When both cookies are dead it raises ``AuthRequiredError``
with an actionable message pointing at manual re-login.

AES301: capability layer. Imports taxonomy, contract, and utility only.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src import is_auth_session_expired, renewal_is_possible
from modules.shared.src.browser.contract_browser_protocol import IBrowserProtocol
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_error import AuthRequiredError, QwenCliError
from modules.shared.src.common.taxonomy_core_event import EVENT_SESSION_EXPIRED, EVENT_SESSION_RENEWED
from modules.shared.src.common.taxonomy_core_vo import AppConfig
from modules.shared.src.common.utility_logger_factory import get_logger
from modules.shared.src.logging.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.session.contract_session_protocol import ISessionRenewalProtocol

log = get_logger("session_renewal")


class SessionRenewalError(QwenCliError):
    """Raised when a session renewal attempt fails but the caller can retry."""


# Block 1: Class Definition & Constructor
class SessionRenewer(ISessionRenewalProtocol):
    """Detects stale auth sessions and renews them via browser self-heal.

    Wire-up:
        browser: IBrowserProtocol
        observability: IObservabilityProtocol

    Public method:
        renew_session_if_stale(cfg, session_path=None) -> bool
    """

    def __init__(
        self,
        browser: IBrowserProtocol,
        observability: IObservabilityProtocol,
    ) -> None:
        self._browser = browser
        self._observability = observability

    # Block 2: Protocol Method Implementation
    def renew_session_if_stale(
        self,
        cfg: AppConfig,
        *,
        session_path: Path | None = None,
    ) -> bool:
        """Renew the session credentials if the auth session is stale.

        Returns True when the session is healthy (either already, or after
        a successful renewal attempt). Raises ``AuthRequiredError`` when
        renewal is impossible or fails — the caller must fall back to
        manual login.

        Steps:
        1. Fast-path: if the cookie store shows a valid ``auth-session``
           cookie, return True immediately (healthy session, no work needed).
        2. If renewal is impossible (``auth-session`` expired/absent AND
           ``refresh_token`` expired/absent), raise
           ``AuthRequiredError(session_expired=True)`` with the actionable
           message pointing at manual re-login.
        3. Otherwise (``auth-session`` stale, ``refresh_token`` valid): run
           the browser warm-up on the master profile. On success, emit
           ``EVENT_SESSION_RENEWED`` and return True. On failure, raise
           ``AuthRequiredError``.

        ``session_path`` may be passed to override the profile path from
        ``cfg`` (used by the orchestrator before it has a full ``AppConfig``).
        """
        profile_dir = session_path if session_path else cfg.session_path

        logger = self._observability.get_logger()
        emitter = LifecycleEmitter(logger)

        # Step 1: fast-path — is the auth session already healthy?
        if not is_auth_session_expired(profile_dir):
            logger.debug("session_renewal_skipped_healthy", profile=str(profile_dir))
            return True

        # Step 2: can renewal even succeed?
        if not renewal_is_possible(profile_dir):
            logger.warning(
                "session_renewal_impossible_refresh_token_dead",
                profile=str(profile_dir),
            )
            emitter.emit(
                EVENT_SESSION_EXPIRED,
                {"url": "https://chat.qwen.ai", "reason": "cookie_store_refresh_token_invalid"},
            )
            raise AuthRequiredError(
                "Session expired and refresh token is invalid or missing — "
                "the saved login session can no longer be renewed automatically. "
                "Run `qwen-web-arwaky session login` to re-authenticate, then retry.",
                session_expired=True,
            )

        # Step 3: attempt the browser warm-up on the master profile.
        logger.info("session_renewal_attempting_browser_warmup", profile=str(profile_dir))
        try:
            self._browser.renew_session(cfg)
        except AuthRequiredError:
            raise
        except Exception as exc:
            raise AuthRequiredError(
                f"Session renewal attempt failed: {exc}. "
                "The refresh token may be invalid or the network may be unreachable. "
                "Run `qwen-web-arwaky session login` to re-authenticate, then retry.",
                session_expired=True,
            ) from exc

        logger.info("session_renewal_success", profile=str(profile_dir))
        emitter.emit(
            EVENT_SESSION_RENEWED,
            {"url": "https://chat.qwen.ai", "reason": "browser_warmup_refresh"},
        )
        return True

    # Block 3: Dunder Methods, Factories & Helpers
    def __repr__(self) -> str:
        return f"SessionRenewer(browser={self._browser!r}, observability={self._observability!r})"


__all__ = ["SessionRenewalError", "SessionRenewer"]
