"""Shared update feature files (taxonomy, contract, utility).

AES layer is the filename prefix, not the directory name.

The update utilities are split by concern so a capability that only
compares versions does not also pull in the subprocess sandbox and the
GitHub client: ``utility_update_version``, ``utility_update_github``,
``utility_update_subprocess``, ``utility_update_chromium``,
``utility_update_source``, and ``utility_update_refusal``. This package
init re-exports the historical ``utility_update_pipeline`` names for
callers that still import them as a group.
"""

from __future__ import annotations

from modules.shared.src.update.utility_update_chromium import (
    chromium_present,
    playwright_browsers_path,
    purge_chromium_cache,
)
from modules.shared.src.update.utility_update_github import (
    github_repo_name,
    github_repo_pattern,
    resolve_github_pinned_url,
)
from modules.shared.src.update.utility_update_refusal import (
    refuse_unverified_install,
    smoke_gate_unavailable,
)
from modules.shared.src.update.utility_update_source import (
    read_source_version,
    resolve_editable_source_dir,
)
from modules.shared.src.update.utility_update_subprocess import (
    SUBPROCESS_FORBIDDEN_CHARS,
    approved_spawn_command,
    decode_output,
    run_pip_show,
    run_subprocess,
    tail,
)
from modules.shared.src.update.utility_update_version import (
    compare_versions,
    version_unresolvable,
)

__all__ = [
    "SUBPROCESS_FORBIDDEN_CHARS",
    "approved_spawn_command",
    "chromium_present",
    "compare_versions",
    "decode_output",
    "github_repo_name",
    "github_repo_pattern",
    "playwright_browsers_path",
    "purge_chromium_cache",
    "read_source_version",
    "refuse_unverified_install",
    "resolve_editable_source_dir",
    "resolve_github_pinned_url",
    "run_pip_show",
    "run_subprocess",
    "smoke_gate_unavailable",
    "tail",
    "version_unresolvable",
]
