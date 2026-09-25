"""Unit tests for utility_core_env — the environment variable contract (issue #292).

Locks the four behaviours the registry exists to guarantee: every recognized
variable is documented with a purpose and default, secret values never reach
output unmasked, a typo'd ``QWEN_*`` name is reported instead of silently
selecting a different runtime mode, and malformed values are surfaced as
validation problems.
"""

from __future__ import annotations

from modules.shared.src.utility_core_env import (
    ENVIRONMENT,
    QWEN_DEFAULT_MODEL,
    QWEN_SWARM_CONCURRENCY,
    QWEN_WEB_GITHUB_REPO,
    QWEN_WEB_MAX_WORKERS,
    QWEN_WORKSPACE_ROOT,
    SENTRY_DSN,
    effective_config,
    get_secret_env,
    is_secret,
    registered_env,
    runbook_index,
    unknown_env_vars,
    validate_env,
)


def test_registry_documents_every_variable_with_purpose_and_default():
    entries = registered_env()
    assert entries
    for name, purpose, default, secret in entries:
        assert name, "every registry entry needs a name"
        assert purpose, f"{name} needs a documented purpose"
        assert isinstance(default, str), f"{name} needs a string default"
        assert isinstance(secret, bool), f"{name} needs an explicit sensitivity label"


def test_registry_names_are_unique():
    names = [entry[0] for entry in registered_env()]
    assert len(names) == len(set(names))


def test_sentry_dsn_is_the_only_secret():
    assert is_secret(SENTRY_DSN)
    assert not is_secret(ENVIRONMENT)
    assert not is_secret(QWEN_WEB_MAX_WORKERS)


def test_effective_config_masks_a_set_secret():
    config = effective_config({SENTRY_DSN: "https://public:secret@o1.ingest.sentry.io/9"})
    assert config[SENTRY_DSN] == "***"


def test_effective_config_never_masks_an_unset_secret():
    config = effective_config({})
    assert config[SENTRY_DSN] == ""


def test_effective_config_falls_back_to_the_registry_default():
    config = effective_config({})
    assert config[QWEN_WEB_GITHUB_REPO] == "rakaarwaky/qwen-web-arwaky"
    assert config[QWEN_WEB_MAX_WORKERS] == "auto"


def test_effective_config_prefers_the_process_value():
    config = effective_config({QWEN_WEB_MAX_WORKERS: "4"})
    assert config[QWEN_WEB_MAX_WORKERS] == "4"


def test_get_secret_env_rejects_an_unregistered_name():
    try:
        get_secret_env("QWEN_NOT_REGISTERED")
    except KeyError:
        return
    raise AssertionError("an unregistered variable must not be read as a secret")


def test_unknown_env_vars_reports_a_typo():
    unknown = unknown_env_vars({QWEN_WEB_MAX_WORKERS: "4", "QWEN_WEB_MAX_WORKS": "4", "PATH": "/bin"})
    assert unknown == ("QWEN_WEB_MAX_WORKS",)


def test_unknown_env_vars_ignores_non_qwen_names():
    assert unknown_env_vars({"HOME": "/root", "OTEL_SERVICE_NAME": "qwen-web"}) == ()


def test_unknown_env_vars_is_empty_for_a_clean_environment():
    assert unknown_env_vars({}) == ()


def test_validate_env_accepts_a_clean_environment():
    assert validate_env({}) == ()


def test_validate_env_rejects_a_non_integer_worker_count():
    problems = validate_env({QWEN_WEB_MAX_WORKERS: "many"})
    assert any(QWEN_WEB_MAX_WORKERS in problem for problem in problems)


def test_validate_env_rejects_a_malformed_github_repo():
    problems = validate_env({QWEN_WEB_GITHUB_REPO: "not-a-repo-path"})
    assert any(QWEN_WEB_GITHUB_REPO in problem for problem in problems)


def test_validate_env_rejects_a_negative_stream_timeout():
    problems = validate_env({"QWEN_STREAM_SAFETY_TIMEOUT_SEC": "-5"})
    assert any("QWEN_STREAM_SAFETY_TIMEOUT_SEC" in problem for problem in problems)


def test_validate_env_rejects_a_relative_workspace_root():
    problems = validate_env({QWEN_WORKSPACE_ROOT: "relative/path"})
    assert any(QWEN_WORKSPACE_ROOT in problem for problem in problems)


def test_validate_env_rejects_an_overlong_model_name():
    problems = validate_env({QWEN_DEFAULT_MODEL: "x" * 129})
    assert any(QWEN_DEFAULT_MODEL in problem for problem in problems)


def test_validate_env_accepts_valid_overrides():
    env = {
        QWEN_WEB_MAX_WORKERS: "4",
        QWEN_SWARM_CONCURRENCY: "2",
        QWEN_WEB_GITHUB_REPO: "owner/name",
        QWEN_WORKSPACE_ROOT: "/srv/work",
    }
    assert validate_env(env) == ()


def test_runbook_index_covers_the_incident_categories():
    index = runbook_index()
    for category in ("auth", "browser", "file_io", "session", "update"):
        assert index[category].startswith("docs/runbooks/")
        assert index[category].endswith(".md")
