#!/bin/bash
set -e
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/robot ]; then
    python3 -m venv .venv
    .venv/bin/python -m pip install -r robot/requirements.txt
fi
export SE_CACHE_PATH="$PWD/.selenium-cache"
if [ -z "${GRAFANA_PASSWORD:-}" ] && [ -f robot/.grafana-password ]; then
    GRAFANA_PASSWORD=$(cat robot/.grafana-password)
    export GRAFANA_PASSWORD
fi
.venv/bin/robot --outputdir reports/robot "$@" robot/test.robot
