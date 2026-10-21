# Grafana and SQL Server Session Analysis

## Setup

Create a Python environment and install the dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Chrome is required for Selenium. ChromeDriver is downloaded automatically.
Set `GRAFANA_PASSWORD`, or save the Grafana password in the local file
`robot/.grafana-password`. That file is ignored by Git.

For SQL Server, install the ODBC driver named by `DB_DRIVER`, copy
`.env.example` to `.env`, and fill in the database connection settings.
Keep real credentials local; `.env` is ignored by Git.

## Run

Run after 16:00 WIB to collect a complete daily period:

```sh
bash robot/run-test.sh
.venv/bin/python scripts/sql_server.py
.venv/bin/python scripts/match_sessions.py
```

Run these commands in order, on the same day. Selenium selects yesterday
16:00 through today 16:00 in Grafana, waits for the CSV download, and runs
`scripts/join.py` on that specific download. `data/processed/merged.csv` is replaced
on each run; older downloads are not combined. Running before 16:00 still
selects today's 16:00 cutoff, so today's data will be incomplete.

The SQL query uses yesterday 16:00 (inclusive) through today 16:00
(exclusive), calculated in Asia/Jakarta. This assumes `MsgTime_c` stores
local WIB timestamps. `scripts/match_sessions.py` compares the downloaded session
IDs with the SQL results and queries details for unmatched sessions.
The SQL steps are run separately; the Selenium script does not connect to
SQL Server automatically.

## Output files

- `data/downloads/*.csv`: downloaded source CSV files.
- `data/processed/merged.csv`: processed latest download, with `session_id`.
- `reports/robot/report.html`: latest Selenium test report.
- `data/sql/sql_query_results.csv`: SQL session IDs and first/last message times.
- `data/results/unmatched_sessions.csv`: unmatched session IDs and their counts.
- `data/results/unmatched_session_details.csv`: SQL details for unmatched sessions.

## Project layout

```text
scripts/             CSV processing, SQL query, session matching
robot/               Selenium test, runner, Selenium requirements
notebooks/           Exploratory notebook (run its first setup cell first)
tests/               Local workflow tests without a database connection
data/downloads/      Source CSV downloads
data/processed/      Latest processed merged.csv
data/sql/            Current SQL query results
data/results/        Current unmatched IDs and SQL details
data/reference/      Two historical CSV inputs used by the notebook
reports/robot/       Current Robot Framework logs and screenshots
```

Current outputs are ignored by Git. Unused historical outputs and duplicate
CSV files have been removed; notebook reference inputs are kept in data/reference/. The exploratory notebook includes historical comparisons;
it does not run as part of the daily workflow.

## Check the code locally

```sh
.venv/bin/python -m unittest discover -s tests -v
```

These tests exercise file selection, output replacement, SQL query time
bounds, and ID matching with a fake database. They do not establish a live
SQL connection. A working SQL Server ODBC driver and `.env` are required
for the real SQL steps.
