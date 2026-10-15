"""Shared fixture and helper support for qwen-web-arwaky tests.

This package is NOT a pytest root. Pytest suites live in
``modules/<name>/tests/``; this package holds the pieces they share:

- ``conftest.py`` — shared browser/behavior fixtures for the local fixture page
- ``pipeline_fixtures.py`` — fixture state management (``restore_fixture_state``)
- ``helpers.py`` — thin named wrappers imported by module test dirs
- ``fixtures/`` — real-session test fixtures (fast/slow variants per pipeline)
"""
