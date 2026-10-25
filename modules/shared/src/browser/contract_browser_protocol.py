"""Browser-domain capability contract (AES102 `_protocol`).

One file for the browser feature. The browser feature has one capability
seam, ``IBrowserProtocol``: it carries every method ``BrowserAdapter``
implements, with one concrete return type each, so the capability
implements its class outright and never carries stubs.

``IBrowserAggregate`` in ``contract_browser_aggregate.py`` is the outward
export surface for outer layers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any

from playwright.sync_api import BrowserContext, Page

from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_vo import AppConfig, ModelLabel, WaitTimeoutMs


class IBrowserModelPolicyProtocol(ABC):
    """Model selection/verification policy (issue #283/#374 fallback rules).

    Product policy about which model to run on and the fallback rules when
    the picker is unreadable, keeping DOM mechanics in the browser adapter.
    """

    @abstractmethod
    def select_model(self, page: Page, emitter: LifecycleEmitter) -> ModelLabel:
        """Read/select the default model on *page*; return the chosen label.

        Raises:
            ModelSwitchError: When no model label can be read at all.
        """
        ...

    @abstractmethod
    def verify_model(self, page: Page, expected: ModelLabel) -> bool:
        """Return True when *page* shows *expected* as the active model."""
        ...

    # Internal DOM-mechanic helpers the browser adapter's delegation
    # wrappers reach through; not part of the outward-facing public seam.

    @abstractmethod
    def ensure_default_model(self, page: Page) -> bool:
        """Best-effort: click the configured default option in the picker.

        Any failure is logged and swallowed so it never blocks the prompt
        pipeline (the verify step drives fallback).
        """
        ...

    @abstractmethod
    def verify_default_model(
        self, page: Page, target: ModelLabel, require_switch: bool = True
    ) -> tuple[bool, ModelLabel]:
        """Confirm the active model is *target*, degrading when it is not.

        Returns ``(True, target)`` when the configured default is active.
        When the configured model is absent from the picker, the first
        available model is selected and a WARNING is logged (issue #283
        AC-2); the method then returns ``(False, fallback)`` so the caller
        proceeds with the active model instead of aborting the pipeline
        (issue #374). Raises ``ModelSwitchError`` only when no model label
        can be read at all.
        """
        ...

    @abstractmethod
    def select_first_available_model(self, page: Page) -> ModelLabel | None:
        """Select the first model the picker offers, or return None when unreadable.

        The graceful-degradation path for a renamed or deprecated model
        identifier (issue #283 AC-2): the run continues on whatever model
        the picker exposes first.
        """
        ...

    @abstractmethod
    def wait_for_picker_ready(self, page: Page, timeout_ms: WaitTimeoutMs = WaitTimeoutMs(15_000)) -> None:
        """Wait until the hydrated picker exposes the configured default option."""
        ...

    @abstractmethod
    def retry_default_model_selection(self, page: Page) -> None:
        """Close a stale picker, allow hydration, and retry default-model selection."""
        ...

    @abstractmethod
    def get_model_trigger(self, page: Page) -> Any:
        """Return the locator for the active model selector trigger button/div."""
        ...

    @abstractmethod
    def try_set_as_default(self, page: Page) -> None:
        """Best-effort attempt to click 'Set default' in the Qwen UI picker."""
        ...


class IBrowserProtocol(ABC):
    """Browser lifecycle capability contract (Playwright adaptation).

    One named method per operation. No ``execute(op, …)`` dispatch;
    each operation has its own typed signature and concrete return type.
    """

    @abstractmethod
    def browser_session(self, cfg: AppConfig) -> AbstractContextManager[BrowserContext]:
        """Launch an isolated persistent Chromium context for *cfg*.

        The returned context manager owns the Chromium process group and
        scopes the session profile to the run, so parallel runs never
        contend on the profile's ``SingletonLock``. Exiting tears the
        browser down, so a raising caller cannot leak a process.
        """
        ...

    @abstractmethod
    def navigate_to_chat(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Navigate *page* to the chat, select the model, emit startup events.

        Navigation, the authentication assertion, a clean-conversation
        reset, and default-model selection all complete before the
        ``web_loaded`` / ``login_verified`` / ``model_verified`` events
        reach *emitter*, so an observer that has seen those events knows
        the page is ready to drive.

        Raises:
            AuthRequiredError: When the page resolves to a login or
                guest view.
            ModelSwitchError: When no model label can be read at all.
        """
        ...

    @abstractmethod
    def check_auth(self, page: Page) -> None:
        """Raise ``AuthRequiredError`` when *page* is not authenticated.

        Combines the URL check with the login-form check, so a caller
        can prove the session without inspecting the DOM itself.

        Raises:
            AuthRequiredError: When the page is on a login or guest view,
                or shows a login form.
        """
        ...

    @abstractmethod
    def health_probe_page(self, cfg: AppConfig) -> AbstractContextManager[Page]:
        """Open one fresh, authenticated chat page on *cfg*'s session profile.

        The returned context manager launches an ephemeral persistent
        Chromium context scoped to *cfg.session_path*, navigates to the
        chat URL, asserts authentication, and yields one ready page.
        It performs no model selection and no prompt dispatch, so a
        caller only pays the page-load cost. Exiting tears down the
        browser process group.

        Raises:
            AuthRequiredError: When the page lands on a login or guest
                view, or shows a login form.
        """
        ...

    @abstractmethod
    def check_session(self, page: Page) -> bool:
        """Return True when *page* shows the authenticated chat UI.

        Never raises, unlike :meth:`check_auth`: a page that is still
        loading is tolerated and judged by the live chat-input check.
        Surfaces use the boolean to report session state.
        """
        ...

    @abstractmethod
    def detect_session_expired(self, page: Page) -> bool:
        """True when the live page now shows an in-page session-expiry notice.

        Re-runs the banner text/selector scan from ``_assert_on_chat_page``
        against the CURRENT page state. Best-effort: a DOM that is unreadable
        (mid-hydration) is not a signal, so the method returns False rather
        than raising. Used by prompt pipelines after a failed dispatch to
        surface ``EVENT_SESSION_EXPIRED``.
        """
        ...

    @abstractmethod
    def renew_session(self, cfg: AppConfig) -> None:
        """Attempt to renew the session credentials on *cfg*'s profile in place.

        Opens the chat page on the MASTER profile (login mode, no ephemeral
        clone) so that when the ``auth-session`` cookie has expired but the
        long-lived ``refresh_token`` is still valid, the site's own JS can
        exchange the refresh token for a fresh session cookie while the page
        loads. The renewed cookies are persisted to the master profile on
        context close.

        Raises:
            AuthRequiredError: When the session could not be renewed — either
                the page still lands on a login/guest view, shows a login
                form, or the refresh token itself is dead (manual re-login
                is the only path left).
        """
        ...

    @abstractmethod
    def reset_page(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Reset *page* to a clean chat state.

        Navigates back to chat.qwen.ai and emits a network-reconnecting
        event, so the observer sees the reset as a recoverable dip
        rather than a new session.
        """
        ...


class ISessionCheckProtocol(ABC):
    """Session liveness and auth-probe capability contract.

    One named method per probe: a page-readiness check and an
    authentication assertion. The capability binds both to the Playwright
    page it wraps, so a caller gets a stateless probe object instead of
    repeating the sequence.
    """

    @abstractmethod
    def is_alive(self) -> bool:
        """Return True when the session is stable and the chat UI is responsive.

        Never raises: a page that is still loading or whose DOM is not
        readable is judged False by the live checks, not reported as an
        error.
        """
        ...

    @abstractmethod
    def check_auth(self) -> None:
        """Raise AuthRequiredError when the session is no longer authenticated.

        Combines the URL check with the login-form and in-page expiry
        banner checks, so a caller proves the session without inspecting
        the DOM itself.

        Raises:
            AuthRequiredError: When the page is on a login or guest view,
                shows a login form, or the saved session has expired.
        """
        ...


__all__ = [
    "IBrowserModelPolicyProtocol",
    "IBrowserProtocol",
    "ISessionCheckProtocol",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IBrowserModelPolicyProtocol": IBrowserModelPolicyProtocol,
    "IBrowserProtocol": IBrowserProtocol,
    "ISessionCheckProtocol": ISessionCheckProtocol,
}
