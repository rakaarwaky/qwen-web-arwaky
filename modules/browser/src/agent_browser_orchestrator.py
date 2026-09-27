"""Agent: authenticate a browser session so callers never repeat the sequence.

Each prompt and session orchestrator used to open a Chromium context, pick a
page, navigate to the chat, and prove the saved session was still signed in —
four steps repeated in six files. This orchestrator owns that sequence once and
exposes it as a single context manager, so no caller can forget the
authentication check that every DOM interaction depends on.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import BrowserContext, Page

from modules.shared.src.contract_core_aggregate import IBrowserAggregate
from modules.shared.src.contract_core_protocol import IBrowserProtocol
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_vo import AppConfig

__all__ = ["BrowserOrchestrator"]


class BrowserOrchestrator(IBrowserAggregate):
    """Open authenticated chat sessions on behalf of the other orchestrators."""

    def __init__(self, browser: IBrowserProtocol) -> None:
        """Wrap the browser capability that does the Playwright work.

        The dependency arrives as ``IBrowserProtocol`` so this agent depends on
        the contract, not on the concrete ``BrowserAdapter``: a test can inject
        a stub that never launches a real Chromium process.
        """
        self._browser = browser

    @contextmanager
    def open_session(self, cfg: AppConfig) -> Iterator[Page]:
        """Yield a page already navigated to the chat and proven authenticated.

        Entering launches the persistent Chromium context and yields the first
        page, or a new one when the context starts empty. Navigation and the
        auth check run before the page is handed over, so a caller receiving a
        page is guaranteed a signed-in chat. Exiting tears the context down even
        when the caller's body raises, which is what keeps a failed run from
        leaking Chromium processes.
        """
        with self._browser.browser_session(cfg) as bctx:
            yield self._first_page(bctx)

    def check_session(self, page: Page) -> bool:
        """Return True when ``page`` shows the authenticated chat UI.

        Callers use this to report a session's state without raising, unlike
        the auth check inside :meth:`open_session`.
        """
        return self._browser.check_session(page)

    def _first_page(self, bctx: BrowserContext) -> Page:
        """Return the context's first page, creating one when it has none.

        A freshly launched persistent context usually exposes about:blank, but
        a restored profile can start with none, and every caller needs a page to
        work with, so the fallback keeps one code path for both cases.
        """
        if getattr(bctx, "pages", None):
            return bctx.pages[0]
        return bctx.new_page()

    def navigate_to_chat(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Navigate ``page`` to the chat and verify the session is signed in.

        Exposed for the flows that already hold a page (session validation,
        manual login) and therefore do not enter :meth:`open_session`, so the
        auth check stays in one place for those paths too.
        """
        self._browser.navigate_to_chat(page, emitter)
        self._browser.check_auth(page)
