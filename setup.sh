#!/usr/bin/env bash
#
# setup.sh — install this project (and its pyproject.toml dependencies)
# into the CURRENT Python environment in editable mode, then remove the
# *.egg-info build leftovers.
#
# Usage:
#   ./setup.sh            # install project + core dependencies
#   ./setup.sh dev        # also install the [dev] optional-dependencies group
#   ./setup.sh dev,test   # several extras groups, comma-separated
 
set -euo pipefail
 
# Always run from the folder this script lives in (the project root),
# so it works no matter where you call it from.
cd "$(dirname "${BASH_SOURCE[0]}")"
 
cleanup() {
    local exit_code=$?
    echo ""
    echo "==> Cleaning up *.egg-info folders..."
    # Search root and one level down to catch src/ layouts (src/pkg.egg-info).
    find . -maxdepth 2 -type d -name "*.egg-info" -not -path "./.git/*" -print -exec rm -rf {} + 2>/dev/null || true
    if [[ $exit_code -eq 0 ]]; then
        echo "==> Done. Setup completed successfully."
    else
        echo "==> Setup FAILED (exit code $exit_code). Scroll up for the error."
    fi
    exit "$exit_code"
}
trap cleanup EXIT
 
echo "==> Checking for pyproject.toml..."
if [[ ! -f pyproject.toml ]]; then
    echo "ERROR: pyproject.toml not found in $(pwd)" >&2
    exit 1
fi
 
echo "==> Checking which Python environment is active..."
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    echo "    venv: ${VIRTUAL_ENV}"
elif [[ -n "${CONDA_DEFAULT_ENV:-}" && "${CONDA_DEFAULT_ENV}" != "base" ]]; then
    echo "    Conda env: ${CONDA_DEFAULT_ENV}"
else
    echo "ERROR: No project environment is active (found: '${CONDA_DEFAULT_ENV:-none}')." >&2
    echo "       Refusing to install into base/system Python." >&2
    echo "       Run: conda activate <env-name>   then rerun this script." >&2
    exit 1
fi
echo "    Python: $(python -c 'import sys; print(sys.executable)')"
echo "    Version: $(python --version 2>&1)"
 
echo "==> Upgrading pip..."
python -m pip install --upgrade pip
 
if [[ $# -gt 0 && -n "$1" ]]; then
    GROUP_ARGS=()
    IFS=',' read -ra group_list <<< "$1"
    for g in "${group_list[@]}"; do
        GROUP_ARGS+=(--group "$g")
    done
    echo "==> Installing project in editable mode WITH dependency groups [$1]..."
    python -m pip install -e . "${GROUP_ARGS[@]}"
else
    echo "==> Installing project in editable mode (core dependencies)..."
    python -m pip install -e .
fi
 
echo "==> Verifying installed dependencies are compatible..."
python -m pip check