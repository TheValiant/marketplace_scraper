#!/usr/bin/env bash
# pylance.sh — Self-resolving linter & type-checker for the ecom_search project.
# Runs Flake8 (style/complexity) and Pyright (strict static type checking).
set -euo pipefail

# ── Color Codes ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[FAIL]${RESET}  $*"; }

# ── Dependency Auto-Resolution ───────────────────────────────────────────────
ensure_tool() {
    local tool="$1"
    if ! command -v "$tool" &>/dev/null; then
        warn "'$tool' not found in PATH — installing via pip..."
        pip install "$tool" || { error "Failed to install $tool"; exit 1; }
        # Re-check after install
        if ! command -v "$tool" &>/dev/null; then
            error "'$tool' still not available after installation."
            exit 1
        fi
        success "'$tool' installed successfully."
    else
        success "'$tool' found at $(command -v "$tool")"
    fi
}

info "Checking dependencies..."
ensure_tool flake8
ensure_tool pyright

# ── Trap: clean up temporary pyrightconfig.json on exit ──────────────────────
PYRIGHT_CFG="pyrightconfig.json"
cleanup() { rm -f "$PYRIGHT_CFG"; }
trap cleanup EXIT

# Track overall result (0 = pass, 1 = fail)
RESULT=0

# ── Phase 1: Flake8 ─────────────────────────────────────────────────────────
info "Running Flake8 (style & complexity)..."
set +e
flake8 . \
    --exclude=.git,__pycache__,.venv,venv,env,.tox,node_modules,.antigravity \
    --max-complexity=10 \
    --max-line-length=88 \
    --show-source \
    --statistics
FLAKE8_EXIT=$?
set -e

if [[ $FLAKE8_EXIT -ne 0 ]]; then
    error "Flake8 reported issues (exit code $FLAKE8_EXIT)."
    RESULT=1
else
    success "Flake8 passed — no issues found."
fi

# ── Phase 2: Pyright (strict mode via temporary config) ──────────────────────
info "Generating temporary $PYRIGHT_CFG..."
cat > "$PYRIGHT_CFG" <<'EOF'
{
    "typeCheckingMode": "strict",
    "exclude": [
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        "node_modules",
        ".antigravity"
    ],
    "venvPath": ".",
    "venv": ".venv"
}
EOF

info "Running Pyright (strict type checking)..."
set +e
pyright .
PYRIGHT_EXIT=$?
set -e

if [[ $PYRIGHT_EXIT -ne 0 ]]; then
    error "Pyright reported issues (exit code $PYRIGHT_EXIT)."
    RESULT=1
else
    success "Pyright passed — no type errors found."
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
if [[ $RESULT -eq 0 ]]; then
    echo -e "${GREEN}══════════════════════════════════════${RESET}"
    echo -e "${GREEN}  ✓  All checks passed!              ${RESET}"
    echo -e "${GREEN}══════════════════════════════════════${RESET}"
    exit 0
else
    echo -e "${RED}══════════════════════════════════════${RESET}"
    echo -e "${RED}  ✗  Checks failed — see above.      ${RESET}"
    echo -e "${RED}══════════════════════════════════════${RESET}"
    exit 1
fi
