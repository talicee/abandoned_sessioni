import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from datetime import timedelta

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import match_sessions
import sql_server


class WorkflowTests(unittest.TestCase):
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

    def test_matching_uses_latest_processed_csv_and_preserves_id_strings(self):
        self.assertEqual(match_sessions.MERGED_CSV, ROOT / "data/processed/merged.csv")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            merged = folder / "merged.csv"
            merged.write_text("session_id\n001\n002\n002\n")
            sql = folder / "sql.csv"
            sql.write_text("session_id\n001\n")
            unmatched = folder / "results/unmatched.csv"
            details = folder / "results/details.csv"
            with patch.object(match_sessions, "MERGED_CSV", merged), patch.object(match_sessions, "SQL_RESULTS_CSV", sql), patch.object(match_sessions, "UNMATCHED_CSV", unmatched), patch.object(match_sessions, "DETAILS_CSV", details), patch.object(match_sessions, "query_unmatched_sessions", return_value=(["Key1"], [("002",)])) as query, patch("builtins.print") as output:
                match_sessions.main()
            query.assert_called_once_with(["002"])
            output.assert_any_call("Session ID tidak ditemukan di SQL:")
            output.assert_any_call("  002 (2 baris di CSV)")
            with unmatched.open(encoding="utf-8-sig", newline="") as file:
                self.assertEqual(list(csv.DictReader(file)), [{"session_id": "002", "merged_count": "2"}])
            self.assertTrue(details.is_file())


if __name__ == "__main__":
    unittest.main()
