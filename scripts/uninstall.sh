#!/usr/bin/env bash
# scripts/uninstall.sh — Clean uninstaller for qwen-web-arwaky (XDG Base Directory)
set -euo pipefail

BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/qwen-web"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/qwen-web"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/qwen-web"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/qwen-web"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Uninstalling qwen-web-arwaky ==="

# Remove bin launchers (full name + short alias + extras)
COMMANDS=("qwen-web-arwaky" "qwa" "qwen-web-cli" "qwc" "qwen-web-mcp")
for cmd in "${COMMANDS[@]}"; do
    if [ -L "$BIN_DIR/$cmd" ] || [ -f "$BIN_DIR/$cmd" ]; then
        rm -f "$BIN_DIR/$cmd"
        echo "✓ Removed $BIN_DIR/$cmd"
    fi
done

# Remove in-tree .venv/venv symlink if it points to XDG
for name in ".venv" "venv"; do
    if [ -L "$PROJECT_DIR/$name" ]; then
        rm -f "$PROJECT_DIR/$name"
        echo "✓ Removed $PROJECT_DIR/$name symlink"
    fi
done

# Remove XDG config & cache (selalu), data & state saat --purge
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
