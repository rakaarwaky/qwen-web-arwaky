"""Regression test: the CLI root injects the session seams the TUI needs.

Two wiring gaps left the Sessions tab empty and every ``session``
subcommand unusable when driven through ``main()``:

* ``handle_sessions`` was called without the session aggregate, so
  ``qwen-web-arwaky session ...`` aborted with "Session aggregate not
  injected".
* ``InteractiveController`` was built without ``session_manager``, so the
  TUI's ``_ensure_sessions_loaded`` early-returned on its ``None`` guard
  and the Sessions pane stayed at REGISTERED 0 even with a populated pool.

Both injections come from the root container, so these tests patch the
container's seams and assert the values reach the call sites.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.cli.src.surface_cli_interactive_controller import InteractiveController
from modules.root_cli_main_entry import main
from modules.shared.src.session.taxonomy_session_vo import SessionList, SessionResponse


def _fake_container(session_manager: MagicMock, session_rotator: MagicMock | None = None) -> MagicMock:
    """Container double exposing only the seams ``main()`` reads.

    Attribute children are pre-assigned so the assertion compares the exact
    instance the controller receives against the one the test holds.
    """
    container = MagicMock()
    container.session_manager = session_manager
    container.session_rotator = session_rotator if session_rotator is not None else MagicMock()
    container.agent_session_orchestrator = MagicMock(name="session_aggregate")
    container.agent_job_orchestrator = MagicMock()
    container.agent_swarm_orchestrator = MagicMock()
    container.agent_update_orchestrator = MagicMock()
    container.config = MagicMock()
    container.observability = MagicMock()
    # The interactive path composes the prompt aggregate from these seams
    # before the controller is built; each must be a real attribute.
    container.agent_direct_prompt_orchestrator = MagicMock()
    container.agent_prompt_file_orchestrator = MagicMock()
    container.agent_attachment_prompt_orchestrator = MagicMock()
    container.run_cancel_registry = MagicMock()
    return container


def test_session_subcommand_receives_the_session_aggregate(tmp_path: Path) -> None:
    """``session <cmd>`` must dispatch through the injected aggregate."""
    with (
        patch("sys.argv", ["qwen-web-arwaky", "session", "status"]),
        patch("modules.root_cli_main_entry._default_container") as container_fn,
        patch("modules.cli.src.surface_cli_sessions_command.print"),
    ):
        container = _fake_container(MagicMock())
        # A listing verb must answer with an empty pool, not a MagicMock
        # whose truthy ``error`` turns every session command into a failure.
        container.agent_session_orchestrator.execute.return_value = SessionResponse(
            sessions=SessionList([]), message="0 sessions"
        )
        container_fn.return_value = container
        assert main() == 0

    container.agent_session_orchestrator.execute.assert_called_once()


def test_interactive_controller_receives_the_session_manager(tmp_path: Path) -> None:
    """The TUI controller needs the pool manager or the Sessions tab stays empty."""
    session_manager = MagicMock()
    captured: dict[str, object] = {}

    original_init = InteractiveController.__init__

    def _capture(self: InteractiveController, *args: object, **kwargs: object) -> None:
        captured.update(kwargs)
        original_init(self, *args, **kwargs)

    with (
        patch("sys.argv", ["qwen-web-arwaky"]),
        patch("sys.stdin.isatty", return_value=True),
        patch("modules.root_cli_main_entry._default_container") as container_fn,
        patch(
            "modules.cli.src.surface_cli_interactive_controller.InteractiveController.run",
            return_value={"success": True, "message": "TUI Session Closed."},
        ),
        patch.object(InteractiveController, "__init__", _capture),
    ):
        container = _fake_container(session_manager)
        container_fn.return_value = container
        assert main() == 0

    assert captured.get("session_manager") is session_manager


def test_interactive_controller_receives_the_session_rotator(tmp_path: Path) -> None:
    """The headless TUI path needs the rotator or it reverts to the default session.

    ``InteractiveController``'s headless branch builds its own AppConfig, so
    without an injected rotator the pool selection is dropped and an empty
    default session is used instead of a logged-in profile.
    """
    session_manager = MagicMock()
    rotator = MagicMock(name="session_rotator")
    captured: dict[str, object] = {}

    original_init = InteractiveController.__init__

    def _capture(self: InteractiveController, *args: object, **kwargs: object) -> None:
        captured.update(kwargs)
        original_init(self, *args, **kwargs)

    with (
        patch("sys.argv", ["qwen-web-arwaky"]),
        patch("sys.stdin.isatty", return_value=True),
        patch("modules.root_cli_main_entry._default_container") as container_fn,
        patch(
            "modules.cli.src.surface_cli_interactive_controller.InteractiveController.run",
            return_value={"success": True, "message": "TUI Session Closed."},
        ),
        patch.object(InteractiveController, "__init__", _capture),
    ):
        container = _fake_container(session_manager, rotator)
        container_fn.return_value = container
        assert main() == 0

    assert captured.get("session_rotator") is rotator
