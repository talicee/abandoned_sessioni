import csv
from datetime import date
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("daily", ROOT / "scripts/run-daily.py")
daily = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daily)


class DailyTests(unittest.TestCase):
    def test_summary_deduplicates_ids_and_keeps_failed_days_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            records = [
                {"date": "2026-09-23", "status": "success", "session_ids": "001;002"},
                {"date": "2026-09-24", "status": "failed", "session_ids": "999"},
                {"date": "2026-09-25", "status": "success", "session_ids": "002;003"},
            ]
            self.assertEqual(daily.summarize(records, Path(tmp)), ["001", "002", "003"])
            with (Path(tmp) / "session_ids.csv").open(encoding="utf-8-sig") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(rows[1], {"session_id": "002", "dates": "2026-09-23;2026-09-25"})

    def test_successful_day_is_resumed_without_running_workflow_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "2026-09-23"
            folder.mkdir()
            record = {"date": "2026-09-23", "status": "success", "session_ids": "001"}
            (folder / "status.json").write_text(json.dumps(record))
            with patch.object(daily, "DAILY", Path(tmp)), patch.object(daily.subprocess, "Popen") as process:
                self.assertEqual(daily.run_day(date(2026, 9, 23)), record)
                process.assert_not_called()

    def test_failed_day_does_not_reuse_previous_sql_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data/processed").mkdir(parents=True)
            (root / "data/sql").mkdir()
            (root / "data/downloads").mkdir()
            raw = root / "data/downloads/empty.csv"
            raw.write_text("Time,Line\n")
            (root / "data/processed/grafana_summary.json").write_text(json.dumps({"from": "2026-09-23 00:00:00", "to": "2026-09-23 23:59:59", "row_count": 0, "unique_session_count": 0, "source_csv": str(raw)}))
            (root / "data/sql/sql_summary.json").write_text(json.dumps({"from": "2026-09-22 00:00:00", "to": "2026-09-22 23:59:59", "session_count": 999}))
            process = MagicMock()
            process.__enter__.return_value = process
            process.stdout = iter(["Grafana empty\n"])
            process.wait.return_value = 1
            with patch.object(daily, "ROOT", root), patch.object(daily, "DAILY", root / "data/daily"), patch.object(daily.subprocess, "Popen", return_value=process):
                record = daily.run_day(date(2026, 9, 23))
            self.assertEqual(record["status"], "failed")
            self.assertEqual(record["grafana_rows"], 0)
            self.assertNotIn("sql_sessions", record)
            self.assertNotIn("abandoned_count", record)

    def test_day_archives_only_its_own_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                "processed/merged.csv": "Time,Line,session_id\n2026-09-23 10:00:00,in,001\n",
                "processed/time_range.json": "{}",
                "sql/sql_query_results.csv": "session_id\n001\n002\n",
                "results/unmatched_sessions.csv": "session_id\n002\n",
                "results/unmatched_session_details.csv": "Key1\n002\n",
                "downloads/raw.csv": "Time,Line\n2026-09-23 10:00:00,in\n",
            }
            for name, contents in files.items():
                path = root / "data" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents)
            window = {"from": "2026-09-23 00:00:00", "to": "2026-09-23 23:59:59"}
            (root / "data/processed/grafana_summary.json").write_text(json.dumps({**window, "row_count": 1, "unique_session_count": 1, "source_csv": str(root / "data/downloads/raw.csv")}))
            (root / "data/sql/sql_summary.json").write_text(json.dumps({**window, "session_count": 2}))
            process = MagicMock()
            process.__enter__.return_value = process
            process.stdout = iter(["workflow complete\n"])
            process.wait.return_value = 0
            with patch.object(daily, "ROOT", root), patch.object(daily, "DAILY", root / "data/daily"), patch.object(daily.subprocess, "Popen", return_value=process) as run:
                record = daily.run_day(date(2026, 9, 23))
            self.assertEqual(record["abandoned_count"], 1)
            self.assertEqual(record["session_ids"], "002")
            self.assertTrue((root / "data/daily/2026-09-23/grafana_raw.csv").is_file())
            command = run.call_args.args[0]
            self.assertIn("2026-09-23 00:00:00", command)
            self.assertIn("2026-09-23 23:59:59", command)
            self.assertIn("BROWSER:headlesschrome", command)


if __name__ == "__main__":
    unittest.main()
