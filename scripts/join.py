#

import csv
import re
import argparse
import json
from datetime import datetime
from pathlib import Path

SESSION_ID_PATTERN = re.compile(r'session_id[^0-9]*([0-9]+)')

def main():
    parser = argparse.ArgumentParser(description="Process the latest Grafana CSV and extract session IDs.")
    root = Path(__file__).resolve().parent.parent
    parser.add_argument("input", nargs="?", type=Path, default=root / "data" / "downloads")
    parser.add_argument("--output", type=Path, default=root / "data" / "processed" / "merged.csv")
    parser.add_argument("--from", dest="from_time")
    parser.add_argument("--to", dest="to_time")
    args = parser.parse_args()
    source = args.input.resolve()
    output_path = args.output.resolve()
    if source.is_dir():
        candidates = [path for path in source.glob("*.csv") if path != output_path and path.name != "merged.csv"]
        if not candidates:
            raise FileNotFoundError("No input CSV files found")
        source = max(candidates, key=lambda path: path.stat().st_mtime_ns)
    if source == output_path:
        raise ValueError("Input must be a downloaded CSV, not merged.csv")
    input_paths = [source]

    rows = []
    fieldnames = None
    for path in input_paths:
        with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None or "Time" not in reader.fieldnames:
                raise ValueError(f"{path.name} is missing a 'Time' column")
            if "Line" not in reader.fieldnames:
                raise ValueError(f"{path.name} is missing a 'Line' column")
            if fieldnames is None:
                fieldnames = list(reader.fieldnames)
            elif reader.fieldnames != fieldnames:
                raise ValueError(f"{path.name} has a different CSV header")

            for line_number, row in enumerate(reader, start=2):
                try:
                    timestamp = datetime.strptime(row["Time"], "%Y-%m-%d %H:%M:%S")
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"Invalid Time in {path.name}, row {line_number}: {row['Time']!r}"
                    ) from error
                match = SESSION_ID_PATTERN.search(row["Line"] or "")
                row["session_id"] = match.group(1) if match else ""
                rows.append((timestamp, row))

    if fieldnames is None:
        raise FileNotFoundError("No input CSV files found")

    fieldnames.append("session_id")
    rows.sort(key=lambda item: item[0])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(row for _, row in rows)

    extracted = sum(bool(row.get("session_id")) for _, row in rows)
    summary = {
        "source_csv": str(source),
        "processed_csv": str(output_path),
        "from": args.from_time,
        "to": args.to_time,
        "timezone": "Asia/Jakarta",
        "row_count": len(rows),
        "unique_session_count": len({row["session_id"] for _, row in rows if row["session_id"]}),
        "rows_with_session_id": extracted,
        "earliest_time": rows[0][0].isoformat(sep=" ") if rows else None,
        "latest_time": rows[-1][0].isoformat(sep=" ") if rows else None,
    }
    summary_path = output_path.with_name("grafana_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Grafana: {len(rows)} baris, {summary['unique_session_count']} session unik")
    print(f"Timestamp CSV: {summary['earliest_time']} -> {summary['latest_time']}")
    print(f"CSV sumber: {source}")
    print(f"Ringkasan sementara: {summary_path}")
    if not rows or not extracted:
        parser.exit(1, "CSV Grafana kosong atau tanpa session ID. SQL dan matching dihentikan; periksa query, loading, dan rentang Grafana.\n")


if __name__ == "__main__":
    main()
