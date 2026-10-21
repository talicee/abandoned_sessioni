#!/bin/bash
set -e
cd "$(dirname "$0")/.."
robot_args=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --from|--to)
            if [ "$#" -lt 2 ] || [ -z "$2" ]; then
                printf 'Parameter %s perlu nilai "YYYY-MM-DD HH:MM:SS".\n' "$1" >&2
                exit 2
            fi
            if [ "$1" = --from ]; then
                robot_args+=(--variable "FROM_TIME:$2")
            else
                robot_args+=(--variable "TO_TIME:$2")
            fi
            shift 2
            ;;
        *) robot_args+=("$1"); shift ;;
    esac
done
if [ ! -x .venv/bin/robot ]; then
    python3 -m venv .venv
    .venv/bin/python -m pip install -r robot/requirements.txt
fi
export SE_CACHE_PATH="$PWD/.selenium-cache"
if [ -z "${GRAFANA_PASSWORD:-}" ] && [ -f robot/.grafana-password ]; then
    GRAFANA_PASSWORD=$(cat robot/.grafana-password)
    export GRAFANA_PASSWORD
fi
.venv/bin/robot --console quiet --consolemarkers off --outputdir reports/robot "${robot_args[@]}" robot/test.robot
printf 'Grafana dan pemrosesan CSV: PASS\nLaporan: reports/robot/report.html\n'
