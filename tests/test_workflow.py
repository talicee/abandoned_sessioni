import csv
import json
import os
import sqlite3
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import match_sessions
import sql_server
from time_range import resolve_time_range


class WorkflowTests(unittest.TestCase):
    def test_abandoned_query_checks_latest_customer_message_without_message_limit(self):
        with sqlite3.connect(":memory:") as connection:
            columns = match_sessions.DETAIL_COLUMNS[:-2]
            connection.execute("CREATE TABLE UD39 (" + ", ".join(
                name + (" INTEGER" if name in ("MsgID_c", "RawLoadID_c", "CnvID_c", "MsgTypeCode_c") else " TEXT")
                for name in columns
            ) + ")")

            def message(session, number, kind, timestamp=None):
                source, target = {"in": ("external", "API"), "out": ("API", "external"), "system": ("external", "")}[kind]
                connection.execute("INSERT INTO UD39 (Key1,Key5,MsgID_c,MsgTime_c,FromType_c,ToType_c,MsgType_c) VALUES (?,?,?,?,?,?,?)",
                    (session, "ChatMessage", number, timestamp or f"2026-10-20 10:00:{number:02}", source, target, kind))

            message("answered", 1, "in"); message("answered", 2, "out"); message("answered", 3, "system")
            for number in range(1, 9):
                message("spam", number, "in")
            message("followup", 1, "in"); message("followup", 2, "out"); message("followup", 3, "in")
            message("open", 1, "in")
            message("systemonly", 1, "system")
            message("tiesanswered", 1, "in", "2026-10-20 11:00:00")
            message("tiesanswered", 2, "out", "2026-10-20 11:00:00")
            message("olderreply", 1, "in", "2026-10-20 12:00:00")
            message("olderreply", 2, "out", "2026-10-19 12:00:00")
            candidates = ["answered", "spam", "followup", "open", "systemonly", "tiesanswered", "olderreply"]
            result = connection.execute(match_sessions.SQL_TEMPLATE.format(placeholders=",".join("?" for _ in candidates)), ["ChatMessage", *candidates]).fetchall()
            actual = {row[columns.index("Key1")]: row for row in result}
            self.assertEqual(set(actual), {"spam", "followup", "open", "olderreply"})
            self.assertEqual(actual["spam"][columns.index("MsgID_c")], 8)
            self.assertEqual(actual["spam"][-2], 8)

    def test_default_range_stays_at_16_wib_before_and_after_cutoff(self):
        for hour in (10, 18):
            start, end = resolve_time_range(now=datetime(2028, 3, 1, hour, tzinfo=ZoneInfo("Asia/Jakarta")))
            self.assertEqual(start.isoformat(), "2028-02-29T16:00:00+07:00")
            self.assertEqual(end.isoformat(), "2028-03-01T16:00:00+07:00")

    def test_custom_range_preserves_dates_and_hours(self):
        start, end = resolve_time_range("2026-10-18 08:30:00", "2026-10-20 17:45:30")
        self.assertEqual(start.isoformat(), "2026-10-18T08:30:00+07:00")
        self.assertEqual(end.isoformat(), "2026-10-20T17:45:30+07:00")

    def test_invalid_custom_range_is_rejected(self):
        for start, end in [("2026-10-20 16:00:00", ""), ("", "2026-10-21 16:00:00"), ("2026-02-30 16:00:00", "2026-03-01 16:00:00"), ("2026-10-21 16:00:00", "2026-10-20 16:00:00"), ("2026-10-21 16:00:00", "2026-10-21 16:00:00")]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                resolve_time_range(start, end)

    def test_only_latest_download_is_processed_and_output_is_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name, session, mtime in [("old.csv", "111", 1000), ("new.csv", "222", 2000)]:
                path = folder / name
                path.write_text(f'Time,Line\n2026-10-21 16:00:00,session_id: {session}\n')
                os.utime(path, (mtime, mtime))
            output = folder / "processed" / "merged.csv"
            for source, expected in [(folder, "222"), (folder / "old.csv", "111"), (folder, "222")]:
                subprocess.run([sys.executable, str(ROOT / "scripts/join.py"), str(source), "--output", str(output)], check=True, capture_output=True)
                with output.open(encoding="utf-8-sig", newline="") as file:
                    rows = list(csv.DictReader(file))
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["session_id"], expected)

    def test_sql_uses_exact_saved_grafana_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            connection = MagicMock()
            cursor = connection.__enter__.return_value.cursor.return_value
            cursor.description = [("session_id",), ("first_msg_time",), ("last_msg_time",)]
            cursor.fetchall.return_value = []
            env = {key: "test" for key in ("DB_DRIVER", "DB_SERVER", "DB_DATABASE", "DB_USERNAME", "DB_PASSWORD")}
            range_file = Path(tmp) / "time_range.json"
            range_file.write_text(json.dumps({"from": "2028-02-29 16:00:00", "to": "2028-03-01 16:00:00", "timezone": "Asia/Jakarta"}))
            with patch.dict(os.environ, env), patch.object(sql_server, "TIME_RANGE_FILE", range_file), patch.object(sql_server, "load_env_file"), patch.object(sql_server.pyodbc, "connect", return_value=connection), patch.object(sql_server, "OUTPUT_FILE", Path(tmp) / "sql/results.csv"):
                sql_server.main()
            query, kind, start, end = cursor.execute.call_args.args
            self.assertEqual(kind, "ChatMessage")
            self.assertEqual(end - start, timedelta(days=1))
            self.assertEqual(end.strftime("%H:%M:%S"), "16:00:00")
            self.assertEqual(start.isoformat(sep=" "), "2028-02-29 16:00:00")
            self.assertEqual(end.isoformat(sep=" "), "2028-03-01 16:00:00")
            self.assertIn("MsgTime_c >= ?", query)
            self.assertIn("MsgTime_c <= ?", query)

    def test_sql_requires_saved_grafana_window_before_connecting(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sql_server, "TIME_RANGE_FILE", Path(tmp) / "missing.json"), patch.object(sql_server, "make_connection") as connect:
                with self.assertRaises(FileNotFoundError):
                    sql_server.main()
                connect.assert_not_called()

    def test_matching_finds_sql_sessions_missing_from_grafana(self):
        self.assertEqual(match_sessions.MERGED_CSV, ROOT / "data/processed/merged.csv")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            merged = folder / "merged.csv"
            merged.write_text("session_id\n001\n002\n002\n")
            sql = folder / "sql.csv"
            sql.write_text("session_id,first_msg_time,last_msg_time\n001,2026-10-20 08:00:00,2026-10-20 09:00:00\n003,2026-10-20 10:00:00,2026-10-20 11:00:00\n003,2026-10-20 10:00:00,2026-10-20 11:00:00\n004,2026-10-20 12:00:00,2026-10-20 13:00:00\n")
            unmatched = folder / "results/unmatched.csv"
            details = folder / "results/details.csv"
            with patch.object(match_sessions, "MERGED_CSV", merged), patch.object(match_sessions, "SQL_RESULTS_CSV", sql), patch.object(match_sessions, "UNMATCHED_CSV", unmatched), patch.object(match_sessions, "DETAILS_CSV", details), patch.object(match_sessions, "query_unmatched_sessions", return_value=(["Key1"], [("003",)])) as query, patch("builtins.print") as output:
                match_sessions.main()
            query.assert_called_once_with(["003", "004"])
            output.assert_any_call("Session ID hasil akhir (1):")
            self.assertNotIn(unittest.mock.call("  004"), output.call_args_list)
            output.assert_any_call("  003")
            with unmatched.open(encoding="utf-8-sig", newline="") as file:
                self.assertEqual(list(csv.DictReader(file)), [{"session_id": "003", "first_msg_time": "2026-10-20 10:00:00", "last_msg_time": "2026-10-20 11:00:00"}, {"session_id": "004", "first_msg_time": "2026-10-20 12:00:00", "last_msg_time": "2026-10-20 13:00:00"}])
            self.assertTrue(details.is_file())


if __name__ == "__main__":
    unittest.main()
