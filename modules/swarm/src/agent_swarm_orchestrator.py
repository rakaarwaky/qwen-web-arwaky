"""Agent: route a Swarm request to the swarm runner and shape its response.

The TUI Swarm tab, the CLI swarm command, and the MCP swarm tool all call
``execute`` on this one method. The routing and the two policies a
consumer should not re-implement — resolving a folder input down to one
attachment, and warning before a fan-out large enough to hurt the host —
live here, so a surface cannot skip either one.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.contract_jobs_protocol import IFolderToAttachmentProtocol
from modules.shared.src.contract_swarm_aggregate import ISwarmAggregate
from modules.shared.src.contract_swarm_protocol import ISwarmProtocol
from modules.shared.src.taxonomy_core_vo import FilePath
from modules.shared.src.taxonomy_swarm_vo import (
    BrowserCount,
    SwarmId,
    SwarmRequest,
    SwarmResponse,
    SwarmSnapshot,
)

__all__ = ["SwarmOrchestrator"]

# Resource-governance policy (issue #277). Above this many concurrent browsers
# the TUI shows an explicit warning before the fan-out starts; below it the
# start is silent, matching the interactive cost users expect.
SWARM_RESOURCE_WARNING_BROWSERS = 4


class SwarmOrchestrator(ISwarmAggregate):
    """Run Swarm fan-outs on behalf of the CLI, TUI, and MCP surfaces.

    Holds the swarm runner as ``ISwarmProtocol`` so this agent depends on
    the contract, not the concrete ``SwarmRunner``: a test can inject a
    stub that never launches a browser.
    """

    def __init__(self, runner: ISwarmProtocol, folder_adapter: IFolderToAttachmentProtocol | None = None) -> None:
        """Wire the swarm runner to the folder resolver that precedes it.

        ``runner`` performs the fan-out. ``folder_adapter`` compiles a
        folder input down to the single attachment every role shares;
        without it a folder input is passed to the roles as-is.
        """
        self._runner = runner
        self._folder_adapter = folder_adapter

    @property
    def browser_concurrency(self) -> BrowserCount:
        """Configured browser concurrency for a single Swarm run."""
        return self._runner.browser_concurrency

    @property
    def resource_warning(self) -> str | None:
        """Return the pre-launch resource warning, or None when it is not needed.

        The TUI Swarm tab presents this as a confirmation modal so a
        resource-intensive fan-out is never started silently (issue #277).
        """
        if self._runner.browser_concurrency < SWARM_RESOURCE_WARNING_BROWSERS:
            return None
        return f"This will launch up to {self._runner.browser_concurrency} browser processes. Continue?"

    def execute(self, request: SwarmRequest) -> SwarmResponse:
        """Route the swarm verb to the runner and return one response shape.

        A missing argument is reported as ``error`` on the response rather
        than raised, so a surface renders the message without a try/except
        around every Swarm call.
        """
        if request.verb == "start":
            if request.input_path is None:
                return SwarmResponse(error="start requires input_path")
            return SwarmResponse(snapshot=self.start(request.input_path))
        if request.verb == "snapshot":
            if request.swarm_id is None:
                return SwarmResponse(error="snapshot requires swarm_id")
            return SwarmResponse(snapshot=self.snapshot(request.swarm_id))
        if request.verb == "cancel":
            if request.swarm_id is None:
                return SwarmResponse(error="cancel requires swarm_id")
            self.cancel(request.swarm_id)
            return SwarmResponse(snapshot=self.snapshot(request.swarm_id))
        raise ValueError(f"Unknown swarm verb: {request.verb!r}")

    def start(self, input_path: Path) -> SwarmSnapshot:
        """Start a fan-out over every discovered role template.

        A folder input is compiled down to one attachment first, so every
        role in the Swarm reads the same material regardless of whether
        the user pointed at a file or a directory.
        """
        source = Path(input_path).expanduser().resolve()
        attachment = source
        if source.is_dir() and self._folder_adapter is not None:
            attachment = self._folder_adapter.resolve_to_attachment(source)
        return self._runner.start(FilePath(source), FilePath(attachment))

    def snapshot(self, swarm_id: SwarmId) -> SwarmSnapshot | None:
        """Return the latest snapshot for a swarm, or None when absent."""
        return self._runner.snapshot(swarm_id)

    def cancel(self, swarm_id: SwarmId) -> None:
        """Cancel queued and active work for a swarm."""
        self._runner.cancel(swarm_id)
