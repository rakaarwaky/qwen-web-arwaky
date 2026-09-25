---
name: python-doc-comments
description: "How to write Python doc comments: PEP 257 docstrings on every public module, class, function, and method so a reader knows what and why without opening the body."
metadata:
  tags: [python, docs, docstring, doc-comments, pep257]
  triggers:
    - "python doc comments"
    - "write docstrings"
    - "module docstring"
    - "args returns docstring"
  dependencies: []
  related:
    - add-docs-python
    - cleanup-consolidate-python
---

# python-doc-comments

## Purpose

Document every public Python item so a reader knows **what** and **why**
without opening the body.

- **Audience:** Engineers and agents reading generated or source docs.
- **Scope:** Module, class, function, and method docstrings (PEP 257) under a
  package's public surface. Tests and benches are out of scope.
- **Location:** On the item itself (`"""…"""` immediately after the
  `def` / `class` / module header).
- **Length:** One summary line; `Args` / `Returns` / `Attributes` only when
  the signature or fields are not self-evident.

## Rules

Six rules. Each one prevents a specific failure mode.

1. **Module-level docstring is mandatory.** First statement of every public
   module. One sentence on the module's job; no changelog.
2. **Doc comments explain what and why, never how.** Restating the next three
   lines of code wastes the reader's time.
3. **Never restate the signature in prose.** `Args` names match the
   parameters; do not repeat types already in the annotation when the
   annotation says it better.
4. **Public classes and functions always get docstrings (PEP 257).** Private
   helpers (`_name`) may omit them when the name is enough.
5. **`Args` and `Returns` on every public function** whose parameters or
   return value are not obvious from the type hints alone.
6. **No status claims.** Docstrings never say implemented / shipped /
   N% done — that lives in `BACKLOG.md` (status-in-spec).

## Workflow

1. **Create file** — module docstring at top of source file.
2. **Write Purpose** — one-line module job.
3. **Write Audience** — who reads this.
4. **Write Scope** — what the module covers.
5. **Verify** → import check passes; doc present.

## Template

Copy, fill, delete nothing.

```python
"""Value objects for import rules."""

class ImportRuleVO:
    """An import rule: a path pattern and the message it reports.

    Attributes:
        pattern: Glob matched against a repo-relative path.
        message: Human-readable violation text.
    """

    def check(self, path: str) -> bool:
        """Return whether *path* violates this rule.

        Args:
            path: Repo-relative file path to test.

        Returns:
            True when the path matches the rule's pattern.
        """
```

## Section Contract

Every public item is required to carry the rows that apply. Each exists for
one reason.

| Section                       | Why it belongs here                                                            |
| ----------------------------- | ------------------------------------------------------------------------------ |
| Module docstring (required)   | Names the module's job before any import.                                      |
| Class summary (required)      | One sentence: what an instance is. Watch for restating the class name.         |
| Attributes (recommended)      | Documents fields whose names do not carry the meaning. Skip when self-describing. |
| Method summary (required)     | One sentence: what a call does. Watch for "This method…" throat-clearing.      |
| Args (recommended)            | Explains non-obvious parameters. Skip when every arg is named for its type alone. |
| Returns / Raises (recommended)| States the contract the caller depends on. Skip only when the return type is `None` and nothing can fail. |

## Verify

```bash
python -c "import modules"
# Checks: importability + module docstrings present on public surface.
# Manual: no "how" narration; Args/Returns on public defs; no status words.
```

One-shot audit of the public surface (source only, tests/benches excluded):

```bash
python - <<'EOF'
import ast, pathlib
missing = 0
for f in sorted(pathlib.Path('.').rglob('*.py')):
    if '.venv' in f.parts or 'tests' in f.parts or 'benches' in f.parts:
        continue
    tree = ast.parse(f.read_text())
    if not ast.get_docstring(tree):
        print(f"{f}: module docstring missing"); missing += 1
    for n in ast.walk(tree):
        if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not n.name.startswith('_') and not ast.get_docstring(n):
                print(f"{f}:{n.lineno}: {n.name} docstring missing"); missing += 1
raise SystemExit(1 if missing else 0)
EOF
```
