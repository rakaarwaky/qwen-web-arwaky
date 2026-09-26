"""Contract test suite verifying public API contracts across feature modules."""

import unittest
from pathlib import Path

from modules.prompt.src.capabilities_direct_prompt_adapter import DirectPromptAdapter as CoreOrchestrator
from modules.shared.src import AppConfig, AuthRequiredError, PromptInjectionError, RunContext


class TestQwenAutoContract(unittest.TestCase):
    """Contract tests to verify class and type signatures exist."""

    def test_app_config_contract(self) -> None:
        cfg = AppConfig(
            mode="single",
            input_path=Path("input.md"),
            output_path=Path("output.md"),
            session_path=Path("session"),
            interval=3,
            timeout=300,
            headless=True,
        )
        self.assertEqual(cfg.mode, "single")
        self.assertEqual(cfg.interval, 3)

    def test_run_context_contract(self) -> None:
        ctx = RunContext()
        self.assertTrue(isinstance(ctx.run_id, str))
        self.assertGreater(len(ctx.run_id), 0)

    def test_exceptions_contract(self) -> None:
        self.assertTrue(issubclass(AuthRequiredError, RuntimeError))
        self.assertTrue(issubclass(PromptInjectionError, RuntimeError))

    def test_core_aggregate_contract_methods(self) -> None:
        expected_methods = [
            "process_direct_prompt",
        ]
        for m in expected_methods:
            self.assertTrue(hasattr(CoreOrchestrator, m), f"CoreOrchestrator missing method {m}")

    def test_update_protocol_contract_methods(self) -> None:
        from modules.shared.src.contract_update_protocol import IUpdateProtocol

        expected = [
            "current_version",
            "check_update",
            "upgrade_package",
            "sync_browser",
            "perform_update",
            "rollback_to",
        ]
        for m in expected:
            self.assertTrue(hasattr(IUpdateProtocol, m), f"IUpdateProtocol missing method {m}")


if __name__ == "__main__":
    unittest.main()
