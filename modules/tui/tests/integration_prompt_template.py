"""Integration tests for built-in prompt template usage in the TUI surface."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestTuiPromptTemplateIntegration:
    """Test TUI role template resolution."""

    def test_tui_action_run_action_with_role(self) -> None:
        from modules.config.src.capabilities_config_slot_resolver import SlotRunPlanResolver
        from modules.tui.src.surface_tui_app import QwenTuiApp

        # AR-1: 5th positional arg is slot_config (ISlotRunPlanProtocol),
        # injected from the Root container instead of being constructed
        # inside the TUI surface. Use the real resolver so role-template
        # materialization is exercised end-to-end.
        app = QwenTuiApp(
            MagicMock(),  # workspace
            MagicMock(),  # direct
            MagicMock(),  # file_only
            MagicMock(),  # attachment
            SlotRunPlanResolver(),  # slot_config
        )

        # The per-slot Settings form is gone; the keyboard run reads the
        # slot's typed composer text as the prompt source, so a role typed
        # in the composer materializes exactly as it did in the old form.
        mock_composer = MagicMock(value="software-architect")

        def fake_query_one(selector: str, *args: object, **kwargs: object) -> MagicMock:
            sel = str(selector)
            if sel.startswith("#composer-"):
                return mock_composer
            return MagicMock()

        app.query_one = fake_query_one
        app._execute_slot_worker = MagicMock()
        app.set_timer = MagicMock()
        app._run_slot(1)

        app._execute_slot_worker.assert_called_once()
        cfg = app._execute_slot_worker.call_args[0][1]
        assert cfg.prompt_path is not None
        assert cfg.prompt_path.name == "software-architect.md"
        assert cfg.prompt_path.exists()
