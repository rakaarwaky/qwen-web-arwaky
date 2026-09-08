#!/usr/bin/env bash
# scripts/uninstall.sh — Clean uninstaller for qwen-web-arwaky (XDG Base Directory)
set -euo pipefail

TOOL_NAME="qwen-web"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/$TOOL_NAME"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/$TOOL_NAME"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/$TOOL_NAME"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/$TOOL_NAME"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Uninstalling qwen-web-arwaky ==="

# Remove bin launchers
COMMANDS=("qwen-web-arwaky" "qwa" "qwen-web-cli" "qwc" "qwen-web-mcp")
for cmd in "${COMMANDS[@]}"; do
    if [ -L "$BIN_DIR/$cmd" ] || [ -f "$BIN_DIR/$cmd" ]; then
        rm -f "$BIN_DIR/$cmd"
        echo "✓ Removed $BIN_DIR/$cmd"
    fi
done

# Remove in-tree .venv/venv symlinks
for name in ".venv" "venv"; do
    if [ -L "$PROJECT_DIR/$name" ]; then
        rm -f "$PROJECT_DIR/$name"
        echo "✓ Removed $PROJECT_DIR/$name symlink"
    fi
done

# Remove XDG config & cache (always), data & state with --purge
if [ -d "$CONFIG_DIR" ]; then
    rm -rf "$CONFIG_DIR"
    echo "✓ Removed $CONFIG_DIR"
fi
if [ -d "$CACHE_DIR" ]; then
    rm -rf "$CACHE_DIR"
    echo "✓ Removed $CACHE_DIR"
fi
if [[ "${1:-}" == "--purge" ]]; then
    for d in "$DATA_DIR" "$STATE_DIR"; do
        if [ -d "$d" ]; then
            rm -rf "$d"
            echo "✓ Purged $d"
        fi
    done
fi

echo "Uninstall complete."
