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


@dataclass(frozen=True)
class SetupRequest:
    """One setup verb plus everything the agent needs to run it.

    Fields the chosen verb does not read stay at their defaults, so the
    login sequence and the standalone browser-launched setup verb share
    one shape without either one passing arguments the other ignores.
    """

    verb: str = ""
    browser_headless: bool = True
    profile_path: Path | str | None = None


@dataclass(frozen=True)
class SetupResponse:
    """What a setup verb produced.

    ``success`` is ``True`` when the browser session was established;
    ``error`` names the reason when the sequence could not be completed.
    ``profile_path`` carries the resolved profile directory on success
    so a caller that receives the response without reading the exception
    can still locate the persisted session.
    """

    success: bool = False
    profile_path: Path | str | None = None
    error: str | None = None


__all__ = ["SetupRequest", "SetupResponse"]
