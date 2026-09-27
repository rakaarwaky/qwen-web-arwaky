#!/usr/bin/env bash
# ci.sh — Local quality gates that mirror .github/workflows/ci.yml for
# qwen-web-arwaky. Use this to gate local merges and PR readiness without
# depending on GitHub Actions runners.
#
# Usage:
#   bash scripts/ci.sh                 # run on host (uv-based)
#   bash scripts/ci.sh --container     # run inside the existing qwen-web-arwaky Podman container
#
# Gates (mirror of ci.yml):
#   1. ruff format --check
#   2. ruff check + mypy + uv lock --check
#   3. uv build
#   4. pytest (CI command, 3.12 matrix)
#   5. lint-arwaky-cli scan
#   6. AD-05 template hygiene (grep for &lt; &gt;)
#   7. Bandit security scan
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ─── Color / logging ────────────────────────────────────────────────────────
RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[1;33m' CYAN='\033[0;36m' NC='\033[0m'
info() { printf "${CYAN}  [ci]   %s${NC}\n" "$*"; }
ok()   { printf "${GREEN}  ✓ [ci]  %s${NC}\n" "$*"; }
warn() { printf "${YELLOW}  ✗ [ci]  %s${NC}\n" "$*"; }
fail() { printf "${RED}  FATAL [ci] %s${NC}\n" "$*" >&2; exit 1; }

# ─── Dispatch: host vs container ────────────────────────────────────────────
if [[ "${1:-}" == "--container" ]]; then
    if ! command -v podman >/dev/null 2>&1; then
        fail "podman not found on this host"
    fi
    if ! podman ps --format '{{.Names}}' | grep -q '^qwen-web-arwaky$'; then
        fail "container 'qwen-web-arwaky' is not running — start it with: bash scripts/podman.sh start"
    fi
    info "Running inside container 'qwen-web-arwaky' (source mounted at /root/src)."
    # Exec the script inside the running container; the container was started
    # with 'sleep infinity' as entrypoint so 'bash' is available directly.
    podman exec qwen-web-arwaky bash /root/src/scripts/ci.sh
    exit $?
fi

cd "${PROJECT_ROOT}"
# lint-arwaky-cli resolves its scan root from the current directory; the
# container's workdir is /root, so cd into the source mount first.

# ─── Detect execution mode: host (uv venv) vs container (baked venv) ──────
# Inside the slim container, /opt/venv already has every dependency installed.
# uv sync would try to write a local .venv into the (read-only) source mount
# and fail, so skip it entirely when we are in the container.
IN_CONTAINER=0
if [[ -d /opt/venv && -f /opt/venv/bin/qwa ]]; then
    IN_CONTAINER=1
fi

# ─── Pre-flight: ensure uv is available ────────────────────────────────────
if [[ "${IN_CONTAINER}" -eq 0 ]]; then
    if ! command -v uv >/dev/null 2>&1; then
        info "Installing uv..."
        if command -v pip; then pip install --quiet uv; fi
        if ! command -v uv >/dev/null 2>&1; then
            curl -LsSf https://astral.sh/uv/install.sh | sh
        fi
    fi

    info "Syncing project dependencies (uv)..."
    uv sync --no-dev || fail "uv sync failed — check network / uv.lock"

    # Best-effort extras that are not in the main lock: Bandit + Playwright
    # chromium. These only affect gate 7 (bandit) and gate 4 (pytest browser
    # tests); failures here are downgraded to warnings so the remaining gates
    # still run.
    if ! uv pip show bandit >/dev/null 2>&1; then
        info "Installing bandit..."
        uv pip install --quiet bandit || true
    fi
    if ! uv run python -c "from playwright.sync_api import sync_playwright" >/dev/null 2>&1; then
        info "Installing Playwright chromium..."
        uv run python -m playwright install chromium || true
    fi
fi


FAILURES=0
run_gate() {
    local name="$1"; shift
    info "Gate: ${name}"
    if "$@" >/tmp/ci_${name// /_}.log 2>&1; then
        ok "${name} passed"
    else
        warn "${name} failed (last lines:)"
        tail -8 "/tmp/ci_${name// /_}.log" || true
        FAILURES=$((FAILURES + 1))
    fi
}

# ─── Gate 1: ruff format ─────────────────────────────────────────────────────
run_gate "ruff format check" uv run ruff format --check modules/ tests/

# ─── Gate 2: ruff check + mypy + uv lock ───────────────────────────────────
run_gate "ruff check" uv run ruff check modules/ tests/
run_gate "mypy" uv run mypy modules/
run_gate "uv lock check" uv lock --check

# ─── Gate 3: build the distribution ─────────────────────────────────────────
run_gate "uv build" uv build

# ─── Gate 4: pytest — mirror of .github/workflows/ci.yml 'Tests (pytest)' ─
# NOTE: The CI job installs pytest-asyncio/pytest-cov as test extras. Mirror
# that here with a best-effort install so local runs match.
uv pip install --quiet pytest pytest-asyncio pytest-cov pytest-mock 2>/dev/null || true
run_gate "pytest" \
    uv run python -m pytest \
        tests/ modules/shared/tests/ modules/cli/tests/ modules/mcp/tests/ \
        modules/prompt/tests/ modules/session/tests/ modules/jobs/tests/ \
        modules/browser/tests/ modules/config/tests/ modules/logging/tests/ \
        modules/swarm/tests/ modules/update/tests/ \
        modules/shared/benches/ modules/prompt/benches/ \
        --ignore=tests/test_e2e_pipeline.py -m "not benchmark" -v

# ─── Gate 5: AES architecture self-lint ──────────────────────────────────────
# CI downloads lint-arwaky-cli from the GitHub release at runtime.
# Prefer a locally-installed binary; fall back to downloading when missing.
if ! command -v lint-arwaky-cli >/dev/null 2>&1; then
    info "Downloading lint-arwaky-cli from latest release..."
    if command -v curl && curl -fsSL \
        https://github.com/rakaarwaky/lint-arwaky/releases/latest/download/lint-arwaky-cli \
        -o "${TMPDIR:-/tmp}/lint-arwaky-cli" 2>/dev/null; then
        chmod +x "${TMPDIR:-/tmp}/lint-arwaky-cli"
        PATH="${TMPDIR:-/tmp}:${PATH}"
        if command -v lint-arwaky-cli; then
            info "Using downloaded lint-arwaky-cli: $(command -v lint-arwaky-cli)"
        fi
    fi
fi
if command -v lint-arwaky-cli >/dev/null 2>&1; then
    output="$(lint-arwaky-cli scan . 2>&1)" || true
    violations="$(echo "$output" | grep -oP 'Total:\s*\K\d+' || echo 'PARSE_FAILURE')"
    if [[ "$violations" == "0" ]]; then
        ok "AES self-lint passed (0 violations)"
    else
        warn "AES self-lint: ${violations} violations"
        echo "$output" | tail -10
        FAILURES=$((FAILURES + 1))
    fi
else
    warn "lint-arwaky-cli unavailable — gate 5 skipped"
    FAILURES=$((FAILURES + 1))
fi

# ─── Gate 6: AD-05 template hygiene ─────────────────────────────────────────
# mirrors ci.yml 'Check template files are not HTML-escaped'
if grep -rEl '&lt;|&gt;|\\[' modules/templates/ 2>/dev/null; then
    warn "AD-05: HTML-escaped tokens found in modules/templates/"
    FAILURES=$((FAILURES + 1))
else
    ok "AD-05 template hygiene clean"
fi

# ─── Gate 7: Bandit security scan (source only, medium+ severity) ─────────
# Exclude test dirs so B101 (assert) noise from tests doesn't pollute results.
# Only medium/high confidence findings count as failures — low-level B101
# asserts in source are noise and ignored.
if uv run bandit -r modules/ -x '*/tests/*,*/test/*' \
        --severity-level medium --confidence-level medium \
        >/tmp/ci_bandit.log 2>&1; then
    ok "Bandit clean"
elif grep -q "No issues identified" /tmp/ci_bandit.log 2>/dev/null; then
    ok "Bandit clean"
else
    warn "Bandit found issues (last lines:)"
    tail -10 /tmp/ci_bandit.log
    FAILURES=$((FAILURES + 1))
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
if [[ "$FAILURES" -eq 0 ]]; then
    ok "All 7 gates passed — ready to merge"
    exit 0
else
    warn "${FAILURES} gate(s) failed — see /tmp/ci_*.log"
    exit 1
fi
