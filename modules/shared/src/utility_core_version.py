"""Utility: package version resolution (AES201).

Dynamically resolves the application version from pyproject.toml or
importlib.metadata, eliminating hardcoded version numbers across the codebase.
"""

from __future__ import annotations

import contextlib
import importlib.metadata
import re
from pathlib import Path

PACKAGE_NAME = "qwen-web-arwaky"
_PYPROJECT_PATH = Path(__file__).resolve().parents[3] / "pyproject.toml"


def get_package_version(package_name: str = PACKAGE_NAME) -> str:
    """Return the current application version dynamically.

    Resolution strategy:
      1. Parse `version = "..."` directly from pyproject.toml if present.
      2. Fallback to `importlib.metadata.version(package_name)`.
      3. Fallback to "0.0.0-dev".
    """
    if _PYPROJECT_PATH.exists():
        with contextlib.suppress(Exception):
            content = _PYPROJECT_PATH.read_text(encoding="utf-8")
            match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
            if match:
                return match.group(1).strip()

    with contextlib.suppress(Exception):
        importlib.invalidate_caches()
        return importlib.metadata.version(package_name)

    return "0.0.0-dev"
