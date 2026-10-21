#!/bin/bash
set -e
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
.venv/bin/python -c 'import robot, SeleniumLibrary, pandas, pyodbc' 2>/dev/null || .venv/bin/python -m pip install -r requirements.txt
bash robot/run-test.sh "$@"
.venv/bin/python scripts/sql_server.py
.venv/bin/python scripts/match_sessions.py
