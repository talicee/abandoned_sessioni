import csv
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pyodbc


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
OUTPUT_FILE = BASE_DIR / "data" / "sql" / "sql_query_results.csv"


def load_env_file(path):
    """Load simple KEY=VALUE entries without overriding existing environment variables."""
    if not path.is_file():
        raise FileNotFoundError(f"Environment file not found: {path}")

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()

        key, separator, value = line.partition("=")
        if not separator:
            continue

        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def odbc_value(value):
    """Brace an ODBC connection-string value and escape any closing braces."""
    value = str(value)
    if value.startswith("{") and value.endswith("}"):
        value = value[1:-1].replace("}}", "}")
    return "{" + value.replace("}", "}}") + "}"


def main():
    load_env_file(ENV_FILE)

    required = ("DB_DRIVER", "DB_SERVER", "DB_DATABASE", "DB_USERNAME", "DB_PASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing required .env values: " + ", ".join(missing))

    connection_string = ";".join(
        (
            f"DRIVER={odbc_value(os.environ['DB_DRIVER'])}",
            f"SERVER={odbc_value(os.environ['DB_SERVER'])}",
            f"DATABASE={odbc_value(os.environ['DB_DATABASE'])}",
            f"UID={odbc_value(os.environ['DB_USERNAME'])}",
            f"PWD={odbc_value(os.environ['DB_PASSWORD'])}",
            "Encrypt=yes",
            "TrustServerCertificate=yes",
        )
    )

    query = """
        SELECT  Key1 AS session_id,
                MIN(MsgTime_c) AS first_msg_time,
                MAX(MsgTime_c) AS last_msg_time
        FROM    UD39
        WHERE   Key5 = ?
          AND   MsgTime_c >= ?
          AND   MsgTime_c < ?
        GROUP BY Key1
        ORDER BY first_msg_time;
    """

    with pyodbc.connect(connection_string) as connection:
        cursor = connection.cursor()
        cutoff = datetime.now(ZoneInfo("Asia/Jakarta")).replace(
            hour=16, minute=0, second=0, microsecond=0, tzinfo=None
        )
        start = cutoff - timedelta(days=1)
        cursor.execute(query, "ChatMessage", start, cutoff)
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        cursor.close()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(columns)
        writer.writerows(rows)

    print(f"Saved {len(rows)} rows to {OUTPUT_FILE}")
    print(f"SQL time range (WIB): {start} to {cutoff} (exclusive)")


if __name__ == "__main__":
    main()
