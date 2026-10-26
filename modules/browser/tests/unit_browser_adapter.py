"""Unit tests for browser session management and lifecycle helpers.

The monolith `capabilities_browser_adapter` was dissolved into narrow
capability views (lifecycle, navigation, model policy, diagnostics) plus
the `BrowserOrchestrator` facade in the Agent layer. These tests drive
that new seam.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.browser.src.agent_browser_orchestrator import (
    BrowserOrchestrator,
    _raise_if_session_expired,
)
from modules.browser.src.capabilities_browser_diagnostics import (
    _NOISE_CONSOLE_PATTERNS,
    BrowserDiagnostics,
    _is_third_party_noise,
)
from modules.browser.src.capabilities_browser_lifecycle import BrowserLifecycle
from modules.browser.src.capabilities_browser_model_policy import BrowserModelPolicy
from modules.browser.src.capabilities_browser_navigation import BrowserNavigation
from modules.session.src.capabilities_session_health_checker import SessionCheck
from modules.shared.src import AuthRequiredError, LifecycleEmitter
from modules.shared.src.browser import utility_browser_session_check as session_check_util
from modules.shared.src.browser.utility_browser_session_check import _in_page_expiry_banner_visible
from modules.shared.src.common import utility_dom_helper as dom_helper
from modules.shared.src.common.taxonomy_core_event import (
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_SESSION_EXPIRED,
    EVENT_WEB_LOADED,
)
from modules.shared.src.common.taxonomy_core_vo import AppConfig


def _make_orchestrator() -> BrowserOrchestrator:
    """Build a BrowserOrchestrator with all narrow capability views wired."""
    obs = MagicMock()
    obs.get_logger.return_value = MagicMock()
    diag = BrowserDiagnostics()
    model_policy = BrowserModelPolicy()
    lifecycle = BrowserLifecycle(navigation=None, diagnostics=diag)
    navigation = BrowserNavigation(model_policy=model_policy, lifecycle=lifecycle)
    lifecycle.navigation = navigation
    return BrowserOrchestrator(
        None,
        obs,
        lifecycle=lifecycle,
        navigation=navigation,
        model_policy=model_policy,
        diagnostics=diag,
    )


def _adapter() -> BrowserOrchestrator:
    """Build a BrowserOrchestrator (replaces the deleted BrowserAdapter)."""
    return _make_orchestrator()


def _make_cfg(tmp_path: Path, mode: str, headless: bool, **extra: object) -> AppConfig:
    """Build a minimal AppConfig for launch-path tests."""
    session = tmp_path / f"session_{mode or 'default'}"
    session.mkdir(parents=True, exist_ok=True)
    return AppConfig(
        mode=mode,
        input_path=tmp_path / "in",
        output_path=tmp_path / "out",
        session_path=session,
        headless=headless,
        **extra,
    )


def _make_page_mock(body_text: str = "", banner_shell_visible: bool = False):
    """Build a chat-page mock with controllable body text and banner shell.

    The banner-shell visibility drives ``is_any_visible`` so tests can script
    either detection path (keyword text or expired-banner CSS) without a real
    Playwright page.
    """
    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_page.inner_text.return_value = body_text
    mock_page.locator.return_value = MagicMock()
    mock_page.query_selector.return_value = MagicMock()

    original_any_visible = dom_helper.is_any_visible
    dom_helper.is_any_visible = lambda page, selectors, _visible=banner_shell_visible: _visible
    return mock_page, session_check_util, original_any_visible


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
    mock_page, adapter_mod, orig = _make_page_mock(body_text="")
    try:
        _adapter().check_auth(mock_page)
    finally:
        dom_helper.is_any_visible = orig


def test_check_auth_login_url():
    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/passport/login"
    loc = MagicMock()
    loc.count.return_value = 0
    mock_page.locator.return_value = loc
    mock_page.inner_text.return_value = ""

    with pytest.raises(AuthRequiredError, match="Not authenticated"):
        _adapter().check_auth(mock_page)


def test_assert_on_chat_page_strict_logs_warning_when_textarea_missing():
    """Steady-state default (strict=True) keeps the warning log level."""
    mock_page, _, _ = _make_page_mock(body_text="")
    mock_page.query_selector.return_value = None  # textarea missing, no login form

    with patch.object(session_check_util.log, "warning") as warn, patch.object(session_check_util.log, "info") as info:
        session_check_util.assert_on_chat_page(mock_page)  # default strict=True

    warn.assert_called_once_with("chat_textarea_missing_but_no_login_form_detected %s", mock_page.url)
    info.assert_not_called()


def test_assert_on_chat_page_non_strict_logs_info_when_textarea_missing():
    """navigate_to_chat (strict=False) demotes the transient-missing state to info."""

    mock_page, _, _ = _make_page_mock(body_text="")
    mock_page.query_selector.return_value = None  # textarea missing, no login form

    with patch.object(session_check_util.log, "warning") as warn, patch.object(session_check_util.log, "info") as info:
        session_check_util.assert_on_chat_page(mock_page, strict=False)

    info.assert_called_once_with("chat_textarea_missing_but_no_login_form_detected %s", mock_page.url)
    warn.assert_not_called()


def test_assert_on_chat_page_strict_still_raises_on_auth_redirect():
    """strict=False must not suppress a real AuthRequiredError."""

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/passport/login"
    loc = MagicMock()
    loc.count.return_value = 0
    mock_page.locator.return_value = loc
    mock_page.inner_text.return_value = ""

    with pytest.raises(AuthRequiredError, match="Not authenticated"):
        session_check_util.assert_on_chat_page(mock_page, strict=False)


def test_reset_page_emits_reconnecting():
    mock_page = MagicMock()
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    _adapter().reset_page(mock_page, mock_emitter)
    mock_emitter.emit.assert_called_once()
    mock_page.goto.assert_called_once()


def test_raise_if_session_expired_banner_keyword():
    """An in-page 'Session expired' notice raises AuthRequiredError tagged session_expired."""

    mock_page, _, orig = _make_page_mock(body_text="Your session has expired. Please login again.")
    try:
        with pytest.raises(AuthRequiredError, match="Session expired") as exc_info:
            _raise_if_session_expired(mock_page)
        assert exc_info.value.session_expired is True
    finally:
        dom_helper.is_any_visible = orig


def test_raise_if_session_expired_banner_selector():
    """A banner shell with no matching keyword text still fires the expiry raise."""

    mock_page, _, _ = _make_page_mock(body_text="", banner_shell_visible=True)
    # Drive the two probes independently: login-form selectors are absent,
    # banner-shell selectors are present, so only the expiry path can fire.
    import modules.shared.src.common.taxonomy_core_constant as const

    banner = ", ".join(const.SESSION_EXPIRED_BANNER_SELECTORS)

    def _split_probe(page, selectors):
        return selectors == banner

    original_is_any_visible = dom_helper.is_any_visible
    dom_helper.is_any_visible = _split_probe
    try:
        with pytest.raises(AuthRequiredError, match="Session expired") as exc_info:
            _raise_if_session_expired(mock_page)
        assert exc_info.value.session_expired is True
    finally:
        dom_helper.is_any_visible = original_is_any_visible


def test_assert_on_chat_page_no_false_positive_on_chat_text():
    """Normal chat content must not trigger the session-expired path."""

    mock_page, _, orig = _make_page_mock(body_text="Hello, here is a response.")
    try:
        session_check_util.assert_on_chat_page(mock_page)  # no raise
    finally:
        dom_helper.is_any_visible = orig


def test_goto_chat_uses_commit_when_domcontentloaded_is_slow():
    from playwright.sync_api import Error as PwError

    mock_page = MagicMock()
    mock_page.wait_for_load_state.side_effect = PwError("third-party asset stalled")

    _adapter()._navigation._goto_chat(mock_page, navigation_timeout_ms=1000, load_timeout_ms=100)

    assert mock_page.goto.call_args.kwargs["wait_until"] == "commit"
    assert mock_page.goto.call_args.kwargs["timeout"] == 1000


def test_navigate_to_chat_emits_web_loaded():

    mock_page, _, orig = _make_page_mock(body_text="")
    loc = MagicMock()
    loc.count.return_value = 0
    loc.first.is_visible.return_value = False
    loc.first.is_enabled.return_value = False
    mock_page.locator.return_value = loc
    mock_page.query_selector.return_value = MagicMock()
    # Simulate the model switch succeeding: the picker now reports Qwen3.8-Max.
    mock_page.get_by_role.return_value.inner_text.return_value = "Select Model Qwen3.8-Max"
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    try:
        _adapter().navigate_to_chat(mock_page, mock_emitter)
    finally:
        dom_helper.is_any_visible = orig

    # navigate_to_chat emits WEB_LOADED, LOGIN_VERIFIED, then MODEL_VERIFIED.
    emitted_events = [call.args[0] for call in mock_emitter.emit.call_args_list]
    assert emitted_events == [EVENT_WEB_LOADED, EVENT_LOGIN_VERIFIED, EVENT_MODEL_VERIFIED]


def test_navigate_to_chat_emits_session_expired_on_in_page_banner():
    """When the chat page shows an in-page expiry banner, navigate_to_chat
    emits EVENT_SESSION_EXPIRED before propagating the AuthRequiredError."""
    mock_page, _, orig = _make_page_mock(body_text="Your session has expired. Please login again.")
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    try:
        with pytest.raises(AuthRequiredError) as exc_info:
            _adapter().navigate_to_chat(mock_page, mock_emitter)
        assert exc_info.value.session_expired is True
    finally:
        dom_helper.is_any_visible = orig
    emitted = [call.args[0] for call in mock_emitter.emit.call_args_list]
    assert EVENT_SESSION_EXPIRED in emitted, f"expected EVENT_SESSION_EXPIRED in {emitted}"
    expired_calls = [c for c in mock_emitter.emit.call_args_list if c.args[0] == EVENT_SESSION_EXPIRED]
    assert expired_calls[0].args[1] == {"url": "https://chat.qwen.ai/", "reason": "in_page_banner"}


def test_navigate_to_chat_no_session_expired_event_on_clean_page():
    """A healthy chat page must not emit EVENT_SESSION_EXPIRED."""

    mock_page, _, orig = _make_page_mock(body_text="Hello")
    mock_page.get_by_role.return_value.inner_text.return_value = "Select Model Qwen3.8-Max"
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    try:
        _adapter().navigate_to_chat(mock_page, mock_emitter)
    finally:
        dom_helper.is_any_visible = orig

    emitted = [call.args[0] for call in mock_emitter.emit.call_args_list]
    assert EVENT_SESSION_EXPIRED not in emitted, f"unexpected EVENT_SESSION_EXPIRED in {emitted}"


def test_navigate_to_chat_reports_fallback_model_on_event():
    """issue #283 AC-2: an unlisted model degrades to the first available one."""

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    trigger = MagicMock()
    trigger.is_visible.return_value = True
    trigger.inner_text.return_value = "Select Model Qwen3.7-Plus"
    first_item = MagicMock()
    first_item.is_visible.return_value = True
    first_item.inner_text.return_value = "Qwen3.7-Plus"

    def _fake_locator(selector, has_text=None):
        loc = MagicMock()
        if ".wms-trigger" in selector:
            loc.first = trigger
        else:
            loc.count.return_value = 0
            loc.first = first_item
            loc.first.is_enabled.return_value = False
        return loc

    mock_page.locator.side_effect = _fake_locator
    mock_page.get_by_role.return_value = trigger
    mock_page.inner_text.return_value = ""
    orig_vis = dom_helper.is_any_visible
    dom_helper.is_any_visible = lambda page, selectors: False
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    try:
        _adapter().navigate_to_chat(mock_page, mock_emitter)
    finally:
        dom_helper.is_any_visible = orig_vis

    verified = [call for call in mock_emitter.emit.call_args_list if call.args[0] == EVENT_MODEL_VERIFIED]
    assert verified, "MODEL_VERIFIED must be emitted even on the fallback path"
    # ``fallback`` rides along (issue #374) so a consumer can tell a substituted
    # model from the configured one.
    assert verified[0].args[1] == {"model": "Qwen3.7-Plus", "fallback": True}


