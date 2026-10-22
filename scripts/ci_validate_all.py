#!/usr/bin/env python3
"""CI validation: every name in modules/shared/src/__init__.py __all__ must
exist as an attribute of the module (no phantom or removed symbols).

Run from the repo root:
    uv run python scripts/ci_validate_all.py

Exits 0 when every __all__ entry passes hasattr; exits 1 with a printed list
of missing names otherwise. Wired into CI as a guard against stale __all__
entries (e.g. phantom aggregate names or bare package re-exports).
"""

from __future__ import annotations

import sys


def main() -> int:
    import modules.shared.src as mod

    all_names = getattr(mod, "__all__", None)
    if all_names is None:
        print("FAIL: modules.shared.src has no __all__", file=sys.stderr)
        return 1

    missing = [name for name in all_names if not hasattr(mod, name)]
    if missing:
        print(f"FAIL: {len(missing)} name(s) in __all__ missing as module attribute(s):", file=sys.stderr)
        for name in missing:
            print(f"  - {name}", file=sys.stderr)
        return 1

    print(f"OK: all {len(all_names)} __all__ entries exist as module attributes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())