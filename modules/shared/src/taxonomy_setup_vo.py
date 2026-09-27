"""Setup-domain value objects and aggregate request/response pair.

The setup feature owns the interactive manual-login flow: launch a
browser, navigate to the Qwen login page, complete the CAPTCHA, and
validate the resulting session. Consumers depend on one seam — the
aggregate's ``execute`` — so the surface never has to call multiple
capability methods directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class SetupRequest:
    """One setup verb plus everything the agent needs to run it.

    Fields the chosen verb does not read stay at their defaults, so the
    login sequence and the standalone browser-launched setup verb share
    one shape without either one passing arguments the other ignores.

    ``wait_for_confirmation`` lets an interactive caller hold the browser
    open inside the context until it signals the manual login finished;
    it must be consulted while the page is still live, so the agent runs
    it during the wait loop rather than after the context closes.
    """

    verb: str = ""
    browser_headless: bool = True
    profile_path: Path | str | None = None
    wait_for_confirmation: Callable[[], bool] | None = None


@dataclass(frozen=True)
class SetupResponse:
    """What a setup verb produced.

    ``success`` is ``True`` when the browser session was established;
    ``error`` names the reason when the sequence could not be completed.
    ``profile_path`` carries the resolved profile directory on success
    so a caller that receives the response without reading the exception
    can still locate the persisted session. ``message`` is the
    human-readable outcome a surface renders directly — it distinguishes
    "the saved session was already valid" from "a fresh manual login
    completed", which the profile path alone cannot tell apart.
    """

    success: bool = False
    profile_path: Path | str | None = None
    message: str = ""
    error: str | None = None


__all__ = ["SetupRequest", "SetupResponse"]