def test_select_first_available_model_returns_none_when_picker_closed():
    mock_page = MagicMock()
    mock_page.locator.return_value.first.is_visible.return_value = False

    assert _adapter()._model_policy.select_first_available_model(mock_page) is None


def test_clean_stale_locks(tmp_path: Path):
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    lock_file = session_dir / "SingletonLock"
    lock_file.write_text("lock")

    _adapter()._lifecycle._clean_stale_locks(str(session_dir))
    assert not lock_file.exists()


def test_ensure_default_model_clicks_default_option():
    from modules.shared.src.common.taxonomy_core_constant import DEFAULT_MODEL

    mock_page = MagicMock()
    picker = MagicMock()
    option = MagicMock()
    set_btn = MagicMock()
    set_btn.is_visible.return_value = False
    locators = {"Select Model": picker, DEFAULT_MODEL: option, "Set default": set_btn}

    def _fake_get_by_role(role, name=None, exact=False):
        return locators.get(name or "", MagicMock())

    mock_page.get_by_role.side_effect = _fake_get_by_role

    switched = _adapter()._model_policy.ensure_default_model(mock_page)

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

    _adapter()._model_policy.try_set_as_default(mock_page)

    trigger.click.assert_called_once_with(timeout=3000)
    pin.evaluate.assert_called_once_with("e => e.click()")
    mock_page.keyboard.press.assert_called_once_with("Escape")


