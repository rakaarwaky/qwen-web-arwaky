#!/usr/bin/env bash
# Prepare an isolated, deterministic UAT workspace without requiring a live Qwen session.
set -euo pipefail

ROOT_DIR="${QWEN_UAT_ROOT:-.qwen-web/output/uat}"
mkdir -p "$ROOT_DIR" "$ROOT_DIR/input" "$ROOT_DIR/processing" "$ROOT_DIR/done" "$ROOT_DIR/failed"
: "${QWEN_UAT_SESSION_DIR:=$ROOT_DIR/session}"
mkdir -p "$QWEN_UAT_SESSION_DIR"

cat <<MSG
UAT workspace ready:
  output: $ROOT_DIR
  session: $QWEN_UAT_SESSION_DIR

Live authentication is intentionally not performed by this script.
For browser-backed UAT, provide a valid session separately and run the
scenario checklist in UAT.md.
MSG
