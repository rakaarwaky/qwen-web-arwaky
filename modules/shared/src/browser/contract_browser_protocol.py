"""Browser-domain capability contract (AES102 `_protocol`).

One file for the browser feature. The browser feature exposes four
capability seams, all defined here:

- ``IBrowserLifecycleProtocol`` — launch/teardown, ephemeral probes, renewal
- ``IBrowserNavigationProtocol`` — goto, auth assert, page reset, login window
- ``IBrowserModelPolicyProtocol`` — model selection/verification (issue #283/#374)
- ``IBrowserDiagnosticsProtocol`` — network/console listeners, URL scrubbing

``IBrowserAggregate`` in ``contract_browser_aggregate.py`` is the outward
export surface for outer layers. The legacy ``IBrowserProtocol`` facade was
retired after the protocol split; every call site now depends on the
narrow protocols directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from pathlib import Path
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

    @abstractmethod
    def target_model(self) -> ModelLabel:
        """Return the per-run target model the picker helpers should read.

        Reads the shared ``utility_browser_model_target`` contextvar so
        concurrent runs scope their model to their own session (issue #283).
        """
        ...


class IBrowserLifecycleProtocol(ABC):
    """Launch/teardown, ephemeral-context probes, and master-profile renewal.

    Owns the Playwright process group and the executable-path injection.
    Does not navigate, select models, or probe liveness.
    """

    @abstractmethod
    def browser_session(
        self,
        cfg: AppConfig,
        session_path: Path | None = None,
        executable_path: str | None = None,
    ) -> AbstractContextManager[BrowserContext]:
        """Launch an isolated persistent Chromium context for *cfg*.

        Exiting tears the browser down, so a raising caller cannot leak a
        process. *session_path* is the profile path prepared by the session
        `ProfilePreparer` (a plain path; the browser capability no longer
        clones the profile). *executable_path* is injected by the update
        module (binary-selection concern); when omitted, the adapter
        resolves it.
        """
        ...

    @abstractmethod
    def health_probe_page(
        self,
        cfg: AppConfig,
        session_path: Path | None = None,
        executable_path: str | None = None,
    ) -> AbstractContextManager[Page]:
        """Open one fresh, authenticated chat page on *cfg*'s session profile.

        Launches an ephemeral persistent context, navigates to the chat URL,
        asserts authentication, and yields one ready page. Performs no model
        selection and no prompt dispatch. Used by `SessionLimitChecker`
        (`modules/session/src/capabilities_session_limit_checker.py` L65).
        """
        ...

    @abstractmethod
    def renew_session(
        self,
        cfg: AppConfig,
        session_path: Path | None = None,
        executable_path: str | None = None,
    ) -> None:
        """Renew session credentials on *cfg*'s master profile in place
        (master-profile warm-up, no ephemeral clone). Raises
        ``AuthRequiredError`` when renewal is impossible. Used by
        `SessionRenewer` (`modules/session/src/capabilities_session_renewal.py`
        L114).
        """
        ...


class IBrowserNavigationProtocol(ABC):
    """Page navigation, authentication assert, and new-chat reset.

    Pure browser mechanics: goto, auth assert, page reset. No model
    selection policy and no profile-cloning.
    """

    @abstractmethod
    def open_chat_page(self, page: Page, *, strict: bool = True) -> None:
        """Navigate *page* to the chat URL and assert authentication.

        The shared launch → navigate → auth-assert sequence's navigation
        half: up to 4 goto attempts with exponential backoff (transient
        network failures), a committed-document load, then one
        authentication assertion. *strict* mirrors the two consumers:
        renewal asserts on the chat page (strict), the health probe
        tolerates a page that is still hydrating (non-strict).

        Raises:
            AuthRequiredError: When the page lands on a login/guest view
                or shows a login form.
        """
        ...

    @abstractmethod
    def navigate_to_chat(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Navigate *page* to the chat, assert auth, reset to a clean conversation.

        Raises:
            AuthRequiredError: When the page resolves to a login or guest view.
        """
        ...

    @abstractmethod
    def check_auth(self, page: Page) -> None:
        """Raise ``AuthRequiredError`` when *page* is not authenticated."""
        ...

    @abstractmethod
    def reset_page(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Reset *page* to a clean chat state."""
        ...

    @abstractmethod
    def open_login_page(
        self, cfg: AppConfig, lifecycle: IBrowserLifecycleProtocol | None = None
    ) -> AbstractContextManager[Page]:
        """Open one fresh page on *cfg*'s profile and go to the chat URL.

        Thin wrapper over ``browser_session`` + first page + ``goto``.
        Used by the manual login window flow; performs no model
        selection. When *lifecycle* is provided it supplies
        ``browser_session`` (the composition root injects the shared
        view); otherwise the navigation capability falls back to its
        own launch path.
        """
        ...


class IBrowserDiagnosticsProtocol(ABC):
    """Page and context diagnostics: asset-abort route, page-creation hook,
    network/console listeners, URL scrubbing, noise demotion.

    Today the diagnostics capability wires diagnostics at TWO levels inside
    `browser_session` (`modules/browser/src/capabilities_browser_diagnostics.py`
    and `modules/browser/src/capabilities_browser_lifecycle.py`): a
    **context-level** asset-abort route
    (`ctx.route("**/*.{png,…}", abort)`) and a page-creation hook
    (`ctx.on("page", attach_page_diagnostics)`), plus **per-page** listeners
    (`page.on("request"/"requestfailed"/"console"/"response")`). The protocol
    therefore covers both levels, not just the per-page half.
    """

    @abstractmethod
    def wire_diagnostics(self, ctx: BrowserContext) -> None:
        """Attach all diagnostics to *ctx*: the context-level asset-abort
        route, the `ctx.on("page", …)` hook that attaches per-page listeners
        to new and existing pages, URL scrubbing, and third-party noise
        demotion. Called once per context from `browser_session` (or the
        launch-pool warm path)."""
        ...

    @abstractmethod
    def detect_session_expired(self, page: Page) -> bool:
        """True when the live page now shows an in-page session-expiry notice.

        Re-runs the banner text/selector scan against the CURRENT page
        state. Best-effort: a DOM that is unreadable (mid-hydration) is
        not a signal, so the method returns False rather than raising.
        Used by prompt pipelines after a failed dispatch to surface
        ``EVENT_SESSION_EXPIRED``.
        """
        ...


__all__ = [
    "IBrowserDiagnosticsProtocol",
    "IBrowserLifecycleProtocol",
    "IBrowserModelPolicyProtocol",
    "IBrowserNavigationProtocol",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IBrowserDiagnosticsProtocol": IBrowserDiagnosticsProtocol,
    "IBrowserLifecycleProtocol": IBrowserLifecycleProtocol,
    "IBrowserModelPolicyProtocol": IBrowserModelPolicyProtocol,
    "IBrowserNavigationProtocol": IBrowserNavigationProtocol,
}