def test_ensure_default_model_swallows_error():
    from playwright.sync_api import Error as PwError

    mock_page = MagicMock()
    mock_page.get_by_role.return_value.wait_for.side_effect = PwError("picker missing")

    # Best-effort: must never raise and must report failure, so the prompt
    # pipeline can fall back to a single verification pass.
    assert _adapter()._model_policy.ensure_default_model(mock_page) is False


def test_verify_default_model_retries_transient_picker_read_failure():
    from playwright.sync_api import Error as PwError

    from modules.shared.src.common.taxonomy_core_constant import DEFAULT_MODEL

    mock_page = MagicMock()
    picker = mock_page.get_by_role.return_value
    picker.inner_text.side_effect = [PwError("picker not hydrated"), f"Select Model {DEFAULT_MODEL}"]
    adapter = _adapter()
    # The retry path now lives in the model-policy capability:
    # verify_default_model -> retry_default_model_selection ->
    # ensure_default_model. Mock the policy-level helpers so the test
    # isolates the retry-and-verify loop without running the real
    # picker DOM interaction.
    adapter._model_policy.ensure_default_model = MagicMock(return_value=False)

    adapter._verify_default_model(mock_page)

    assert picker.inner_text.call_count == 2
    adapter._model_policy.ensure_default_model.assert_called_once_with(mock_page)


