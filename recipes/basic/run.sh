#!/bin/bash
# Serve + run. Setup (once): see README. State and logs go to ./work.
set -e
cd "$(dirname "$0")"

mkdir -p work

# Start Aster from the external-provider stack, with the local example's
# credential and state directory overriding the deployment defaults
# (`aster serve -c <stack> --<section.field> <value>`); stop it again when this
# script exits. ASTER_UPSTREAM_URL and ASTER_UPSTREAM_API_KEY come from your
# environment.
export ASTER_TOKEN=aster-local
PYTHONPATH=../.. python3 -m aster serve -c "$PWD/external-provider.yaml" \
    --storage.agent-record-dir work/agent-record \
    --storage.artifact-repository work/artifacts.git \
    --storage.artifact-work-dir work/artifact-work \
    --storage.artifact-cache-dir work/artifact-cache \
    > work/aster.log 2>&1 &
aster_pid=$!
trap 'kill "$aster_pid" 2>/dev/null || true; wait "$aster_pid" 2>/dev/null || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Aster enforces the YAML ready_timeout and exits if startup fails.
while kill -0 "$aster_pid" 2>/dev/null; do
    curl -sf --max-time 5 http://127.0.0.1:8900/healthz > /dev/null && break
    sleep 1
done
if ! kill -0 "$aster_pid" 2>/dev/null; then
    echo "Aster failed to start. See $PWD/work/aster.log" >&2
    exit 1
fi

python3 run.py
