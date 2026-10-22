# Grafana and SQL Server Session Analysis

Find SQL/Yeastar sessions that are absent from Grafana, then identify customer
messages that have not received an API or agent reply and have never been
picked up by an agent. All time ranges use **WIB (Asia/Jakarta, UTC+07:00)**.

## Setup

Run these commands from the project root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Chrome is required. Selenium downloads ChromeDriver automatically when needed.
Set `GRAFANA_PASSWORD`, or save the password in `robot/.grafana-password`.
That local file is ignored by Git.

For SQL Server, install the ODBC driver specified by `DB_DRIVER`, copy
`.env.example` to `.env`, and fill in the database connection settings.
Keep credentials local; `.env` is ignored by Git.

Both SQL scripts use the same connection setup and a 15-second connection
timeout. This Mac uses a verified Microsoft driver under `.odbc-driver/`;
its local ODBC configuration is selected automatically when present.
That directory is ignored by Git. Other machines need their own driver
installation matching `DB_DRIVER`.

## Run the complete workflow

```sh
bash scripts/run-workflow.sh
```

The default range is **yesterday at 16:00:00 through today at 16:00:00 WIB**.
Run after 16:00 to collect a complete daily period. Running earlier still
uses today's 16:00 cutoff, so today's data will be incomplete.

The workflow runs these steps in order and stops if any step fails:

1. Download the Grafana CSV, wait for completion, and process that specific file.
2. Query SQL Server using the exact time range selected in Grafana.
3. Find SQL/Yeastar sessions missing from Grafana and check their full histories.

`data/processed/merged.csv` is replaced on each run. Older downloads are not
combined. Selenium verifies the selected timestamps in the Grafana URL and
saves them to `data/processed/time_range.json`. SQL reads that file and uses
the same inclusive start/end bounds rather than calculating new dates.
This assumes `MsgTime_c` contains local WIB timestamps.

These are manual commands; the scripts do not schedule themselves.

## Date and time examples

### 1. Default daily range

```sh
bash scripts/run-workflow.sh
```

For example, running on October 22, 2026 at 17:00 requests October 21 at
16:00:00 through October 22 at 16:00:00 WIB.

### 2. Custom dates and times

```sh
bash scripts/run-workflow.sh \
  --from "2026-10-18 08:30:00" \
  --to "2026-10-20 17:45:30"
```

This requests October 18 at 08:30:00 through October 20 at 17:45:30 WIB.
The interval does not need to be 24 hours. SQL uses the same timestamps.

- Supply **both** `--from` and `--to`.
- Use **`YYYY-MM-DD HH:MM:SS`**, including seconds.
- Quote each timestamp because it contains a space.
- `--from` must be earlier than `--to`.
- Custom parameters apply only to that invocation. The next invocation
  without parameters returns to the default daily range.
- Invalid ranges stop before the browser or SQL query starts.
- For multiline shell commands, `\` must be the final character on its line;
  do not leave a space after it.

### 3. Headless Chrome

```sh
bash scripts/run-workflow.sh \
  --from "2026-10-20 16:00:00" \
  --to "2026-10-21 16:00:00" \
  --variable BROWSER:headlesschrome
```

If Selenium Manager is waiting for an online driver lookup and a compatible
ChromeDriver is already cached, use:

```sh
SE_OFFLINE=true bash scripts/run-workflow.sh --variable BROWSER:headlesschrome
```

This disables driver downloads and metadata requests, not Grafana or SQL
network access. A cached compatible driver is required for this option.

### 4. Download and process CSV only

```sh
bash robot/run-test.sh \
  --from "2026-10-20 09:00:00" \
  --to "2026-10-20 12:00:00"
