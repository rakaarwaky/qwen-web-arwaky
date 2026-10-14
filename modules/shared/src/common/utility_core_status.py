"""Status path utilities — canonical status file path derivation.

Taxonomy layer (utility): stateless functions, taxonomy imports only.
"""

from __future__ import annotations

from pathlib import Path

STATUS_FILENAME = "status.json"


def status_path_for(log_path: Path) -> Path:
    """Return the canonical path to the status JSON file for a given log directory.

    Parameters
    ----------
    log_path : Path
        Log directory path.

    Returns
    -------
    Path
        log_path / STATUS_FILENAME

    """
    return log_path / STATUS_FILENAME
