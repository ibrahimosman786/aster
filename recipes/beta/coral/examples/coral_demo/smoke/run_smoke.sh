#!/bin/bash
# No-GPU smoke run: real CORAL runtime + real Aster service, canned model.
#
# Exercises run.py unmodified — AgentManager, worktrees, gateway + LiteLLM,
# grader daemon, attempt watcher, result bundle — against
# smoke/echo_aster_service.py (the production Aster service with a canned
# inference backend) and smoke/scripted_runtime.py (a real AgentRuntime
# whose agent is scripted). Needs an environment with coral AND aster
# installed:
#
#   uv venv .venv && uv pip install -e .[coral] -e ../../../../..
#   ./smoke/run_smoke.sh
set -e
cd "$(dirname "$0")/.."
REPO_ROOT="$(cd ../../../../.. && pwd)"
export PYTHONPATH="$REPO_ROOT:$PWD:${PYTHONPATH:-}"  # recipes.beta.coral + smoke importable
export ASTER_TOKEN="${ASTER_TOKEN:-aster-local}"
WORK="$PWD/work/smoke-$(date +%s)"
mkdir -p "$WORK"

ASTER_PORT="${ASTER_PORT:-18900}"  # clear of any real stack on 8900
python3 smoke/echo_aster_service.py --port "$ASTER_PORT" --token "$ASTER_TOKEN" > "$WORK/aster-stub.log" 2>&1 &
aster_pid=$!
cleanup() {
    kill "$aster_pid" 2>/dev/null || true
    wait "$aster_pid" 2>/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 60); do
    curl -sf "http://127.0.0.1:$ASTER_PORT/healthz" > /dev/null && break
    sleep 1
done

python3 run.py \
    --work "$WORK" \
    --agents 2 \
    --max-attempts 4 \
    --aster-url "http://127.0.0.1:$ASTER_PORT" \
    --gateway-port 18091 \
    --runtime smoke.scripted_runtime:ScriptedRuntime \
    --model aster-policy

python3 smoke/check_bundle.py "$WORK/bundle.json"
echo "smoke run OK: $WORK/bundle.json"
