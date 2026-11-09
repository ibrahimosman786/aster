#!/bin/bash
# Reefine on pi, end to end. Usage: ./run.sh bugfix | research | measure [--n N]
# Starts aster serve on configs/deployment.yaml, waits for /healthz, installs
# the served tree under work/harness, runs run.py <mode>, stops the service.
# State and logs go to ./work. Setup (once): see README.
set -e
cd "$(dirname "$0")"

MODE="${1:-}"
case "$MODE" in
    bugfix|research|measure) ;;
    *) echo "usage: ./run.sh bugfix | research | measure [--n N]" >&2; exit 2 ;;
esac
shift
mkdir -p work

# The model server and the model: ollama on this machine unless the environment says otherwise.
export ASTER_UPSTREAM_URL="${ASTER_UPSTREAM_URL:-http://127.0.0.1:11434}"
export ASTER_UPSTREAM_MODEL="${ASTER_UPSTREAM_MODEL:-gemma4:26b}"
export ASTER_UPSTREAM_API_KEY="${ASTER_UPSTREAM_API_KEY:-dummy}"
export ASTER_TOKEN="${ASTER_TOKEN:-aster-local}"
# A local 26B model answers a request in minutes; the method package's default budget is two.
export ASTER_ASTERINE_CALL_TIMEOUT_S="${ASTER_ASTERINE_CALL_TIMEOUT_S:-900}"
# A thinking model spends the reply budget on its reasoning first: 4096 tokens came back empty, which is why the
# method package's defaults are 65536 for a request and 16384 for its review now; pinned here so a run does not
# depend on those defaults.
export ASTER_ASTERINE_CALL_MAX_TOKENS="${ASTER_ASTERINE_CALL_MAX_TOKENS:-16384}"

TUTORIAL="$PWD"
REPO="$(cd ../../../.. && pwd)"
# aster serve and run.py run from this checkout.
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"

# deployment.yaml listens on 8901; an aster already there would answer for another deployment.
if curl -sf http://127.0.0.1:8901/healthz > /dev/null 2>&1; then
    echo "an aster already answers on 127.0.0.1:8901; stop it first" >&2
    exit 1
fi

# Start Aster from the repository root, where deployment.yaml's state directories are relative to,
# and stop it again when this script exits.
(cd "$REPO" && exec python3 -m aster serve -c "$TUTORIAL/configs/deployment.yaml") > work/aster.log 2>&1 &
SERVE_PID=$!
trap 'kill "$SERVE_PID" 2>/dev/null' EXIT

# Wait until Aster answers; a dead orchestrator fails fast with its log.
while ! curl -sf http://127.0.0.1:8901/healthz > /dev/null; do
    kill -0 "$SERVE_PID" 2>/dev/null || { cat work/aster.log >&2; exit 1; }
    sleep 1
done

# The served tree, rendered for pi with a binding at this Aster, and its release metadata file land under work/harness.
python3 run.py install
python3 run.py "$MODE" "$@"
