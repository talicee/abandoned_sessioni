# Grafana and SQL Server Session Analysis

This workflow starts after `merged.csv` has already been created. It does not run `join.py`.

## Requirements

- Python 3
- The SQL Server ODBC driver named by `DB_DRIVER` in `.env`
- Python packages `pandas` and `pyodbc`
- A `.env` file in this folder with these settings:

```dotenv
DB_DRIVER=ODBC Driver 18 for SQL Server
DB_SERVER=your-server
DB_DATABASE=your-database
DB_USERNAME=your-username
DB_PASSWORD=your-password
```

Replace the example values with your connection details. `.env` is ignored by Git, so keep the real credentials there and do not commit them.

Install the Python packages from PowerShell if needed:

```powershell
py -3 -m pip install pandas pyodbc
```

## Run the workflow

Make sure `merged.csv` is in this folder, then run these commands from PowerShell:

```powershell
py -3 sql_server.py
py -3 match_sessions.py
```

Run the commands in order. The first script queries SQL Server for ChatMessage session IDs on October 20, 2026 and saves `sql_query_results.csv`. The second script compares those IDs with the unique `session_id` values in `merged.csv`, saves the IDs missing from the SQL results to `unmatched_sessions.csv`, then queries SQL Server for details on those unmatched IDs.

## Output files

- `sql_query_results.csv` — session IDs and first/last message times from the initial SQL query.
- `unmatched_sessions.csv` — unique session IDs in `merged.csv` that were not found in `sql_query_results.csv`, with their count in `merged.csv`.
- `unmatched_session_details.csv` — final SQL query results for the unmatched IDs. This is the final output of the workflow.
