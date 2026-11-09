#!/usr/bin/env bash
# The OpenClawRL deployment (Aster, independent PRM and student model), then the 72-session GSM8K
# stream through reef-eval. Setup (once): see README. State goes to $RUN_DIR.
#
# The stack is left running and a healthy one is reused, so a re-run continues
# where the lab left off; `docker compose down` stops it. A trained
# stack is bound to its scenario, so switching STREAM_NAME or RUN_DIR needs a
# restart.
set -euo pipefail
cd "$(dirname "$0")"
ASTER_ROOT="$(cd ../../../.. && pwd)"

ASTER_IMAGE="aster-openclawrl"
ASTER_CONFIG="recipes/openclawrl/examples/openclawrl/serve.yaml"
MODEL_DIR="$HOME/models"
RUN_DIR="$HOME/aster-run"
STREAM_NAME="gsm8k"
TASKS="$PWD/harbor-tasks"          # all 72 sessions, in order
HOST_IP="$(hostname -I | awk '{print $1}')"
ASTER_URL="http://${HOST_IP}:28900"

# Prerequisites
command -v uvx >/dev/null || { echo "run.sh: uvx not found (pip install uv)" >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "run.sh: Docker is not running" >&2; exit 1; }
docker image inspect "$ASTER_IMAGE" >/dev/null 2>&1 \
    || { echo "run.sh: image $ASTER_IMAGE not found (build docker/Dockerfile.aster)" >&2; exit 1; }
mkdir -p "$RUN_DIR"

# The judge service, one image shared by every task, tagged with user_sim/'s
# content hash. The tasks pin that tag, so a change here without a re-stamp
# would build an image no task can pull; ./restamp.sh fixes it.
USER_SIM_TAG="$(cat user_sim/{Dockerfile,personas.py,pyproject.toml,student_server.py} | sha256sum | cut -c1-12)"
grep -q "FROM openclawrl-user-sim:$USER_SIM_TAG" harbor-tasks/gsm8k-s000/environment/Dockerfile.judge \
    || { echo "run.sh: user_sim/ changed; re-stamp the 72 tasks with ./restamp.sh" >&2; exit 1; }
docker build -q -t "openclawrl-user-sim:$USER_SIM_TAG" user_sim >/dev/null
[ -f "$RUN_DIR/token" ] || openssl rand -hex 16 > "$RUN_DIR/token"
ASTER_TOKEN="$(cat "$RUN_DIR/token")"

# 1. Compose owns Aster, PRM and student-model startup and readiness.
echo "==> [1/2] the aster stack at $ASTER_URL (a cold boot takes ~6 minutes on B200s)"
# compose reads these from the environment; the subshell keeps the token out of
# everything that runs after it.
(
    export ASTER_IMAGE ASTER_CONFIG MODEL_DIR RUN_DIR ASTER_ROOT ASTER_TOKEN
    docker compose up -d --wait
) || { echo "run.sh: the stack never became healthy; docker compose logs" >&2; exit 1; }

# 2. The stream, through reef-eval in an ephemeral uvx environment

# Per-session accept/style metrics, when a key is present: learning_curve.py tails
# the lab, because the judge's verdict lands there rather than in aster.
if [ -n "${WANDB_API_KEY:-}" ]; then
    uv run --no-project --with wandb "$PWD/results/learning_curve.py" \
        --lab "$RUN_DIR/lab" --aster-url "$ASTER_URL" --aster-token "$ASTER_TOKEN" \
        --wandb-dir "$RUN_DIR/lab" > "$RUN_DIR/learning_curve.log" 2>&1 &
    trap 'kill $! 2>/dev/null' EXIT
fi

echo "==> [2/2] streaming $TASKS as '$STREAM_NAME' (agent: harness:HermesStreamAgent)"
ASTER_TOKEN="$ASTER_TOKEN" uvx \
    --from "reef-eval[harbor]" \
    --with-editable "$PWD" \
    --with reef-client \
    reef-eval stream "$TASKS" --name "$STREAM_NAME" \
        --agent harness:HermesStreamAgent \
        --agent-arg kwargs="{\"aster_url\": \"$ASTER_URL\"}" \
        --agent-arg extra_allowed_hosts="[\"$HOST_IP\"]" \
        --lab "$RUN_DIR/lab" \
        "$@"

echo "==> done; reef-eval lab at $RUN_DIR/lab (stack still serving at $ASTER_URL)"
echo "    sessions-to-adaptation = reef_eval.metrics.learning_curve over the stream's rewards"
