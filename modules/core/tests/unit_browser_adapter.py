"""Unit tests for browser session management and lifecycle helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.core.src.capabilities_browser_adapter import BrowserAdapter, SessionCheck
from modules.shared.src import AuthRequiredError, LifecycleEmitter
from modules.shared.src.taxonomy_core_event import (
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_WEB_LOADED,
)


def test_session_check_is_alive_success():
    mock_page = MagicMock()
    mock_page.evaluate.return_value = "complete"
    mock_page.query_selector.return_value = MagicMock()

    checker = SessionCheck(mock_page)
    assert checker.is_alive() is True


def test_session_check_not_ready():
    mock_page = MagicMock()
    mock_page.evaluate.return_value = "loading"

    checker = SessionCheck(mock_page)
    assert checker.is_alive() is False


def test_session_check_textarea_missing():
    mock_page = MagicMock()
    mock_page.evaluate.return_value = "complete"
    mock_page.query_selector.return_value = None

    checker = SessionCheck(mock_page)
    assert checker.is_alive() is False


def test_session_check_auth_redirect():
    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/login"

    checker = SessionCheck(mock_page)
    with pytest.raises(AuthRequiredError, match="Not authenticated"):
        checker.check_auth()


def test_check_auth_valid():
    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    loc = MagicMock()
    loc.count.return_value = 0
    mock_page.locator.return_value = loc
    mock_page.query_selector.return_value = MagicMock()
    BrowserAdapter().check_auth(mock_page)


def test_check_auth_login_url():
    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/passport/login"
    loc = MagicMock()
    loc.count.return_value = 0
    mock_page.locator.return_value = loc

    with pytest.raises(AuthRequiredError, match="Not authenticated"):
        BrowserAdapter().check_auth(mock_page)


def test_reset_page_emits_reconnecting():
    mock_page = MagicMock()
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    BrowserAdapter().reset_page(mock_page, mock_emitter)
    mock_emitter.emit.assert_called_once()
    mock_page.goto.assert_called_once()


def test_goto_chat_uses_commit_when_domcontentloaded_is_slow():
    from playwright.sync_api import Error as PwError

    mock_page = MagicMock()
    mock_page.wait_for_load_state.side_effect = PwError("third-party asset stalled")

    BrowserAdapter()._goto_chat(mock_page, navigation_timeout_ms=1000, load_timeout_ms=100)

    assert mock_page.goto.call_args.kwargs["wait_until"] == "commit"
    assert mock_page.goto.call_args.kwargs["timeout"] == 1000


def test_navigate_to_chat_emits_web_loaded():
    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    loc = MagicMock()
    loc.count.return_value = 0
    loc.first.is_visible.return_value = False
    loc.first.is_enabled.return_value = False
    mock_page.locator.return_value = loc
    mock_page.query_selector.return_value = MagicMock()
    # Simulate the model switch succeeding: the picker now reports Qwen3.8-Max.
    mock_page.get_by_role.return_value.inner_text.return_value = "Select Model Qwen3.8-Max"
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    BrowserAdapter().navigate_to_chat(mock_page, mock_emitter)

    # navigate_to_chat emits WEB_LOADED, LOGIN_VERIFIED, then MODEL_VERIFIED.
    emitted_events = [call.args[0] for call in mock_emitter.emit.call_args_list]
    assert emitted_events == [EVENT_WEB_LOADED, EVENT_LOGIN_VERIFIED, EVENT_MODEL_VERIFIED]


def test_clean_stale_locks(tmp_path: Path):
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    lock_file = session_dir / "SingletonLock"
    lock_file.write_text("lock")

    BrowserAdapter()._clean_stale_locks(str(session_dir))
    assert not lock_file.exists()


def test_ensure_default_model_clicks_default_option():
    from modules.shared.src.taxonomy_core_constant import DEFAULT_MODEL

    mock_page = MagicMock()
    picker = MagicMock()
    option = MagicMock()
    set_btn = MagicMock()
    set_btn.is_visible.return_value = False
    locators = {MODEL_SELECTOR_BUTTON_NAME: picker, DEFAULT_MODEL: option, "Set default": set_btn}

    def _fake_get_by_role(role, name=None, exact=False):
        return locators.get(name or "", MagicMock())

    mock_page.get_by_role.side_effect = _fake_get_by_role

    switched = BrowserAdapter().ensure_default_model(mock_page)

    assert switched is True
    picker.wait_for.assert_called_once()
    assert picker.click.call_count >= 1
    option.wait_for.assert_called_once()
    option.click.assert_called_once()
    assert mock_page.wait_for_timeout.call_count >= 1


def test_try_set_as_default_clicks_button():
    mock_page = MagicMock()
    trigger = MagicMock()
    trigger.is_visible.return_value = True
    item = MagicMock()
    item.is_visible.return_value = True
    pin = MagicMock()
    pin.inner_text.return_value = "Set as default"

    item.locator.return_value.first = pin

    def _fake_locator(selector, has_text=None):
        mock = MagicMock()
        if ".wms-trigger" in selector:
            mock.first = trigger
        elif ".wms-list__item" in selector:
            mock.first = item
        return mock

    mock_page.locator.side_effect = _fake_locator

    BrowserAdapter()._try_set_as_default(mock_page)

    trigger.click.assert_called_once_with(timeout=3000)
    pin.evaluate.assert_called_once_with("e => e.click()")
    mock_page.keyboard.press.assert_called_once_with("Escape")


def test_ensure_default_model_swallows_error():
    from playwright.sync_api import Error as PwError

    mock_page = MagicMock()
    mock_page.get_by_role.return_value.wait_for.side_effect = PwError("picker missing")

    # Best-effort: must never raise and must report failure, so the prompt
    # pipeline can fall back to a single verification pass.
    assert BrowserAdapter().ensure_default_model(mock_page) is False


def test_verify_default_model_retries_transient_picker_read_failure():
    from playwright.sync_api import Error as PwError

    from modules.shared.src.taxonomy_core_constant import DEFAULT_MODEL

    mock_page = MagicMock()
    picker = mock_page.get_by_role.return_value
    picker.inner_text.side_effect = [PwError("picker not hydrated"), f"Select Model {DEFAULT_MODEL}"]
    adapter = BrowserAdapter()
    adapter.ensure_default_model = MagicMock(return_value=False)

    adapter._verify_default_model(mock_page)

    assert picker.inner_text.call_count == 2
    mock_page.keyboard.press.assert_called_once_with("Escape")
    adapter.ensure_default_model.assert_called_once_with(mock_page)


def test_verify_default_model_ok():
    from modules.shared.src.taxonomy_core_constant import DEFAULT_MODEL

    mock_page = MagicMock()
    mock_page.get_by_role.return_value.inner_text.return_value = f"Select Model {DEFAULT_MODEL}"

    # Must not raise when the picker reports the hardcoded default.
    BrowserAdapter()._verify_default_model(mock_page)


def test_verify_default_model_raises_on_mismatch():
    from modules.shared.src.taxonomy_core_error import ModelSwitchError

    mock_page = MagicMock()
    mock_page.get_by_role.return_value.inner_text.return_value = "Select Model Qwen3.7-Plus"

    with pytest.raises(ModelSwitchError, match="Default model not active"):
        BrowserAdapter()._verify_default_model(mock_page)


def test_verify_default_model_rejects_superstring_model():
    """A similarly-named model (e.g. Qwen3.8-Max-X) must NOT pass the gate."""
    from modules.shared.src.taxonomy_core_error import ModelSwitchError

    mock_page = MagicMock()
    mock_page.get_by_role.return_value.inner_text.return_value = "Select Model Qwen3.8-Max-Plus"

    with pytest.raises(ModelSwitchError, match="Default model not active"):
        BrowserAdapter()._verify_default_model(mock_page)


def test_verify_default_model_retries_when_switch_reported_failure():
    from modules.shared.src.taxonomy_core_constant import DEFAULT_MODEL

    mock_page = MagicMock()
    # First read shows the old model; the retry re-runs ensure_default_model,
    # after which the picker reports the default model.
    inner_texts = iter(["Select Model Qwen3.7-Plus", f"Select Model {DEFAULT_MODEL}"])

    def _fake_inner_text():
        return next(inner_texts)

    mock_page.get_by_role.return_value.inner_text.side_effect = _fake_inner_text

    # Must not raise: the retry path fixes the mismatch.
    BrowserAdapter()._verify_default_model(mock_page, require_switch=False)


def test_verify_default_model_raises_when_unreadable():
    from playwright.sync_api import Error as PwError

    from modules.shared.src.taxonomy_core_error import ModelSwitchError

    mock_page = MagicMock()
    mock_page.get_by_role.return_value.wait_for.side_effect = PwError("picker gone")

    with pytest.raises(ModelSwitchError, match="Cannot read active model"):
        BrowserAdapter()._verify_default_model(mock_page)


MODEL_SELECTOR_BUTTON_NAME = "Select Model"