```

This does not run SQL or matching. After a successful download, those steps
can also be run separately:

```sh
.venv/bin/python scripts/sql_server.py
.venv/bin/python scripts/match_sessions.py
```

Separate SQL runs use the saved `time_range.json`, even on another date.
The browser stage must complete successfully first to create both that
file and `merged.csv`.

## Session matching rules

The initial comparison follows `notebooks/cek.ipynb`:

```text
candidates = SQL/Yeastar session IDs - Grafana session IDs
```

`unmatched_sessions.csv` contains one row per candidate, with `session_id`,
`first_msg_time`, and `last_msg_time` from SQL. IDs are trimmed and treated
as strings to preserve leading zeros.

The detail query checks each candidate's full history:

- Find the latest `external -> api` message with `MsgType_c = 'in'`.
- Order messages by `MsgTime_c`, then `MsgID_c` when timestamps are equal.
- Exclude the session if a later `out` message goes to `external` from
  either `api` or `extension`.
- Exclude the session if it **has ever been picked up by an agent**:
  `FromType_c = extension`, `MsgType_c = system`, `MsgTypeCode_c = 5`.
  A pickup before the latest customer message also excludes the session.
- An API transfer to a queue (code `6`) alone does not exclude a session.
- Ignore system closure messages. A session does not need to be closed.
- Do not limit the number of messages; repeated customer messages without
  a reply are still eligible.
- An old reply does not cover a newer unanswered customer message.

`unmatched_session_details.csv` contains the latest unanswered customer
message for each final session. `TotalRows` is informational, not a filter.
The history check is intentionally not limited to the download interval so
replies on other dates are recognized. Detail timestamps may therefore fall
outside the candidate search range. Sessions outside the initial candidate
set are not checked.

Examples verified directly against SQL Server:

| Session | History | Result |
|---|---|---|
| `204554` | Incoming message followed by an API `out` reply | Excluded |
| `205111` | API handoff followed by an agent `out` reply | Excluded |
| `201420` | Agent pickup, code `5`, without an `out` reply | Excluded |
| `196772` | Incoming message without an `out` reply, later closed by the system | Abandoned candidate |
| `196777` | Two incoming images without an `out` reply, later closed by the system | Abandoned candidate |

The notebook contains historical execution output. Rerun its cells to
compare current inputs. See the [workflow investigation](docs/alur-session.md).

## Terminal output

```text
[1/3] Download Grafana data and process the latest CSV
Time range (WIB): ... -> ...
Opening Grafana and signing in...
Applying the Yeastar log filter...
Downloading the CSV and waiting for completion...
Grafana rows: 114; 93 unique sessions
CSV timestamps: ... -> ...
Source CSV: ...
Temporary summary: ...
Grafana and CSV processing: PASS

[2/3] Fetch SQL Server sessions for the Grafana time range
SQL time parameters (WIB): ... -> ... (inclusive, from Grafana)
SQL unique sessions: 138 (one row per session, not all messages)
...

[3/3] Match sessions and fetch UD39 details
...
Final session IDs (2):
  <session_id_1>
  <session_id_2>
```

Only final session IDs that pass the reply and pickup checks are listed.
All initial candidates remain in `data/results/unmatched_sessions.csv`.
Repeated Robot Framework banners and progress markers are hidden; errors
and warnings remain enabled. Full logs are in `reports/robot/log.html`.
For verbose debugging, append `--console verbose --consolemarkers off`.

## Counts and temporary summaries

The terminal reports Grafana CSV row counts, unique session counts, and the
oldest/newest CSV timestamps. Original CSV downloads remain in
`data/downloads/`; the summary records the exact source filename.

- `data/processed/grafana_summary.json`: source CSV, requested time range,
  row/session counts, and observed Grafana timestamps.
- `data/sql/sql_summary.json`: SQL time parameters, session count, and
  observed SQL timestamps.

Each stage replaces its summary on each run. These files are ignored by Git.
SQL groups messages by session, so its row count represents unique sessions,
not individual messages. Initial SQL result timestamps are checked against
the Grafana time range.

An empty Grafana CSV, or one without session IDs, stops the workflow before
SQL. The zero-count Grafana summary is still saved for inspection. Manual
matching also rejects empty Grafana input to avoid incorrectly marking every
SQL session as missing. When a workflow stops, earlier SQL/detail output may
still exist; check the summaries and execution status before using results.

## Run multiple dates, one day at a time

For September 23 through October 21, 2026:

```sh
.venv/bin/python -u scripts/run-daily.py \
  --start-date 2026-09-23 \
  --end-date 2026-10-21
