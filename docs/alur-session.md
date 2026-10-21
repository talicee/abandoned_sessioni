# Perbandingan notebook dan workflow headless

## Tujuan dan perbaikan

Tujuan yang benar mengikuti sel pencocokan `notebooks/cek.ipynb`:
**session SQL/Yeastar yang tidak ada di Grafana**.

Sebelumnya `scripts/match_sessions.py` menghitung arah sebaliknya:
Grafana dikurangi SQL. Karena seluruh session Grafana pada tanggal uji
terdapat di SQL, script menghasilkan 0, sementara notebook menghasilkan 30.
Sekarang script menghitung SQL dikurangi Grafana dan menyimpan waktu pesan
pertama/terakhir dari SQL, sama seperti notebook.

## Reproduksi dengan input yang sama

```sh
bash scripts/run-workflow.sh \
  --from "2026-10-20 00:00:00" \
  --to "2026-10-21 00:00:00" \
  --variable BROWSER:headlesschrome
```

Uji dilakukan pada 21 Oktober 2026. Selenium PASS; URL rentang Grafana
diverifikasi dan SQL membaca batas waktu yang sama dari `time_range.json`.

| Tahap | Hasil |
|---|---:|
| Baris CSV Grafana | 912 |
| Session unik Grafana | 643 |
| Session unik SQL | 673 |
| Grafana dikurangi SQL (arah lama) | 0 |
| SQL dikurangi Grafana (arah notebook dan script baru) | 30 |
| Session yang lolos query detail UD39 | 2 |

Sel notebook dijalankan ulang memakai CSV hasil unduhan ini. Seluruh 30 ID
hasil script sama persis dengan hasil notebook dan file referensi
`data/reference/unmatched_yeastar_sessions.csv`. Seluruh 673 ID SQL, waktu
pesan pertama, dan waktu pesan terakhir juga sama dengan
`data/reference/YeastarLog20Okt.csv` setelah format tanggal dinormalisasi.

## Mengapa notebook menampilkan 701 session?

Output tersimpan notebook berasal dari CSV historis yang berbeda.
File `robot/merged.csv` pada commit `a7b20ad` di main berisi:

- 979 baris dan 701 session unik.
- Rentang aktual 20 Oktober 04:50:58 sampai 21 Oktober 08:26:29.
- Sebanyak 58 session tambahan dibanding CSV satu hari tanggal 20 Oktober;
  seluruh tambahan itu berasal dari 21 Oktober, antara 03:05:37 dan 08:26:29.

Jadi 701 dibanding 643 bukan pengaruh headless. Input historis mencakup
sebagian tanggal 21 Oktober. Output notebook yang tersimpan tidak otomatis
berubah ketika CSV diganti. Selain itu, sel terakhir membaca daftar
referensi historis dan memfilter tanggal `10-20`, bukan memakai hasil
live dari sel pencocokan.

## Mengapa detail hanya 2 baris dari 30 session?

Daftar missing dihitung sebelum filter detail. Query UD39 kemudian meminta
session yang memiliki baris API dan total baris maksimal 3, dihitung dari
seluruh riwayat session. Pemeriksaan langsung ke SQL menemukan:

- Seluruh 30 ID ada di UD39.
- 27 session memiliki lebih dari 3 baris.
- 4 session tidak memiliki baris API.
- Kedua kelompok penolakan tersebut bertumpang tindih; hanya 2 session
  memenuhi semua syarat. Kedua ID itu sama dengan output detail.

Filter detail dipertahankan. `unmatched_sessions.csv` tetap berisi seluruh
30 session, bukan hanya 2 session yang lolos filter detail.

## Alur akhir

1. Grafana mengekspor CSV untuk rentang yang diminta, dengan query log Yeastar.
2. `join.py` memproses unduhan itu saja, mengekstrak session ID sebagai string,
   dan mengganti `data/processed/merged.csv`.
3. `sql_server.py` mengambil session ChatMessage untuk rentang Grafana yang sama.
4. `match_sessions.py` menormalisasi ID, membandingkan SQL dikurangi Grafana,
   menghapus duplikat ID, dan menyimpan waktu pertama/terakhir dari SQL.
5. ID missing dicetak di terminal dan dikirim ke query detail UD39.

Tes regresi menggunakan ID yang hanya ada di masing-masing sisi sehingga
perbandingan terbalik tidak bisa kembali lolos. Ketujuh tes lokal lulus,
dan workflow headless serta kedua query SQL dijalankan terhadap layanan asli.
