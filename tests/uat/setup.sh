#!/usr/bin/env bash
# Prepare an isolated, deterministic UAT workspace without requiring a live Qwen session.
set -euo pipefail

ROOT_DIR="${QWEN_UAT_ROOT:-.qwen-web/output/uat}"
mkdir -p "$ROOT_DIR" "$ROOT_DIR/input"
: "${QWEN_UAT_SESSION_DIR:=$ROOT_DIR/session}"
mkdir -p "$QWEN_UAT_SESSION_DIR"

cat <<MSG
UAT workspace ready:
  output: $ROOT_DIR
  input: $ROOT_DIR/input
  session: $QWEN_UAT_SESSION_DIR

Input files remain in place. Success and failure are recorded in logs and
metrics; no processing, done, or failed folders are created.
Live authentication is intentionally not performed by this script.
MSG
