#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

export ASTER_WORK="${ASTER_WORK:-$PWD/work}"
export ASTER_MODEL="${ASTER_MODEL:-openai/gpt-5.6-luna}"
export ASTER_UPSTREAM_URL="${ASTER_UPSTREAM_URL:-https://api.openai.com}"
export ASTER_PROPOSER_MODEL="${ASTER_PROPOSER_MODEL:-gpt-5.6-sol}"
export ASTER_PROPOSER_URL="${ASTER_PROPOSER_URL:-$ASTER_UPSTREAM_URL}"
export ASTER_PROPOSER_API_KEY="${ASTER_PROPOSER_API_KEY:-${ASTER_UPSTREAM_API_KEY:-}}"
export ASTER_META_HARNESS_WORKERS="${ASTER_META_HARNESS_WORKERS:-4}"
export ASTER_TERMINUS_ENVIRONMENT=e2b

# The harness is installed by pip; the checkout supplies the recipe and Aster.
export PYTHONPATH="$(cd ../../../.. && pwd)${PYTHONPATH:+:$PYTHONPATH}"
exec "${PYTHON:-python3}" run.py "$@"
