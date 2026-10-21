# Grafana and SQL Server Session Analysis

## Setup

Create a Python environment and install the dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Chrome is required for Selenium. ChromeDriver is downloaded automatically.
Set `GRAFANA_PASSWORD`, or save the Grafana password in the local file
`robot/.grafana-password`. That file is ignored by Git.

For SQL Server, install the ODBC driver named by `DB_DRIVER`, copy
`.env.example` to `.env`, and fill in the database connection settings.
Keep real credentials local; `.env` is ignored by Git.

## Run

Run after 16:00 WIB to collect a complete daily period:

```sh
bash scripts/run-workflow.sh
```

The runner stops if any step fails. By default, Selenium selects yesterday
16:00 through today 16:00 in Grafana, waits for the CSV download, and runs
`scripts/join.py` on that specific download. `data/processed/merged.csv` is replaced
on each run; older downloads are not combined. Running before 16:00 still
selects today's 16:00 cutoff, so today's data will be incomplete.

Selenium checks the applied Grafana URL against the requested timestamps,
then saves the exact selected start/end values to
`data/processed/time_range.json`. The SQL query reads that file and uses
the same start/end bounds, both inclusive. It does not calculate its own
dates, even when SQL runs on a different day. This assumes `MsgTime_c`
stores local WIB timestamps. `scripts/match_sessions.py` compares the downloaded session
IDs with the SQL results and queries details for unmatched sessions.
The full runner automatically runs `scripts/sql_server.py`, followed by
`scripts/match_sessions.py`. To run only the browser, use
`bash robot/run-test.sh`. SQL and matching can also be run separately:

```sh
.venv/bin/python scripts/sql_server.py
.venv/bin/python scripts/match_sessions.py
```

The browser must finish successfully first to create both `merged.csv`
and `time_range.json`. For a run without a visible browser window, use
`bash scripts/run-workflow.sh --variable BROWSER:headlesschrome`.

Both SQL scripts share one connection setup and a 15-second connection
timeout. On this Mac, the verified Microsoft driver is installed locally
under `.odbc-driver/`; the connection setup automatically uses its ODBC
configuration when present. This folder is ignored by Git. Other machines
need their own SQL Server ODBC driver installation matching `DB_DRIVER`.

## Contoh penggunaan tanggal dan jam

Jalankan dari folder utama proyek. Semua tanggal dan jam menggunakan **WIB
(Asia/Jakarta)**. Ini adalah perintah manual; script tidak menjadwalkan
proses harian dengan sendirinya.

### 1. Default harian (tanpa parameter)

```sh
bash scripts/run-workflow.sh
```

Rentang otomatis: **kemarin 16:00:00 sampai hari ini 16:00:00**.
Contoh: dijalankan tanggal 21 Oktober 2026 pukul 17.00, data yang diminta
adalah 20 Oktober 2026 pukul 16.00 sampai 21 Oktober 2026 pukul 16.00.
Jika dijalankan sebelum pukul 16.00, batas akhirnya tetap hari ini pukul
16.00; data hari ini belum lengkap.

### 2. Tanggal dan jam khusus

```sh
bash scripts/run-workflow.sh \
  --from "2026-10-18 08:30:00" \
  --to "2026-10-20 17:45:30"
```

Mengambil data mulai **18 Oktober 2026 pukul 08.30.00** sampai
**20 Oktober 2026 pukul 17.45.30 WIB**. Rentang boleh berbeda dari 24 jam.
SQL Server menggunakan tanggal dan jam yang sama persis dari Grafana.

- Isi **kedua** parameter `--from` dan `--to`.
- Gunakan format **`YYYY-MM-DD HH:MM:SS`**, termasuk detik.
- Gunakan tanda kutip karena nilai berisi spasi.
- `--from` harus lebih awal daripada `--to`.
- Parameter hanya berlaku untuk perintah itu. Tanpa parameter pada
  pemanggilan berikutnya, rentang kembali ke default harian.
- Rentang tidak valid menghentikan proses sebelum browser atau query SQL dijalankan.

### 3. Tanpa jendela Chrome

```sh
bash scripts/run-workflow.sh \
  --from "2026-10-20 16:00:00" \
  --to "2026-10-21 16:00:00" \
  --variable BROWSER:headlesschrome
```

### 4. Hanya download dan proses CSV (tanpa SQL/matching)

```sh
bash robot/run-test.sh \
  --from "2026-10-20 09:00:00" \
  --to "2026-10-20 12:00:00"
```

Perintah workflow lengkap menjalankan download → pemrosesan CSV terbaru →
SQL Server → pencocokan session. File `data/processed/merged.csv` dan
`data/processed/time_range.json` diganti sesuai rentang terbaru, bukan
ditambahkan ke hasil hari sebelumnya. SQL yang dijalankan terpisah akan
membaca rentang tersimpan itu, bukan parameter atau tanggal hari berjalan.

## Output files

- `data/downloads/*.csv`: downloaded source CSV files.
- `data/processed/merged.csv`: processed latest download, with `session_id`.
- `data/processed/time_range.json`: exact Grafana start/end and timezone used by SQL.
- `reports/robot/report.html`: latest Selenium test report.
- `data/sql/sql_query_results.csv`: SQL session IDs and first/last message times.
- `data/results/unmatched_sessions.csv`: unmatched session IDs and their counts.
- `data/results/unmatched_session_details.csv`: SQL details for unmatched sessions.

## Project layout

```text
scripts/             CSV processing, SQL query, session matching
robot/               Selenium test, runner, Selenium requirements
notebooks/           Exploratory notebook (run its first setup cell first)
tests/               Local workflow tests without a database connection
data/downloads/      Source CSV downloads
data/processed/      Latest processed merged.csv
data/sql/            Current SQL query results
data/results/        Current unmatched IDs and SQL details
data/reference/      Two historical CSV inputs used by the notebook
reports/robot/       Current Robot Framework logs and screenshots
```

Current outputs are ignored by Git. Unused historical outputs and duplicate
CSV files have been removed; notebook reference inputs are kept in data/reference/. The exploratory notebook includes historical comparisons;
it does not run as part of the daily workflow.

## Check the code locally

```sh
.venv/bin/python -m unittest discover -s tests -v
```

These tests exercise file selection, output replacement, SQL query time
bounds, and ID matching with a fake database. They do not establish a live
SQL connection. A working SQL Server ODBC driver and `.env` are required
for the real SQL steps.
