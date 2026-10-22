#!/bin/bash
set -e
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
.venv/bin/python -c 'import robot, SeleniumLibrary, pandas, pyodbc' 2>/dev/null || .venv/bin/python -m pip install -r requirements.txt
printf '\n[1/3] Download Grafana data and process the latest CSV\n'
bash robot/run-test.sh "$@"
printf '\n[2/3] Fetch SQL Server sessions for the Grafana time range\n'
.venv/bin/python scripts/sql_server.py
printf '\n[3/3] Match sessions and fetch UD39 details\n'
.venv/bin/python scripts/match_sessions.py