def _navigate_fixture(mock_page: MagicMock, model_text: str) -> MagicMock:
    """Shared navigate_to_chat page mock: authenticated URL + model picker text."""

    mock_page.url = "https://chat.qwen.ai/"
    loc = MagicMock()
    loc.count.return_value = 0
    loc.first.is_visible.return_value = False
    loc.first.is_enabled.return_value = False
    mock_page.locator.return_value = loc
    mock_page.query_selector.return_value = MagicMock()
    mock_page.get_by_role.return_value.inner_text.return_value = model_text
    # No in-page expiry banner: body is clean and no login/expired shells show.
    mock_page.inner_text.return_value = ""
    dom_helper.is_any_visible = lambda page, selectors: False
    return MagicMock(spec=LifecycleEmitter)


def test_verify_default_model_fallback_event_payload() -> None:
    """navigate_to_chat marks EVENT_MODEL_VERIFIED fallback=True when a
    different model is readable, instead of aborting the pipeline."""
    mock_page = MagicMock()
    emitter = _navigate_fixture(mock_page, "Select Model Qwen3.7-Plus")
    adapter = _adapter()
    adapter._navigation._goto_chat = MagicMock()
    adapter._navigation._start_new_chat = MagicMock()
    adapter._model_policy.wait_for_picker_ready = MagicMock()
    adapter._model_policy.ensure_default_model = MagicMock(return_value=False)

    adapter.navigate_to_chat(mock_page, emitter)

    verified_args, _ = emitter.emit.call_args
    assert verified_args[0] == EVENT_MODEL_VERIFIED
    assert verified_args[1]["model"] == "Select Model Qwen3.7-Plus"
    assert verified_args[1]["fallback"] is True


