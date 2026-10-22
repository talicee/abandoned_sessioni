"""Run the headless workflow one calendar day at a time and collect final IDs."""
import argparse
import csv
from datetime import date, datetime, timedelta
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DAILY = ROOT / "data" / "daily"


def matching_rule_hash():
    return hashlib.sha256((ROOT / "scripts" / "match_sessions.py").read_bytes()).hexdigest()


def summarize(records, output):
    output.mkdir(parents=True, exist_ok=True)
    fields = ["date", "status", "grafana_rows", "grafana_sessions", "sql_sessions", "candidate_count", "abandoned_count", "session_ids"]
    with (output / "summary.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: record.get(key, "") for key in fields} for record in records)
    ids = {}
    for record in records:
        if record["status"] == "success":
            for session_id in record.get("session_ids", "").split(";"):
                if session_id:
                    ids.setdefault(session_id, []).append(record["date"])
    with (output / "session_ids.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["session_id", "dates"])
        writer.writerows((session_id, ";".join(days)) for session_id, days in sorted(ids.items()))
    return sorted(ids)


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def run_day(day):
    rule_hash = matching_rule_hash()
    folder = DAILY / day.isoformat()
    status_file = folder / "status.json"
    if status_file.exists():
        saved = json.loads(status_file.read_text())
        if saved.get("status") in ("success", "verified_empty") and saved.get("matching_rule_hash") == rule_hash:
            print(f"{day}: memakai hasil tersimpan ({saved['status']}).", flush=True)
            return saved
    folder.mkdir(parents=True, exist_ok=True)
    start, end = f"{day} 00:00:00", f"{day} 23:59:59"
    command = ["bash", "scripts/run-workflow.sh", "--from", start, "--to", end, "--variable", "BROWSER:headlesschrome"]
    started_at = datetime.now().timestamp()
    print(f"\n=== {day}: 00:00:00 -> 23:59:59 WIB ===", flush=True)
    with (folder / "console.log").open("w") as log:
        with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
            returncode = process.wait()
    for name in ["output.xml", "log.html", "report.html"]:
        source = ROOT / "reports" / "robot" / name
        if source.is_file() and source.stat().st_mtime >= started_at:
            shutil.copy2(source, folder / name)
    record = {"date": str(day), "status": "success" if returncode == 0 else "failed", "command": command, "matching_rule_hash": rule_hash}
    for relative in ["processed/grafana_summary.json", "sql/sql_summary.json"]:
        source = ROOT / "data" / relative
        if source.exists():
            summary = json.loads(source.read_text())
            if summary.get("from") == start and summary.get("to") == end:
                shutil.copy2(source, folder / source.name)
                if "row_count" in summary:
                    record.update(grafana_rows=summary["row_count"], grafana_sessions=summary["unique_session_count"])
                    raw = Path(summary["source_csv"])
                    if raw.is_file():
                        shutil.copy2(raw, folder / "grafana_raw.csv")
                else:
                    record["sql_sessions"] = summary["session_count"]
    if returncode == 0:
        for relative in ["processed/merged.csv", "processed/time_range.json", "sql/sql_query_results.csv", "results/unmatched_sessions.csv", "results/unmatched_session_details.csv"]:
            source = ROOT / "data" / relative
            shutil.copy2(source, folder / source.name)
        candidates = csv_rows(folder / "unmatched_sessions.csv")
        details = csv_rows(folder / "unmatched_session_details.csv")
        ids = sorted({row["Key1"].strip() for row in details})
        record.update(candidate_count=len(candidates), abandoned_count=len(ids), session_ids=";".join(ids))
    status_file.write_text(json.dumps(record, indent=2))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2026, 9, 23))
    parser.add_argument("--end-date", type=date.fromisoformat, default=datetime.now(ZoneInfo("Asia/Jakarta")).date())
    args = parser.parse_args()
    if args.start_date > args.end_date:
        parser.error("start-date harus sebelum atau sama dengan end-date")
    records = []
    day = args.start_date
    report = DAILY / f"summary_{args.start_date}_{args.end_date}"
    while day <= args.end_date:
        record = run_day(day)
        records.append(record)
        summarize(records, report)
        day += timedelta(days=1)
    ids = summarize(records, report)
    failed = [record["date"] for record in records if record["status"] not in ("success", "verified_empty")]
    verified_empty = sum(record["status"] == "verified_empty" for record in records)
    print(f"\nSelesai: {len(records) - len(failed)}/{len(records)} tanggal diperiksa.")
    print(f"Workflow sukses: {len(records) - len(failed) - verified_empty}; kosong terverifikasi: {verified_empty}.")
    print(f"Session ID akhir tanpa duplikat ({len(ids)}):")
    for session_id in ids:
        print(f"  {session_id}")
    if not ids:
        print("  (tidak ada pada hari yang berhasil)")
    if failed:
        print("Hari belum berhasil: " + ", ".join(failed))
    print(f"Ringkasan per hari: {report / 'summary.csv'}")
    print(f"Daftar ID unik: {report / 'session_ids.csv'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
