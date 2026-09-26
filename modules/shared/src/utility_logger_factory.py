"""Logger factory utility.

Utility layer (utility_logger_factory): provide logger retrieval without
making Capabilities depend on Observability Capability.
"""

from __future__ import annotations

import logging
from typing import Any


def get_logger(name: str) -> Any:
    """Return a bound logger instance.

    Parameters
    ----------
    name : str
        Logger name (typically the module or class name).

    Returns
    -------
    Any
        Bound logger object.

    """
    return logging.getLogger(name)
