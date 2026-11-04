"""Shared fixture and helper support for qwen-web-arwaky tests.

This package is NOT a pytest root. Pytest suites live in
``modules/<name>/tests/``; this package holds the pieces they share:

- ``fixture_browser_conftest.py`` — shared browser/behavior fixtures for the local fixture page
- ``fixture_pipeline_state.py`` — fixture state management (``restore_fixture_state``)
- ``fixture_shared_helpers.py`` — thin named wrappers imported by module test dirs
- ``fixture_uat_records.py`` — deterministic UAT fixtures (evidence generators)
- ``acceptance_uat_fixtures.py`` — UAT fixture tests (acceptance semantics)
- ``fixtures/`` — real-session test fixtures (fast/slow variants per pipeline)
"""
