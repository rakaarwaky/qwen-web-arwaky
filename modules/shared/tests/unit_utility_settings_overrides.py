"""Unit tests for utility_core_env — the persisted override file.

Locks the four behaviours the Settings screen depends on: the file holds
overrides only and never invents a default, a value the registry rejects never
reaches the process environment, a hand-edited or absent file cannot stop the
application from starting, and a real export outranks the stored file.
"""

from __future__ import annotations

import os
from pathlib import Path

from modules.shared.src.utility_core_env import (
    clear_settings,
    install_settings,
    load_settings,
    parse_settings,
    save_settings,
    settings_path,
)


def test_settings_path_sits_under_the_xdg_config_home():
    assert settings_path().name == "settings.env"
    assert settings_path().parent.name == "qwen-web-arwaky"


def test_parse_keeps_registered_names_and_drops_the_rest():
    parsed = parse_settings(
        "# a comment\n\nQWEN_WEB_MAX_WORKERS=4\nNOT_A_SETTING=1\nQTEN_WEB_MAX_WORKERS=9\nnot an assignment\n"
    )
    assert parsed == {"QWEN_WEB_MAX_WORKERS": "4"}


def test_parse_strips_quotes_around_a_value():
    assert parse_settings('QWEN_WEB_GITHUB_REPO="owner/repo"\n') == {"QWEN_WEB_GITHUB_REPO": "owner/repo"}


def test_parse_drops_a_value_the_registry_would_reject():
    # A non-numeric worker count would be reported by doctor, so storing it
    # would mean a restart behaves differently from the session that typed it.
    assert parse_settings("QWEN_WEB_MAX_WORKERS=four\n") == {}


def test_parse_accepts_a_valid_worker_count():
    assert parse_settings("QWEN_WEB_MAX_WORKERS=4\n") == {"QWEN_WEB_MAX_WORKERS": "4"}


def test_load_settings_is_empty_when_the_file_is_absent(tmp_path: Path):
    assert load_settings(tmp_path / "nope.env") == {}


def test_load_settings_survives_an_unreadable_file(tmp_path: Path):
    # A config typo must not stop the application from starting.
    target = tmp_path / "settings.env"
    target.write_bytes(b"\xff\xfe\x00broken")
    assert load_settings(target) == {}


def test_save_then_load_round_trips_the_overrides(tmp_path: Path):
    target = tmp_path / "settings.env"
    save_settings({"QWEN_DEFAULT_MODEL": "qwen3-max"}, target)
    assert load_settings(target) == {"QWEN_DEFAULT_MODEL": "qwen3-max"}


def test_save_writes_a_self_describing_header(tmp_path: Path):
    target = tmp_path / "settings.env"
    save_settings({"QWEN_DEFAULT_MODEL": "qwen3-max"}, target)
    assert target.read_text(encoding="utf-8").startswith("# qwen-web-arwaky runtime overrides.")


def test_save_rewrites_the_whole_set_so_a_removed_override_goes_away(tmp_path: Path):
    target = tmp_path / "settings.env"
    save_settings({"QWEN_DEFAULT_MODEL": "qwen3-max", "QWEN_WEB_MAX_WORKERS": "4"}, target)
    save_settings({"QWEN_DEFAULT_MODEL": "qwen3-max"}, target)
    assert load_settings(target) == {"QWEN_DEFAULT_MODEL": "qwen3-max"}


def test_save_drops_an_invalid_entry_instead_of_storing_it(tmp_path: Path):
    target = tmp_path / "settings.env"
    save_settings({"QWEN_WORKSPACE_ROOT": "relative/path"}, target)
    assert load_settings(target) == {}


def test_install_settings_populates_a_missing_variable(tmp_path: Path):
    target = tmp_path / "settings.env"
    save_settings({"QWEN_DEFAULT_MODEL": "qwen3-max"}, target)
    env: dict[str, str] = {}
    assert install_settings(target, env=env) == {"QWEN_DEFAULT_MODEL": "qwen3-max"}
    assert env["QWEN_DEFAULT_MODEL"] == "qwen3-max"


def test_install_settings_lets_a_real_export_win(tmp_path: Path):
    # A shell export is the operator's most explicit statement of intent, so
    # it outranks whatever the file happens to hold.
    target = tmp_path / "settings.env"
    save_settings({"QWEN_DEFAULT_MODEL": "from-file"}, target)
    env = {"QWEN_DEFAULT_MODEL": "from-shell"}
    assert install_settings(target, env=env) == {}
    assert env["QWEN_DEFAULT_MODEL"] == "from-shell"


def test_install_settings_skips_an_empty_stored_value(tmp_path: Path):
    target = tmp_path / "settings.env"
    target.write_text("QWEN_DEFAULT_MODEL=\n", encoding="utf-8")
    env: dict[str, str] = {}
    assert install_settings(target, env=env) == {}
    assert "QWEN_DEFAULT_MODEL" not in env


def test_install_settings_ignores_a_blank_value_in_the_real_environment(tmp_path: Path):
    target = tmp_path / "settings.env"
    save_settings({"QWEN_DEFAULT_MODEL": "qwen3-max"}, target)
    env = {"QWEN_DEFAULT_MODEL": "   "}
    install_settings(target, env=env)
    assert env["QWEN_DEFAULT_MODEL"] == "qwen3-max"


def test_clear_settings_drops_the_named_override_from_file_and_environment(tmp_path: Path):
    target = tmp_path / "settings.env"
    save_settings({"QWEN_DEFAULT_MODEL": "qwen3-max", "QWEN_WEB_MAX_WORKERS": "4"}, target)
    os.environ["QWEN_WEB_MAX_WORKERS"] = "4"
    try:
        clear_settings(["QWEN_WEB_MAX_WORKERS"], target)
        assert "QWEN_WEB_MAX_WORKERS" not in os.environ
    finally:
        os.environ.pop("QWEN_WEB_MAX_WORKERS", None)
    assert load_settings(target) == {"QWEN_DEFAULT_MODEL": "qwen3-max"}


def test_an_override_survives_a_restart_through_the_file(tmp_path: Path):
    # The behaviour the Settings screen promises: apply, quit, relaunch, and
    # the value is still in force.
    target = tmp_path / "settings.env"
    save_settings({"QWEN_REQUEST_TIMEOUT_SEC": "900"}, target)
    env: dict[str, str] = {}
    install_settings(target, env=env)
    assert env["QWEN_REQUEST_TIMEOUT_SEC"] == "900"