def test_verify_default_model_ok_event_payload() -> None:
    from modules.shared.src.common.taxonomy_core_constant import DEFAULT_MODEL

    mock_page = MagicMock()
    emitter = _navigate_fixture(mock_page, f"Select Model {DEFAULT_MODEL}")
    adapter = _adapter()
    adapter._navigation._goto_chat = MagicMock()
    adapter._navigation._start_new_chat = MagicMock()
    adapter._model_policy.wait_for_picker_ready = MagicMock()
    adapter._model_policy.ensure_default_model = MagicMock(return_value=True)

    adapter.navigate_to_chat(mock_page, emitter)

    verified_args, _ = emitter.emit.call_args
    assert verified_args[1]["model"] == DEFAULT_MODEL
    assert verified_args[1]["fallback"] is False


def test_verify_default_model_ok():
    from modules.shared.src.common.taxonomy_core_constant import DEFAULT_MODEL

    mock_page = MagicMock()
    mock_page.get_by_role.return_value.inner_text.return_value = f"Select Model {DEFAULT_MODEL}"

    # Must not raise when the picker reports the hardcoded default.
    verified, detected = _adapter()._verify_default_model(mock_page)

    assert verified is True
    assert detected == DEFAULT_MODEL


def test_verify_default_model_falls_back_on_mismatch():
    """A readable non-default model degrades gracefully instead of aborting (issue #374).

    The active model is not in the picker's offer list, so ``_select_first_available_model``
    (issue #283 AC-2) is tried first; when the picker reports it is not visible the
    readable-but-different label is returned with ``verified=False`` instead of raising.
    """
    mock_page = MagicMock()
    mock_page.locator.return_value.first.is_visible.return_value = False
    mock_page.get_by_role.return_value.inner_text.return_value = "Select Model Qwen3.7-Plus"

    verified, detected = _adapter()._verify_default_model(mock_page)

    assert verified is False
    assert detected == "Select Model Qwen3.7-Plus"


def test_verify_default_model_rejects_superstring_model():
    """A similarly-named model (e.g. Qwen3.8-Max-X) must NOT pass the gate as the default."""
    mock_page = MagicMock()
    mock_page.locator.return_value.first.is_visible.return_value = False
    mock_page.get_by_role.return_value.inner_text.return_value = "Select Model Qwen3.8-Max-Plus"

    verified, detected = _adapter()._verify_default_model(mock_page)

    assert verified is False
    assert "Qwen3.8-Max-Plus" in detected


