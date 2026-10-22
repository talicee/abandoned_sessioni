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
IDs with the SQL results. It selects SQL/Yeastar sessions absent from
Grafana (SQL IDs minus Grafana IDs), then queries details for those sessions.
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

## Tujuan pencocokan session

Acuan alur adalah `notebooks/cek.ipynb`: cari **session yang ada di SQL/Yeastar,
tetapi tidak ada di Grafana**.

```text
missing = session SQL/Yeastar - session Grafana
```

`unmatched_sessions.csv` menyimpan satu baris per session dengan kolom
`session_id`, `first_msg_time`, dan `last_msg_time` dari SQL. Session ID
normalisasi sebagai string agar nol di depan tidak hilang. Daftar ID
missing tetap disimpan di CSV. Terminal hanya menampilkan daftar session ID
yang lolos filter detail UD39, yaitu hasil akhir yang perlu ditindaklanjuti.

Query detail UD39 memeriksa seluruh riwayat setiap kandidat untuk mencari
**pesan customer terakhir yang belum mendapat balasan API atau agent**:

- Pesan masuk harus `external -> api` dengan `MsgType_c = 'in'`.
- Ambil pesan masuk terakhir berdasarkan `MsgTime_c`, lalu `MsgID_c` jika waktunya sama.
- Keluarkan session jika ada pesan `out` dari `api -> external` **atau**
  `extension -> external` setelah pesan masuk terakhir.
- Keluarkan session jika **pernah di-pickup agent** pada titik mana pun
  dalam riwayatnya: `FromType_c = extension`, `MsgType_c = system`,
  `MsgTypeCode_c = 5`. Pickup sebelum pesan customer terakhir juga mengecualikan session.
- Transfer API ke antrean (kode `6`) saja tidak mengecualikan session.
- Pesan `system` penutupan otomatis diabaikan. Session tidak harus sudah ditutup.
- Tidak ada batas jumlah pesan; spam tanpa balasan tetap terdeteksi.
- Balasan lama tidak menutupi pesan customer baru yang belum terbalas.

`unmatched_session_details.csv` menyimpan satu baris pesan customer terakhir
yang belum terbalas per session. `TotalRows` hanya informasi jumlah riwayat,
bukan filter. Query riwayat tidak dibatasi tanggal unduhan, sehingga balasan
di luar rentang juga diperiksa. Pemeriksaan ini tetap diawali oleh kandidat
SQL dikurangi Grafana; session di luar kandidat itu tidak diperiksa.

Contoh yang diverifikasi langsung di SQL Server:

| Session | Riwayat | Hasil |
|---|---|---|
| `204554` | Ada pesan masuk dan balasan `out` API | Dikeluarkan |
| `205111` | API meneruskan ke agent, lalu agent membalas `out` | Dikeluarkan |
| `201420` | Agent pickup dengan kode `5`, walaupun tidak ada `out` | Dikeluarkan |
| `196772` | Pesan masuk, tanpa `out`, lalu ditutup sistem | Nyangkut |
| `196777` | Dua pesan gambar masuk, tanpa `out`, lalu ditutup sistem | Nyangkut |

Notebook masih menyimpan hasil eksekusi historis. Jalankan ulang selnya
untuk membandingkan input saat ini. Lihat [hasil penelusuran alur](docs/alur-session.md).

### Tampilan terminal

Output dibagi menjadi tiga tahap dengan nama berbeda:

```text
[1/3] Download Grafana dan proses CSV terbaru
Rentang WIB: ... -> ...
Membuka Grafana dan login...
Menerapkan filter log Yeastar...
Mengunduh CSV dan menunggu unduhan selesai...
Grafana dan pemrosesan CSV: PASS

[2/3] Ambil session SQL Server untuk rentang Grafana
...

[3/3] Cocokkan session dan ambil detail UD39
...
Session ID hasil akhir (jumlah):
  <session_id_1>
  <session_id_2>
```

Daftar ID di terminal berasal dari `Key1` pada hasil detail UD39 setelah
pemeriksaan balasan API atau extension terhadap pesan customer terakhir diterapkan. Seluruh session missing sebelum
filter tetap tersedia di `data/results/unmatched_sessions.csv`.
Banner Robot Framework dan titik progres berulang disembunyikan; error
serta warning tetap ditampilkan. Log lengkap tersedia di
`reports/robot/log.html`. Untuk output Robot lengkap saat debugging,
tambahkan `--console verbose --consolemarkers off` pada perintah runner.

### Jumlah baris dan ringkasan sementara

Terminal menampilkan jumlah **baris CSV Grafana**, jumlah **session unik**,
dan timestamp paling awal/akhir pada CSV. CSV asli tetap tersimpan di
`data/downloads/`; nama file tepatnya tercantum pada ringkasan.

- `data/processed/grafana_summary.json`: sumber CSV, rentang diminta,
  jumlah baris, jumlah session unik, dan timestamp aktual Grafana.
- `data/sql/sql_summary.json`: parameter tanggal/jam SQL, jumlah session,
  serta timestamp paling awal/akhir hasil query SQL.

