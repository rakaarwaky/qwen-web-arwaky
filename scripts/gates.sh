#!/usr/bin/env bash
# scripts/gates.sh — Local quality gates mirror CI for qwen-web-arwaky.
# Usage: bash scripts/gates.sh
#   Runs all 5 gates: Ruff (lint + format), Mypy, Bandit, AES self-lint, and Pytest.
#   Mirrors .github/workflows/ci.yml (uv-based). Bandit is always enforced (not optional).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# ─── Color helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { printf "${CYAN}  [gates] %s${NC}\n" "$*"; }
ok()    { printf "${GREEN}  ✓%s${NC}\n" "$*"; }
warn()  { printf "${YELLOW}  ⚠%s${NC}\n" "$*"; }
fail()  { printf "${RED}  ✗%s${NC}\n" "$*"; exit 1; }

# ─── Pre-flight: uv ─────────────────────────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
    info "Installing uv..."
    pip install --quiet uv || curl -LsSf https://astral.sh/uv/install.sh | sh
fi

info "Syncing project dependencies (uv)..."
uv sync --no-dev

# Best-effort extras for local runs: bandit + Playwright browser
uv pip install --quiet bandit >/dev/null 2>&1 || true
uv run python -m playwright install chromium >/dev/null 2>&1 || true

# ─── Gates ──────────────────────────────────────────────────────────────────
FAILURES=0

# Gate 1: Ruff lint + format check
info "Gate 1/5 — Ruff lint & format..."
if uv run ruff format --check modules/ tests/ >/dev/null 2>&1 && \
   uv run ruff check modules/ tests/ 2>&1 | grep -q "All checks passed"; then
    ok "Ruff clean"
else
    warn "Ruff found issues (run 'uv run ruff format --check modules/ tests/' and 'uv run ruff check modules/ tests/' for details)"
    FAILURES=$((FAILURES + 1))
fi

# Gate 2: Mypy type checking
info "Gate 2/5 — Mypy type check..."
if uv run mypy modules/ --ignore-missing-imports >/tmp/gates_mypy.log 2>&1; then
    ok "Mypy clean"
else
    warn "Mypy found type errors"
    tail -5 /tmp/gates_mypy.log
    FAILURES=$((FAILURES + 1))
fi

# Gate 3: Bandit security scan (source code only, exclude tests) — always runs (not optional)
info "Gate 3/5 — Bandit security scan..."
if uv run bandit modules/root_cli_main_entry.py modules/root_mcp_main_entry.py -r modules/ -s B110,B112 2>&1 | grep -q "No issues"; then
    ok "Bandit clean"
else
    warn "Bandit found potential issues"
    FAILURES=$((FAILURES + 1))
fi

# Gate 4: AES architecture self-lint (lint-arwaky-cli)
info "Gate 4/5 — AES architecture self-lint..."
if command -v lint-arwaky-cli &>/dev/null; then
    output=$(lint-arwaky-cli scan . 2>&1) || true
    echo "$output" | tail -5
    violations=$(echo "$output" | grep -oP 'Total:\s*\K\d+' || echo "0")
    if [ "${violations}" = "0" ]; then
        ok "AES architecture clean (0 violations)"
    else
        warn "AES architecture found ${violations} violations"
        FAILURES=$((FAILURES + 1))
    fi
else
    warn "lint-arwaky-cli not installed — skipping AES check (see CI: downloads release binary)"
    FAILURES=$((FAILURES + 1))
fi

# Gate 5: Pytest test suite
info "Gate 5/5 — Running pytest..."
if uv run python -m pytest tests/ --ignore=tests/test_e2e_pipeline.py -v >/tmp/gates_pytest.log 2>&1; then
    ok "Tests passed"
else
    warn "Tests failed (see output above)"
    tail -15 /tmp/gates_pytest.log
    FAILURES=$((FAILURES + 1))
fi

# ─── Summary ────────────────────────────────────────────────────────────────
echo ""
if [ "${FAILURES}" -eq 0 ]; then
    ok "All gates passed"
    exit 0
else
    fail "${FAILURES} gate(s) failed"
fi
