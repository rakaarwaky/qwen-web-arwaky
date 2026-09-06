#!/usr/bin/env python3
"""Bump version utility for qwen-web-arwaky.

Bumps semantic versioning in root `pyproject.toml` and subpackage manifests
(`modules/*/pyproject.toml`). Optionally creates git commit and tag.

Usage:
    python3 scripts/bump.py patch                # 4.2.0 -> 4.2.1
    python3 scripts/bump.py minor                # 4.2.0 -> 4.3.0
    python3 scripts/bump.py major                # 4.2.0 -> 5.0.0
    python3 scripts/bump.py 4.5.0                # explicit version
    python3 scripts/bump.py minor --git          # bump + git commit & tag
    python3 scripts/bump.py minor --dry-run      # preview changes only
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
TARGET_FILES = [
    ROOT_DIR / "pyproject.toml",
    ROOT_DIR / "modules" / "shared" / "pyproject.toml",
    ROOT_DIR / "modules" / "core" / "pyproject.toml",
    ROOT_DIR / "modules" / "mcp" / "pyproject.toml",
]


def get_current_version(root_toml: Path) -> str:
    """Extract version from root pyproject.toml."""
    content = root_toml.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        sys.exit("Error: Could not find `version = \"...\"` in root pyproject.toml")
    return match.group(1).strip()


def compute_new_version(current: str, target: str) -> str:
    """Compute new semver string from rule (patch, minor, major) or explicit version."""
    clean = target.strip().lstrip("vV")
    if re.match(r"^\d+\.\d+\.\d+$", clean):
        return clean

    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", current)
    if not match:
        sys.exit(f"Error: Installed version '{current}' is not valid SemVer (X.Y.Z)")

    major, minor, patch = (int(x) for x in match.groups())
    rule = target.lower()

    if rule == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if rule == "minor":
        return f"{major}.{minor + 1}.0"
    if rule == "major":
        return f"{major + 1}.0.0"

    sys.exit(
        f"Error: Invalid version rule or semver '{target}'. Use 'patch', 'minor', 'major', or 'X.Y.Z'."
    )


def update_file(path: Path, current: str, new_version: str, dry_run: bool = False) -> bool:
    """Update version line in a pyproject.toml file."""
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    pattern = re.compile(rf'^(version\s*=\s*)"{re.escape(current)}"', re.MULTILINE)

    if not pattern.search(content):
        # Fallback to replacing any version line in [project]
        pattern = re.compile(r'^(version\s*=\s*)"[^"]+"', re.MULTILINE)

    new_content, count = pattern.subn(rf'\1"{new_version}"', content, count=1)
    if count == 0:
        print(f"  ⚠️  No version line updated in {path.relative_to(ROOT_DIR)}")
        return False

    if not dry_run:
        path.write_text(new_content, encoding="utf-8")
    print(f"  ✓ Updated {path.relative_to(ROOT_DIR)}")
    return True


def run_git_release(new_version: str) -> None:
    """Commit changes and create a git tag."""
    print("\n📦 Git commit and tag:")
    rel_paths = [str(p.relative_to(ROOT_DIR)) for p in TARGET_FILES if p.exists()]
    subprocess.run(["git", "add"] + rel_paths, check=True, cwd=ROOT_DIR)
    commit_msg = f"release: v{new_version}"
    subprocess.run(["git", "commit", "-m", commit_msg], check=True, cwd=ROOT_DIR)
    tag_name = f"v{new_version}"
    subprocess.run(["git", "tag", "-a", tag_name, "-m", commit_msg], check=True, cwd=ROOT_DIR)
    print(f"  ✓ Created commit '{commit_msg}' and tag '{tag_name}'")
    print("  💡 Run `git push && git push --tags` to publish to GitHub Releases.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Bump version in pyproject.toml files.")
    parser.add_argument(
        "target",
        help="Version bump rule ('patch', 'minor', 'major') or explicit version (e.g. '4.3.0')",
    )
    parser.add_argument(
        "--git",
        action="store_true",
        help="Automatically commit and tag the new release in git",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files",
    )

    args = parser.parse_args(argv)
    root_toml = TARGET_FILES[0]
    current = get_current_version(root_toml)
    new_version = compute_new_version(current, args.target)

    print(f"🚀 Bumping version: {current} ──► {new_version}" + (" (DRY RUN)" if args.dry_run else ""))
    print("Files:")

    for path in TARGET_FILES:
        update_file(path, current, new_version, dry_run=args.dry_run)

    if args.git and not args.dry_run:
        run_git_release(new_version)

    print(f"\n✅ Successfully bumped version to {new_version}")


if __name__ == "__main__":
    main()