def test_verify_default_model_retries_when_switch_reported_failure():
    from modules.shared.src.common.taxonomy_core_constant import DEFAULT_MODEL

    mock_page = MagicMock()
    # First read shows the old model; the retry re-runs ensure_default_model,
    # after which the picker reports the default model.
    inner_texts = iter(["Select Model Qwen3.7-Plus", f"Select Model {DEFAULT_MODEL}"])

    def _fake_inner_text():
        return next(inner_texts)

    mock_page.get_by_role.return_value.inner_text.side_effect = _fake_inner_text

    # Must not raise: the retry path fixes the mismatch.
    verified, detected = _adapter()._verify_default_model(mock_page, require_switch=False)

    assert verified is True
    assert detected == DEFAULT_MODEL


def test_verify_default_model_raises_when_unreadable():
    from playwright.sync_api import Error as PwError

    from modules.shared.src.common.taxonomy_core_error import ModelSwitchError

    mock_page = MagicMock()
    mock_page.get_by_role.return_value.wait_for.side_effect = PwError("picker gone")
    # Ensure the fallback path also cannot read the picker so the full
    # exception stack is exercised.
    mock_page.locator.return_value.first.is_visible.return_value = False

    with pytest.raises(ModelSwitchError, match="Cannot read active model"):
        _adapter()._verify_default_model(mock_page)


MODEL_SELECTOR_BUTTON_NAME = "Select Model"


def test_is_third_party_noise_returns_true_for_known_domains():
    assert _is_third_party_noise("https://www.google.com/measurement/conversion")
    assert _is_third_party_noise("https://analytics.google.com/g/collect")
    assert _is_third_party_noise("https://img.alicdn.com/imgextra/x.png")
    assert _is_third_party_noise("https://aplus.qwen.ai/v.gif")


def test_is_third_party_noise_returns_false_for_qwen_domains():
    assert not _is_third_party_noise("https://chat.qwen.ai/")
    assert not _is_third_party_noise("https://api.qwen.ai/completion")


# ── login_form_selector regression tests ─────────────────────────────────────


def test_login_form_selectors_do_not_include_class_wildcards():
    """[class*='login'] and [class*='passport'] were false positives that
    triggered AuthRequiredError on the authenticated chat page (avatar menu,
    .login-info elements, etc.).  They must not appear in the tuple."""
    from modules.shared.src.common.taxonomy_core_constant import LOGIN_FORM_SELECTORS

    for sel in LOGIN_FORM_SELECTORS:
        assert "[class*='login']" not in sel, f"false-positive selector still present: {sel}"
        assert "[class*='passport']" not in sel, f"false-positive selector still present: {sel}"


def test_assert_on_chat_page_no_false_positive_when_class_wildcards_absent():
    """When the DOM has elements with .login-info / .login class but no actual
    login form, _assert_on_chat_page must NOT raise AuthRequiredError.

    We patch is_any_visible to return True only if the combined selector
    string contains the old false-positive patterns, simulating the bug."""

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_page.query_selector.return_value = MagicMock()  # textarea present

    def fake_is_any_visible(page, selectors):
        # Simulate the old behaviour: if [class*='login'] or [class*='passport']
        # is in the combined string, return True (false positive); otherwise False.
        return "[class*='login'" in selectors or "[class*='passport'" in selectors

    with patch.object(dom_helper, "is_any_visible", side_effect=fake_is_any_visible):
        # Must NOT raise — the bug fix removes the false-positive selectors,
        # so fake_is_any_visible returns False and the check passes.
        session_check_util.assert_on_chat_page(mock_page)


def test_assert_on_chat_page_happy_path_no_login_form_visible():
    """No login form selectors match and textarea is present → no exception."""

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_page.query_selector.return_value = MagicMock()  # textarea present

    with patch.object(dom_helper, "is_any_visible", return_value=False):
        # Should complete without raising AuthRequiredError.
        session_check_util.assert_on_chat_page(mock_page)


def test_login_form_selectors_do_not_include_has_text_buttons():
    """button:has-text / a:has-text selectors (Log in, Sign in, Sign up) are
    visible on the authenticated Qwen chat page nav bar.  They must not appear
    in LOGIN_FORM_SELECTORS or _assert_on_chat_page will raise a false-positive
    AuthRequiredError."""
    from modules.shared.src.common.taxonomy_core_constant import LOGIN_FORM_SELECTORS

    for sel in LOGIN_FORM_SELECTORS:
        assert ":has-text(" not in sel, f"false-positive has-text selector still present: {sel}"


