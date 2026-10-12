"""Tests for main.py — workspace initialization (run_init).

The superset regression tests for ``init_workspace`` live in
``integration_surface_init_cmd.py`` (TestQwaInit); the fine-grained
subset tests from this file were removed in the quality-over-quantity
prune because each is subsumed by ``test_run_init_creates_structure``
or ``test_run_init_idempotent_and_existing_gitignore``.
"""

from __future__ import annotations
