"""Prompt runtime layer: browser/stream capabilities (AES403)."""

# The `from .capabilities_* import ...` lines are added incrementally in PRs 2-4
# as each capability moves into this module; `__all__` documents the end-state.

__all__ = [
    "FileUploader",
    "PromptInjector",
    "SendDispatcher",
    "Saver",
    "StreamMonitor",
]
