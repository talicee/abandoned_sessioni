import csv
from pathlib import Path

import pandas as pd

from sql_server import make_connection


BASE_DIR = Path(__file__).resolve().parent.parent
MERGED_CSV = BASE_DIR / "data" / "processed" / "merged.csv"
SQL_RESULTS_CSV = BASE_DIR / "data" / "sql" / "sql_query_results.csv"
UNMATCHED_CSV = BASE_DIR / "data" / "results" / "unmatched_sessions.csv"
DETAILS_CSV = BASE_DIR / "data" / "results" / "unmatched_session_details.csv"
SQL_ID_BATCH_SIZE = 2000

DETAIL_COLUMNS = [
    "Company", "Key1", "Key2", "Key3", "Key4", "Key5",
    "RawLoadID_c", "CnvID_c", "MsgID_c", "MsgTime_c",
    "FromType_c", "FromName_c", "FromExternalNum_c", "FromExtNum_c",
    "ToType_c", "ToName_c", "ToExternalNum_c", "ToExtNum_c",
    "MsgType_c", "MsgTypeCode_c", "MsgBody_c", "MsgParam_c",
    "TotalRows", "rn",
]

SQL_TEMPLATE = """
WITH AllRows AS (
    SELECT Company, Key1, Key2, Key3, Key4, Key5,
           RawLoadID_c, CnvID_c, MsgID_c, MsgTime_c,
           FromType_c, FromName_c, FromExternalNum_c, FromExtNum_c,
           ToType_c, ToName_c, ToExternalNum_c, ToExtNum_c,
           MsgType_c, MsgTypeCode_c, MsgBody_c, MsgParam_c,
           COUNT(*) OVER (PARTITION BY Key1) AS TotalRows
    FROM UD39
    WHERE Key5 = ?
      AND Key1 IN ({placeholders})
),
Ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY Key1 ORDER BY (SELECT NULL)) AS rn
    FROM AllRows
    WHERE (FromType_c = 'API' OR ToType_c = 'API')
      AND TotalRows <= 3
)
SELECT * FROM Ranked WHERE rn = 1
ORDER BY Key1;
"""


def read_session_ids(csv_path):
    """Read, trim, and return non-empty session IDs from a CSV."""
    frame = pd.read_csv(
        csv_path,
        usecols=["session_id"],
        dtype={"session_id": "string"},
    )
    session_ids = frame["session_id"].dropna().str.strip()
    return session_ids[session_ids != ""]


def query_unmatched_sessions(session_ids):
    """Fetch matching UD39 rows for the unmatched IDs, in safe-sized batches."""
    rows = []
    columns = DETAIL_COLUMNS

    if not session_ids:
        return columns, rows

    with make_connection() as connection:
        cursor = connection.cursor()
        try:
            for start in range(0, len(session_ids), SQL_ID_BATCH_SIZE):
                batch = session_ids[start : start + SQL_ID_BATCH_SIZE]
                placeholders = ", ".join("?" for _ in batch)
                query = SQL_TEMPLATE.format(placeholders=placeholders)
                cursor.execute(query, "ChatMessage", *batch)
                if start == 0:
                    columns = [column[0] for column in cursor.description]
                rows.extend(cursor.fetchall())
        finally:
            cursor.close()

    return columns, rows


def main():
    merged_ids = read_session_ids(MERGED_CSV)
    sql_ids = read_session_ids(SQL_RESULTS_CSV)
    UNMATCHED_CSV.parent.mkdir(parents=True, exist_ok=True)

    # Keep one output row per ID and include its frequency in merged.csv.
    merged_counts = merged_ids.value_counts()
    sql_id_set = set(sql_ids)
    unmatched_counts = merged_counts[~merged_counts.index.isin(sql_id_set)]
    unmatched = unmatched_counts.rename_axis("session_id").reset_index(name="merged_count")
    unmatched.to_csv(UNMATCHED_CSV, index=False, encoding="utf-8-sig")

    # Read the saved unmatched list so the SQL query uses every output session ID.
    unmatched_frame = pd.read_csv(UNMATCHED_CSV, dtype={"session_id": "string"})
    unmatched_session_ids = unmatched_frame["session_id"].dropna().str.strip().tolist()
    unmatched_session_ids = [session_id for session_id in unmatched_session_ids if session_id]

    columns, rows = query_unmatched_sessions(unmatched_session_ids)
    with DETAILS_CSV.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(columns)
        writer.writerows(rows)

    print(f"Unique session IDs in merged.csv: {len(merged_counts)}")
    print(f"Unique session IDs in sql_query_results.csv: {len(sql_id_set)}")
    print(f"Unmatched IDs from merged.csv: {len(unmatched_session_ids)}")
    print(f"UD39 rows returned: {len(rows)}")
    print(f"Saved unmatched IDs to {UNMATCHED_CSV}")
    print(f"Saved SQL details to {DETAILS_CSV}")


if __name__ == "__main__":
    main()
