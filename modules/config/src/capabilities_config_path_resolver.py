"""Capabilities: config path resolution (AES403).

Implements ``IConfigPathResolverProtocol``.

Owns "where does this config point, and can the host use it". Before this
seam the doctor probed ``DEFAULT_OUTPUT`` for writability inline, the prompt
adapters derived output filenames through the factory, and the session
storage resolved its own root — three places answering the same question.
"""

from __future__ import annotations

import time
from pathlib import Path

from modules.shared.src.contract_config_protocol import IConfigPathResolverProtocol
from modules.shared.src.taxonomy_config_vo import ConfigIssue, ResolvedConfigPath, ResolvedConfigPaths
from modules.shared.src.taxonomy_core_vo import AppConfig

#: The config fields that name a filesystem location, paired with whether the
#: run writes to them. A read-only field only has to exist; a written field
#: also has to accept a write.
_PATH_ROLES: tuple[tuple[str, bool], ...] = (
    ("output_path", True),
    ("log_path", True),
    ("session_path", True),
    ("input_path", False),
    ("prompt_file", False),
    ("file_path", False),
    ("storage_state_file", False),
)


class ConfigPathResolver(IConfigPathResolverProtocol):
    """Resolve a config's paths and verify the host can use each one."""

    def resolve_paths(self, app_config: AppConfig) -> ResolvedConfigPaths:
        """Return every path *app_config* names, with existence and writability verified.

        A directory the run has not created yet is not a problem: the
        writable column reports whether the nearest existing ancestor
        accepts a write, which is what decides whether creating the
        directory will succeed.
        """
        resolved: list[ResolvedConfigPath] = []
        issues: list[ConfigIssue] = []
        for field, written in _PATH_ROLES:
            raw = getattr(app_config, field, None)
            if raw is None:
                continue
            path = Path(raw)
            exists = path.exists()
            writable = self._writable(path) if written else True
            if written and not writable:
                issues.append(
                    ConfigIssue(
                        field=field,
                        message=f"{field} cannot be written: {_writable_reason(path)}",
                        severity="error",
                        category="file_io",
                    )
                )
            elif not written and not exists:
                issues.append(
                    ConfigIssue(
                        field=field,
                        message=f"{field} {path} does not exist",
                        severity="warning",
                        category="file_io",
                    )
                )
            resolved.append(ResolvedConfigPath(role=field, path=path, exists=exists, writable=writable))
        return ResolvedConfigPaths(paths=tuple(resolved), issues=tuple(issues))

    @staticmethod
    def _writable(path: Path) -> bool:
        """Return True when the nearest existing ancestor of *path* accepts a write.

        Walking up is what lets a not-yet-created output directory pass: the
        decision is made on the parent that actually exists today, because
        that is what determines whether ``mkdir`` will succeed.
        """
        probe_dir = path if path.is_dir() else path.parent
        for candidate in (probe_dir, *probe_dir.parents):
            if candidate.is_dir():
                return _can_write(candidate)
        return False


def _can_write(directory: Path) -> bool:
    """Return True when the process can create and remove a file in *directory*."""
    nonce = str(time.time_ns() % 100000000)
    probe = directory / f".qwa_path_probe_{nonce}"
    try:
        probe.write_text("ok", encoding="utf-8")
        return True
    except OSError:
        return False
    finally:
        probe.unlink(missing_ok=True)


def _writable_reason(path: Path) -> str:
    """Return the sentence explaining why *path* cannot be written."""
    probe_dir = path if path.is_dir() else path.parent
    for candidate in (probe_dir, *probe_dir.parents):
        if candidate.is_dir():
            return f"nearest existing directory {candidate} rejects writes"
    return f"no existing parent directory above {path}"


__all__ = ["ConfigPathResolver"]
