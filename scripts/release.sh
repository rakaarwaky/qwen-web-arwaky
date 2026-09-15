#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYPROJECT="$PROJECT_ROOT/pyproject.toml"

usage() {
  cat <<EOF
Usage: $(basename "$0") <patch|minor|major|vX.Y.Z>

Bumps version in pyproject.toml, commits, tags, and pushes.

Examples:
  $(basename "$0") patch      # 4.0.0 → 4.0.1
  $(basename "$0") minor      # 4.0.0 → 4.1.0
  $(basename "$0") major      # 4.0.0 → 5.0.0
  $(basename "$0") v4.2.0     # explicit version
EOF
  exit 1
}

[[ $# -lt 1 ]] && usage

# Read current version
CURRENT=$(grep -oP '^version\s*=\s*"\K[^"]+' "$PYPROJECT")
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

# Compute new version
case "$1" in
  patch) NEW="$MAJOR.$MINOR.$((PATCH + 1))" ;;
  minor) NEW="$MAJOR.$((MINOR + 1)).0" ;;
  major) NEW="$((MAJOR + 1)).0.0" ;;
  v*)    NEW="${1#v}" ;;
  *)     usage ;;
esac

# Validate semver
if ! [[ "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: invalid version '$NEW'" >&2
  exit 1
fi

echo "Bumping: $CURRENT → $NEW"

# Bump version in pyproject.toml
sed -i "s/^version = \"$CURRENT\"/version = \"$NEW\"/" "$PYPROJECT"

# Commit and tag
cd "$PROJECT_ROOT"
# The root [project] version in pyproject.toml is the single source of truth and
# uv.lock must move with it — a stale lock breaks --locked/--frozen usage.
uv lock
git add pyproject.toml uv.lock
git commit -m "release: v$NEW"
git tag "v$NEW"
# Push each ref explicitly and check the result. Under `set -e`, a failing
# command on the LEFT of `&&` is exempt from the exit, so the old
# `git push && git push --tags` printed "Released" even when the push was
# rejected. Push branch + tag by name (no upstream assumption).
git push origin "v$NEW" HEAD || { echo "Error: git push failed" >&2; exit 1; }
git push --tags || { echo "Error: tag push failed" >&2; exit 1; }

echo "Released v$NEW"