```

The runner executes the complete workflow **sequentially**, always headless,
from **00:00:00 through 23:59:59 WIB** for one date before starting the next.
Headless browsers close automatically after each test, including failures.
Each date has a separate output folder:

```text
data/daily/2026-09-23/
  console.log
  status.json
  grafana_raw.csv
  grafana_summary.json
  merged.csv
  time_range.json
  sql_query_results.csv
  sql_summary.json
  unmatched_sessions.csv
  unmatched_session_details.csv
```

Fresh Robot Framework reports are also copied into that date's folder.
The overall summaries are saved to:

```text
data/daily/summary_2026-09-23_2026-10-21/summary.csv
data/daily/summary_2026-09-23_2026-10-21/session_ids.csv
```

`summary.csv` records each date's status, counts, and final IDs.
`session_ids.csv` lists final IDs without duplicates and the dates they
appeared. Summaries are updated after every date while the runner continues.

Failed dates, including empty Grafana downloads, are marked `failed` and
excluded from the successful ID summary. The runner continues to the next
date and exits unsuccessfully if any dates remain unresolved. Run the same
command again to resume: successful dates are reused only when their saved
matching-rule hash matches the current rules; failed dates are retried.
Rule changes invalidate old cached results. Existing summaries remain
historical snapshots until the runner is executed again.

To refresh a successful date, remove that date's output folder before
rerunning. The `verified_empty` status is reserved for independently checked
empty dates; it is not automatically assigned to empty downloads. For
October 18, 2026, all 55 SQL sessions were checked independently and none
had an unanswered customer-to-API message. Evidence is in
`data/daily/2026-10-18/empty_verification.json`. This status can also be
reused when its matching-rule hash is current.

Without parameters, the start date is September 23, 2026 and the end date
is today in WIB. Today's data includes only messages available at execution
time, even though its requested end is 23:59:59. Daily requests do not
automatically guarantee that Loki row limits are avoided; inspect row
counts and timestamp coverage in each date's summary.

## Output files

- `data/downloads/*.csv`: original source downloads.
- `data/processed/merged.csv`: processed latest download with `session_id`.
- `data/processed/grafana_summary.json`: temporary Grafana counts and source metadata.
- `data/processed/time_range.json`: exact Grafana start/end and timezone used by SQL.
- `data/sql/sql_query_results.csv`: SQL sessions and their first/last message times.
- `data/sql/sql_summary.json`: SQL parameters, counts, and observed timestamps.
- `data/results/unmatched_sessions.csv`: initial SQL/Yeastar candidates missing from Grafana.
- `data/results/unmatched_session_details.csv`: final unanswered customer messages.
- `reports/robot/report.html`: latest Selenium test report.

## Project layout

```text
scripts/             CSV processing, SQL queries, matching, and runners
robot/               Selenium test, runner, and Selenium requirements
notebooks/           Exploratory notebook; run its setup cell first
tests/               Local tests without a live database connection
data/downloads/      Original CSV downloads
data/processed/      Latest processed CSV and Grafana summaries
data/sql/            Current SQL results and summary
data/results/        Current matching candidates and final details
data/daily/          Archived daily runs and combined ID summaries
data/reference/      Historical CSV inputs used by the notebook
reports/robot/       Current Robot Framework logs and screenshots
```

Current outputs are ignored by Git. Unused historical output and duplicate
CSV files have been removed. Reference files remain in `data/reference/`.
The notebook performs historical comparisons and is not part of the daily
workflow. Customer message contents and original source data are preserved
in their original language.

## Local checks

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Tests cover file selection, output replacement, date ranges, row summaries,
SQL time parameters, matching direction, reply/pickup rules, daily archives,
and cache handling. They use local fixtures and a fake database connection;
a working ODBC driver and `.env` are needed for live SQL runs.
