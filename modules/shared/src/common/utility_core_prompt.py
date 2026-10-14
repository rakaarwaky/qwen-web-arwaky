"""Prompt-handling pure utilities.

Taxonomy layer (utility): stateless functions, taxonomy imports only.
"""

from __future__ import annotations


def extract_prompt_text(content: str) -> str:
    """Strip YAML frontmatter header if present."""
    stripped = content.strip()
    if stripped.startswith("---"):
        parts = stripped.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return stripped


def strip_input_from_output(text: str, full_prompt: str) -> str:
    """Strip leaked input content from AI response."""
    if not text or not full_prompt:
        return text

    prompt_stripped = full_prompt.strip()
    text_stripped = text.strip()

    if text_stripped.startswith(prompt_stripped):
        candidate = text_stripped[len(prompt_stripped) :].lstrip("\n")
        if len(candidate.strip()) > 20:
            return candidate

    lines = text_stripped.splitlines()
    prompt_lines = set(prompt_stripped.splitlines())
    if prompt_lines and len(prompt_lines) > 5:
        matching = sum(1 for line in lines if line.strip() in prompt_lines)
        if matching >= len(prompt_lines) * 0.8 and matching > 3:
            filtered = [line for line in lines if line.strip() not in prompt_lines]
            result = "\n".join(filtered).strip()
            if len(result) > 20:
                return result

    return text
