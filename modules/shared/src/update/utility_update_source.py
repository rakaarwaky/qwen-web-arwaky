"""Update source-detection helpers (utility layer).

Editable-install and source-checkout detection, split out of
``utility_update_pipeline.py``. ``resolve_editable_source_dir`` finds a
PEP 610 editable install (via the dist's ``direct_url.json``) or a cwd
checkout; ``read_source_version`` reads that checkout's declared version
without importing its code.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from importlib import metadata
from pathlib import Path
from urllib.parse import unquote, urlparse

__all__ = [
    "read_source_version",
    "resolve_editable_source_dir",
]

log = logging.getLogger("utility_update_source")


def read_source_version(source_dir: Path) -> str | None:
    """Read a checkout's root project version without importing its code."""
    with contextlib.suppress(OSError):
        content = (source_dir / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
        match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def resolve_editable_source_dir(package_name: str) -> Path | None:
    """Detect a PEP 610 editable install or fall back to a cwd source checkout."""
    dist = None
    try:
        dist = metadata.distribution(package_name)
    except metadata.PackageNotFoundError:
        dist = None
    except Exception as exc:
        log.debug("distribution_lookup_failed error=%s", exc)
    if dist is not None:
        raw: str | None = None
        with contextlib.suppress(Exception):
            raw = dist.read_text("direct_url.json")
        if raw:
            with contextlib.suppress(ValueError, TypeError, KeyError, OSError):
                data = json.loads(raw)
                if isinstance(data, dict) and (data.get("dir_info") or {}).get("editable") is True:
                    parsed = urlparse(str(data.get("url", "")))
                    if parsed.scheme == "file":
                        candidate = Path(unquote(parsed.path))
                        if candidate.is_dir():
                            return candidate
    cwd = Path.cwd()
    pyproject = cwd / "pyproject.toml"
    if pyproject.is_file() and (cwd / "modules").is_dir():
        with contextlib.suppress(OSError):
            content = pyproject.read_text(encoding="utf-8", errors="ignore")
            if re.search(rf"name\s*=\s*[\"']{re.escape(package_name)}[\"']", content):
                return cwd
    return None
