#

import csv
import re
import argparse
from datetime import datetime
from pathlib import Path

SESSION_ID_PATTERN = re.compile(r'session_id[^0-9]*([0-9]+)')

def main():
    parser = argparse.ArgumentParser(description="Process the latest Grafana CSV and extract session IDs.")
    parser.add_argument("input", nargs="?", type=Path, default=Path(__file__).resolve().parent / "robot" / "downloads")
    source = parser.parse_args().input.resolve()
    folder = source if source.is_dir() else source.parent
    output_path = folder / "merged.csv"
    if source.is_dir():
        candidates = [path for path in source.glob("*.csv") if path != output_path]
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
    with output_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(row for _, row in rows)

    extracted = sum(bool(row.get("session_id")) for _, row in rows)
    print(f"Processed {len(rows)} rows from {source.name} into {output_path.name}")
    print(f"Extracted session_id for {extracted} rows")


if __name__ == "__main__":
    main()
