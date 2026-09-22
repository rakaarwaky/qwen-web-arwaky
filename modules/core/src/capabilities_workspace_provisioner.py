"""Capabilities: workspace provisioner (AES403).

Implements IWorkspaceProtocol — workspace initialization with XDG directories,
SKILL.md provisioning, .qwen-web symlinks, and .gitignore management.
All file system I/O for workspace setup lives here.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

from modules.shared.src.contract_core_protocol import IWorkspaceProtocol
from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_JOBS_DIR,
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_SESSION,
    SWARM_OUTPUT_ROOT,
)
from modules.shared.src.taxonomy_core_vo import FilePath
from modules.shared.src.taxonomy_skill_constant import EMBEDDED_SKILL_MD

# Block 1: Class Definition & Constructor


class WorkspaceProvisioner(IWorkspaceProtocol):
    """Workspace directory provisioning with symlinks and .gitignore management."""

    def __init__(self) -> None:
        """Initialize WorkspaceProvisioner."""
        pass

    # ─── Block 2: Public Contract (IWorkspaceProtocol ONLY) ──
    def init_workspace(self, target_dir: FilePath) -> None:
        """Initialize workspace in 4 sequential steps:

        Step 1: Ensure XDG directories exist
        Step 2: Provision .agents/skills/qwen-web/SKILL.md from embedded constant
        Step 3: Provision .qwen-web directory with symlinks
        Step 4: Update .gitignore with .qwen-web/ entry
        """
        target_path = Path(str(target_dir)).resolve()

        # Step 1: Ensure XDG directories exist
        DEFAULT_JOBS_DIR.mkdir(parents=True, exist_ok=True)
        DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)
        DEFAULT_LOG.mkdir(parents=True, exist_ok=True)

        # Step 2: Create .agents/skills/qwen-web/SKILL.md from embedded constant
        skills_dir = target_path / ".agents" / "skills" / "qwen-web"
        skills_dir.mkdir(parents=True, exist_ok=True)
        skill_md_dest = skills_dir / "SKILL.md"
        skill_md_dest.write_text(EMBEDDED_SKILL_MD, encoding="utf-8")

        # Step 3: Create .qwen-web directory with symlinks to XDG paths
        dot_qwen = target_path / ".qwen-web"
        dot_qwen.mkdir(parents=True, exist_ok=True)

        links: dict[str, Any] = {
            "jobs": DEFAULT_JOBS_DIR,
            "log": DEFAULT_LOG,
            "output": DEFAULT_OUTPUT,
            "qwen_session": DEFAULT_SESSION,
            "swarm": SWARM_OUTPUT_ROOT,
        }

        for link_name, xdg_target in links.items():
            link_path = dot_qwen / link_name
            xdg_target.mkdir(parents=True, exist_ok=True)

            if link_path.is_symlink() or link_path.exists():
                if link_path.is_dir() and not link_path.is_symlink():
                    backup = dot_qwen / f"{link_name}.backup-{time.time_ns()}"
                    shutil.move(str(link_path), str(backup))
                else:
                    link_path.unlink(missing_ok=True)

            if not link_path.exists() and not link_path.is_symlink():
                try:
                    os.symlink(xdg_target, link_path, target_is_directory=True)
                except OSError:
                    link_path.mkdir(parents=True, exist_ok=True)

        # Step 4: Add .qwen-web/ to .gitignore
        git_ignore = target_path / ".gitignore"
        entry = ".qwen-web/"
        if git_ignore.exists():
            content = git_ignore.read_text(encoding="utf-8")
            if entry not in content and ".qwen-web" not in content:
                if content and not content.endswith("\n"):
                    content += "\n"
                content += f"{entry}\n"
                git_ignore.write_text(content, encoding="utf-8")
        else:
            git_ignore.write_text(f"{entry}\n", encoding="utf-8")

    # ─── Block 3: Dunder Methods, Factories & Helpers ─────

    def __repr__(self) -> str:
        """Return string representation of WorkspaceProvisioner."""
        return "WorkspaceProvisioner()"
