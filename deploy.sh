#!/usr/bin/env bash
#
# deploy.sh - validate, test, and deploy this Databricks bundle in one standard sequence.
#
# Usage:
#   bash deploy.sh                  # deploy to dev (default)
#   bash deploy.sh dev <job_key>    # deploy to dev, then run a job (key from resources/*.yml)
#   bash deploy.sh --skip-tests     # deploy to dev without running offline tests
#
# Production deploys are blocked here on purpose: prod should be deployed by CI
# from the main branch, as a service principal. Override only with --allow-prod.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
target="dev"
job_key=""
skip_tests=false
allow_prod=false

positional=()
for arg in "$@"; do
    case "$arg" in
        --skip-tests) skip_tests=true ;;
        --allow-prod) allow_prod=true ;;
        -h|--help)    sed -n '2,13p' "$0"; exit 0 ;;
        *)            positional+=("$arg") ;;
    esac
done
[[ ${#positional[@]} -ge 1 ]] && target="${positional[0]}"
[[ ${#positional[@]} -ge 2 ]] && job_key="${positional[1]}"

step() { echo ""; echo "==> $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

trap 'code=$?; [[ $code -ne 0 ]] && echo "" && echo "==> Deploy FAILED at the step above (exit code $code)."' EXIT

# ---------------------------------------------------------------------------
# 1. Guardrails
# ---------------------------------------------------------------------------
step "Checking target: ${target}"
if [[ "$target" == "prod" && "$allow_prod" != true ]]; then
    fail "Production deploys go through CI from main. Use --allow-prod only if you are sure."
fi

step "Checking tools and sign-in..."
command -v databricks >/dev/null || fail "Databricks CLI not found. Install it and restart your terminal."
databricks current-user me --output json >/dev/null \
    || fail "Not signed in. Run: databricks auth login --host <workspace-url>"
echo "    Signed in as: $(databricks current-user me --output json | python -c 'import sys,json; print(json.load(sys.stdin)["userName"])')"

step "Checking Git state..."
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    branch="$(git rev-parse --abbrev-ref HEAD)"
    commit="$(git rev-parse --short HEAD)"
    echo "    Branch: ${branch}  Commit: ${commit}"
    if [[ -n "$(git status --porcelain)" ]]; then
        if [[ "$target" == "dev" ]]; then
            echo "    WARNING: uncommitted changes will be deployed to dev."
        else
            fail "Uncommitted changes. Commit or stash before deploying to ${target}."
        fi
    fi
else
    echo "    WARNING: not a Git repository; nothing records what was deployed."
fi

# ---------------------------------------------------------------------------
# 2. Offline tests
# ---------------------------------------------------------------------------
if [[ "$skip_tests" == true ]]; then
    step "Skipping tests (--skip-tests)."
else
    step "Running offline tests (smoke, unit, stage)..."
    python -m pytest -q || fail "Tests failed. Fix them or rerun with --skip-tests."
fi

# ---------------------------------------------------------------------------
# 3. Validate...show what will deploy...then deploy
# ---------------------------------------------------------------------------
step "Validating bundle for target '${target}'..."
databricks bundle validate -t "$target"

# Dev only: make sure the developer's personal schema exists. It is created here, NOT as a
# bundle resource, so `bundle destroy -t dev` can never delete it. (Prod's schema is a bundle
# resource in resources/schemas.yml.)
if [[ "$target" == "dev" ]]; then
    step "Checking your dev schema..."
    read -r catalog schema < <(
        databricks bundle validate -t dev --output json | python -c \
            'import sys, json; v = json.load(sys.stdin)["variables"]; print(v["catalog"]["value"], v["schema"]["value"])' \
            | tr -d '\r'   # Windows Python ends lines with \r\n; a stray \r would corrupt the name
    )
    if databricks schemas get "${catalog}.${schema}" >/dev/null 2>&1; then
        echo "    ${catalog}.${schema} exists."
    else
        databricks schemas create "$schema" "$catalog" \
            --comment "Personal dev schema (created by deploy.sh)" >/dev/null
        echo "    Created ${catalog}.${schema}."
    fi
fi

step "Deploying bundle to '${target}'..."
databricks bundle deploy -t "$target"

step "Deployed resources:"
databricks bundle summary -t "$target"

# ---------------------------------------------------------------------------
# 4. Optional run
# ---------------------------------------------------------------------------
if [[ -n "$job_key" ]]; then
    step "Running job '${job_key}' on '${target}'..."
    databricks bundle run "$job_key" -t "$target"
fi

step "Done. Target '${target}' is up to date."