Ringkasan diganti setiap kali tahap tersebut dijalankan dan diabaikan Git.
SQL mengelompokkan pesan per session, sehingga jumlah baris hasil SQL
adalah jumlah session unik, bukan jumlah seluruh pesan. Semua timestamp
hasil query awal SQL diverifikasi berada dalam rentang Grafana.

CSV Grafana kosong/tanpa session ID menghentikan workflow sebelum tahap SQL.
Ringkasan Grafana tetap disimpan dengan jumlah 0 agar bisa diperiksa.
Matching yang dijalankan manual juga menolak CSV Grafana tanpa session ID;
hasil kosong tidak boleh membuat seluruh session SQL dianggap missing.
Jika workflow berhenti, output SQL/detail dari proses sebelumnya bisa masih
ada: gunakan ringkasan dan status keberhasilan tahap saat memeriksa hasil.

Filter tanggal berlaku pada pengambilan **daftar kandidat SQL**. Pengecekan
balasan berikutnya sengaja membaca seluruh riwayat kandidat agar balasan
API/agent di tanggal lain tetap dikenali. Karena itu timestamp pesan pada
CSV detail bisa berada di luar rentang pengambilan kandidat.

## Menjalankan beberapa hari, satu hari per proses

Untuk 23 September sampai 21 Oktober 2026:

```sh
.venv/bin/python -u scripts/run-daily.py \
  --start-date 2026-09-23 \
  --end-date 2026-10-21
```

Runner memanggil workflow lengkap secara **berurutan**, selalu headless,
untuk satu tanggal pukul **00:00:00 sampai 23:59:59 WIB** sebelum pindah
ke tanggal berikutnya. Browser headless ditutup otomatis setelah tes,
termasuk saat gagal, agar sesi Chrome tidak menumpuk.
Setiap hari memiliki folder output sendiri, sehingga
hasil hari sebelumnya tidak tertimpa:

```text
data/daily/2026-09-23/
  console.log
  status.json
  grafana_raw.csv
  grafana_summary.json
  merged.csv
  time_range.json
  sql_query_results.csv
  sql_summary.json
  unmatched_sessions.csv
  unmatched_session_details.csv
```

Ringkasan keseluruhan berada di:

```text
data/daily/summary_2026-09-23_2026-10-21/summary.csv
data/daily/summary_2026-09-23_2026-10-21/session_ids.csv
```

`summary.csv` mencatat status dan jumlah baris/session tiap hari serta ID
akhirnya. `session_ids.csv` berisi ID akhir tanpa duplikat dan tanggal
kemunculannya. Ringkasan diperbarui setelah setiap hari selesai, sehingga
bisa dibaca saat runner masih berlangsung.

Hari gagal (termasuk CSV Grafana kosong) ditandai `failed` dan tidak masuk
rekap ID berhasil. Runner tetap mencoba hari berikutnya dan memberi exit
code gagal jika ada hari yang belum berhasil. Log tiap hari tersedia untuk
penelusuran. Laporan Robot yang baru dibuat ikut disalin ke folder tanggal itu. Jalankan perintah yang sama untuk melanjutkan: hari berstatus
`success` dilewati jika aturan matching sama, sementara hari gagal dicoba kembali.
Hash aturan matching disimpan di `status.json`; perubahan aturan membuat
cache lama tidak dipakai dan hari tersebut diproses ulang. Rekap yang sudah
tersimpan tetap merupakan snapshot lama sampai runner dijalankan ulang. Hasil sukses
merupakan snapshot saat dijalankan; untuk memperbarui satu hari yang sudah
sukses, hapus folder tanggal itu sebelum menjalankan ulang.

Status `verified_empty` hanya digunakan setelah verifikasi independen SQL
untuk hari dengan Grafana kosong, bukan diterapkan otomatis pada semua CSV
kosong. Pada 18 Oktober 2026, seluruh 55 session SQL diperiksa dan tidak
ada pesan customer ke API yang belum dibalas; bukti ada di
`data/daily/2026-10-18/empty_verification.json`. Status ini juga dapat
dipakai kembali saat melanjutkan run.

Tanpa parameter, tanggal awal adalah 23 September 2026 dan tanggal akhir
adalah hari ini di WIB. Data tanggal hari ini hanya berisi pesan yang
sudah tersedia saat proses dijalankan, meskipun batas akhirnya 23:59:59.
Per hari tidak otomatis menjamin bebas batas baris Loki; periksa jumlah
baris dan cakupan timestamp pada ringkasan tiap hari.

## Output files

- `data/downloads/*.csv`: downloaded source CSV files.
- `data/processed/merged.csv`: processed latest download, with `session_id`.
- `data/processed/grafana_summary.json`: temporary row/session counts and source CSV metadata.
- `data/sql/sql_summary.json`: SQL time parameters, session count, and observed timestamps.
- `data/processed/time_range.json`: exact Grafana start/end and timezone used by SQL.
- `reports/robot/report.html`: latest Selenium test report.
- `data/sql/sql_query_results.csv`: SQL session IDs and first/last message times.
- `data/results/unmatched_sessions.csv`: SQL/Yeastar session IDs missing from Grafana, with `first_msg_time` and `last_msg_time`.
- `data/results/unmatched_session_details.csv`: latest unanswered customer message for each abandoned candidate session.

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
