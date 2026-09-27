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

from playwright.sync_api import BrowserContext, Page

from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_vo import AppConfig


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
    def check_session(self, page: Page) -> bool:
        """Return True when *page* shows the authenticated chat UI.

        Never raises, unlike :meth:`check_auth`: a page that is still
        loading is tolerated and judged by the live chat-input check.
        Surfaces use the boolean to report session state.
        """
        ...


__all__ = ["IBrowserProtocol"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IBrowserProtocol": IBrowserProtocol,
}
