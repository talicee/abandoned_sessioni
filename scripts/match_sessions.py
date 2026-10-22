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
RankedIncoming AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY Key1 ORDER BY MsgTime_c DESC, MsgID_c DESC
           ) AS rn
    FROM AllRows
    WHERE LOWER(FromType_c) = 'external'
      AND LOWER(ToType_c) = 'api'
      AND LOWER(MsgType_c) = 'in'
      AND MsgTime_c IS NOT NULL
)
SELECT incoming.*
FROM RankedIncoming AS incoming
WHERE incoming.rn = 1
  AND NOT EXISTS (
      SELECT 1 FROM AllRows AS pickup
      WHERE pickup.Key1 = incoming.Key1
        AND LOWER(pickup.FromType_c) = 'extension'
        AND LOWER(pickup.MsgType_c) = 'system'
        AND pickup.MsgTypeCode_c = 5
  )
  AND NOT EXISTS (
      SELECT 1 FROM AllRows AS reply
      WHERE reply.Key1 = incoming.Key1
        AND LOWER(reply.FromType_c) IN ('api', 'extension')
        AND LOWER(reply.ToType_c) = 'external'
        AND LOWER(reply.MsgType_c) = 'out'
        AND (
            reply.MsgTime_c > incoming.MsgTime_c
            OR (reply.MsgTime_c = incoming.MsgTime_c
                AND COALESCE(reply.MsgID_c, -1) > COALESCE(incoming.MsgID_c, -1))
        )
  )
ORDER BY incoming.Key1;
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
    """Return the latest unanswered customer message for each candidate session."""
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
    if merged_ids.empty:
        raise ValueError("Grafana tidak memiliki session ID. Matching dihentikan agar seluruh SQL tidak dianggap missing.")
    sql_frame = pd.read_csv(
        SQL_RESULTS_CSV,
        usecols=["session_id", "first_msg_time", "last_msg_time"],
        dtype={"session_id": "string"},
    )
    sql_frame["session_id"] = sql_frame["session_id"].str.strip()
    sql_frame = sql_frame[sql_frame["session_id"].notna() & sql_frame["session_id"].ne("")]
    UNMATCHED_CSV.parent.mkdir(parents=True, exist_ok=True)

    # Match cek.ipynb: SQL/Yeastar sessions absent from Grafana.
    merged_id_set = set(merged_ids)
    sql_id_set = set(sql_frame["session_id"])
    unmatched = (
        sql_frame[~sql_frame["session_id"].isin(merged_id_set)]
        .drop_duplicates(subset="session_id")
        .loc[:, ["session_id", "first_msg_time", "last_msg_time"]]
        .sort_values("session_id")
        .reset_index(drop=True)
    )
    unmatched.to_csv(UNMATCHED_CSV, index=False, encoding="utf-8-sig")

    # Read the saved unmatched list so the SQL query uses every output session ID.
    unmatched_frame = pd.read_csv(UNMATCHED_CSV, dtype={"session_id": "string"})
    unmatched_session_ids = unmatched_frame["session_id"].dropna().str.strip().tolist()
    unmatched_session_ids = [session_id for session_id in unmatched_session_ids if session_id]

    print("Cek balasan: seluruh riwayat kandidat; timestamp detail bisa di luar rentang pencarian.")
    columns, rows = query_unmatched_sessions(unmatched_session_ids)
    with DETAILS_CSV.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(columns)
        writer.writerows(rows)

    print(f"Unique session IDs in merged.csv: {len(merged_id_set)}")
    print(f"Unique session IDs in sql_query_results.csv: {len(sql_id_set)}")
    print(f"SQL/Yeastar session IDs missing from Grafana: {len(unmatched_session_ids)}")
    print(f"UD39 rows returned: {len(rows)}")
    print(f"Saved unmatched IDs to {UNMATCHED_CSV}")
    print(f"Saved SQL details to {DETAILS_CSV}")
    id_index = columns.index("Key1")
    final_session_ids = sorted({str(row[id_index]).strip() for row in rows})
    print(f"Session ID hasil akhir ({len(final_session_ids)}):")
    for session_id in final_session_ids:
        print(f"  {session_id}")
    if not final_session_ids:
        print("  (tidak ada)")


if __name__ == "__main__":
    main()