def test_assert_on_chat_page_no_false_positive_when_signin_button_visible():
    """Qwen's authenticated chat page shows a 'Sign in' anchor in the nav bar
    (for account switching).  Simulate that DOM: is_any_visible returns True
    only for the old has-text patterns, so it must NOT raise when those
    patterns are absent from the combined selector string."""

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_page.query_selector.return_value = MagicMock()  # textarea present

    def fake_is_any_visible(page, selectors):
        old_fp_patterns = ("has-text('Log in')", "has-text('Sign in')", "has-text('Sign up')")
        return any(p in selectors for p in old_fp_patterns)

    with patch.object(dom_helper, "is_any_visible", side_effect=fake_is_any_visible):
        # Must NOT raise — the has-text selectors have been removed.
        session_check_util.assert_on_chat_page(mock_page)


def test_err_failed_in_noise_patterns_is_lowercase():
    """_NOISE_CONSOLE_PATTERNS must use lowercase 'err_failed' so the
    .lower()-normalised console text actually matches.  Uppercase patterns
    in a frozenset compared against lower-cased text will never match."""

    assert "err_failed" in _NOISE_CONSOLE_PATTERNS
    assert "ERR_FAILED" not in _NOISE_CONSOLE_PATTERNS, (
        "uppercase 'ERR_FAILED' will never match lower-cased console text"
    )


# ── in-page session-expired banner regression tests ──────────────────────────


def test_raise_if_session_expired_raises_on_in_page_expiration_banner():
    """An in-page 'session expired' notice (no login URL redirect, no login
    form) must raise AuthRequiredError with session_expired=True."""

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_page.locator.return_value.count.return_value = 0
    mock_page.query_selector.return_value = MagicMock()  # textarea present
    mock_page.inner_text.return_value = "Session expired, please login again"

    with patch.object(dom_helper, "is_any_visible", return_value=False):
        with pytest.raises(AuthRequiredError, match="Session expired") as exc_info:
            _raise_if_session_expired(mock_page)

    assert exc_info.value.session_expired is True


def test_detect_session_expired_banner_no_false_positive_on_normal_chat_body():
    """Normal chat body text without any expiry keyword must not flag the banner."""

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_page.locator.return_value.count.return_value = 0
    mock_page.query_selector.return_value = MagicMock()  # textarea present
    mock_page.inner_text.return_value = "Ask Qwen anything"

    with patch.object(dom_helper, "is_any_visible", return_value=False):
        assert _in_page_expiry_banner_visible(mock_page) is False


def test_raise_if_session_expired_raises_on_live_token_expired_banner():
    """The banner the site actually renders ('Token has expired, please log in
    again') must raise AuthRequiredError tagged session_expired. The 'token has
    expired' phrase is a substring keyword, so it fires even when the trailing
    'log in again' wording is absent or localized."""

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_page.locator.return_value.count.return_value = 0
    mock_page.query_selector.return_value = MagicMock()  # textarea present
    mock_page.inner_text.return_value = "Token has expired, please log in again"

    with patch.object(dom_helper, "is_any_visible", return_value=False):
        with pytest.raises(AuthRequiredError, match="Session expired") as exc_info:
            _raise_if_session_expired(mock_page)

    assert exc_info.value.session_expired is True


def test_raise_if_session_expired_raises_on_token_has_expired_alone():
    """A banner carrying only 'Token has expired.' (no 'log in again') still
    fires the expiry raise via the dedicated keyword."""

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_page.locator.return_value.count.return_value = 0
    mock_page.query_selector.return_value = MagicMock()  # textarea present
    mock_page.inner_text.return_value = "Token has expired."

    with patch.object(dom_helper, "is_any_visible", return_value=False):
        with pytest.raises(AuthRequiredError, match="Session expired") as exc_info:
            _raise_if_session_expired(mock_page)

    assert exc_info.value.session_expired is True


def test_detect_session_expired_banner_skips_when_body_unreadable():
    """A DOM that is still hydrating (inner_text raises) is not a signal —
    the check is skipped rather than masking a genuine auth problem."""
    from playwright.sync_api import Error as PwError

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_page.locator.return_value.count.return_value = 0
    mock_page.query_selector.return_value = MagicMock()
    mock_page.inner_text.side_effect = PwError("DOM not hydrated yet")

    with patch.object(dom_helper, "is_any_visible", return_value=False):
        assert _in_page_expiry_banner_visible(mock_page) is False


# ── detect_session_expired protocol method tests ─────────────────────────────


def test_detect_session_expired_returns_true_on_token_expired_banner():
    """The live 'Token has expired' banner must flag the session as expired."""

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_page.inner_text.return_value = "Token has expired, please log in again"

    with patch.object(dom_helper, "is_any_visible", return_value=False):
        assert _adapter().detect_session_expired(mock_page) is True


def test_detect_session_expired_returns_false_on_clean_page():
    """A clean chat body (no keyword, no visible banner shell) is not expired."""

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_page.inner_text.return_value = "Hello, here is a response."

    with patch.object(dom_helper, "is_any_visible", return_value=False):
        assert _adapter().detect_session_expired(mock_page) is False


def test_detect_session_expired_returns_false_when_body_unreadable():
    """An unreadable DOM (inner_text raises) is not a signal — returns False."""
    from playwright.sync_api import Error as PwError

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_page.inner_text.side_effect = PwError("DOM not hydrated yet")

    with patch.object(dom_helper, "is_any_visible", return_value=False):
        assert _adapter().detect_session_expired(mock_page) is False


def test_detect_session_expired_fires_on_banner_shell_selector():
    """A visible expiry banner shell (no keyword text) must flag the session."""

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_page.inner_text.return_value = ""

    def _banner_probe(_page, selectors):
        import modules.shared.src.common.taxonomy_core_constant as const

        return selectors == ", ".join(const.SESSION_EXPIRED_BANNER_SELECTORS)

    with patch.object(dom_helper, "is_any_visible", side_effect=_banner_probe):
        assert _adapter().detect_session_expired(mock_page) is True


def test_navigate_to_chat_emits_session_expired_before_propagation():
    """In-page banner path: EVENT_SESSION_EXPIRED is emitted with the banner
    reason before AuthRequiredError propagates to the orchestrator."""

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_page.inner_text.return_value = "Your session has expired. Please login again"
    mock_page.query_selector.return_value = None
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    with patch.object(dom_helper, "is_any_visible", return_value=False):
        with pytest.raises(AuthRequiredError, match="Session expired") as exc_info:
            _adapter().navigate_to_chat(mock_page, mock_emitter)

    assert exc_info.value.session_expired is True
    emitted = [call.args for call in mock_emitter.emit.call_args_list]
    assert (EVENT_SESSION_EXPIRED, {"url": "https://chat.qwen.ai/", "reason": "in_page_banner"}) in emitted


def test_navigate_to_chat_no_session_expired_emit_on_redirect_case():
    """A URL redirect to login (not the in-page banner) must NOT emit
    EVENT_SESSION_EXPIRED and the error must not carry session_expired."""

    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/passport/login"
    mock_page.locator.return_value.count.return_value = 0
    mock_page.inner_text.return_value = "login"
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    with patch.object(dom_helper, "is_any_visible", return_value=False):
        with pytest.raises(AuthRequiredError, match="Not authenticated") as exc_info:
            _adapter().navigate_to_chat(mock_page, mock_emitter)

    assert exc_info.value.session_expired is False
    emitted = [call.args[0] for call in mock_emitter.emit.call_args_list]
    assert EVENT_SESSION_EXPIRED not in emitted
