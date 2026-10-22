# Notebook and headless workflow comparison

## Matching direction

The intended comparison follows `notebooks/cek.ipynb`: find **SQL/Yeastar
sessions that do not appear in Grafana**.

The original script calculated the reverse difference, Grafana minus SQL.
Because every Grafana session in the test dataset appeared in SQL, it
returned 0 while the notebook returned 30. The script now calculates SQL
minus Grafana and preserves SQL first/last message times.

## Reproduce the comparison

```sh
bash scripts/run-workflow.sh \
  --from "2026-10-20 00:00:00" \
  --to "2026-10-21 00:00:00" \
  --variable BROWSER:headlesschrome
```

This investigation was run on October 21, 2026. Selenium passed, the
Grafana URL timestamps were verified, and SQL used the same range saved
in `time_range.json`.

| Stage | Historical result |
|---|---:|
| Grafana CSV rows | 912 |
| Unique Grafana sessions | 643 |
| Unique SQL sessions | 673 |
| Grafana minus SQL, the old direction | 0 |
| SQL minus Grafana, the intended direction | 30 |
| Sessions passing the original UD39 detail filter | 2 |

Running the notebook cells again with this CSV produced the same 30 IDs
as the script and `data/reference/unmatched_yeastar_sessions.csv`. All
673 SQL IDs and their first/last message timestamps also matched
`data/reference/YeastarLog20Okt.csv` after normalizing date formats.

## Why the notebook showed 701 sessions

The saved notebook output used a different historical CSV. At commit
`a7b20ad`, `robot/merged.csv` contained:

- 979 rows and 701 unique sessions.
- Timestamps from October 20 at 04:50:58 through October 21 at 08:26:29.
- 58 additional sessions compared with the October 20 daily CSV. All
  additional sessions came from October 21, between 03:05:37 and 08:26:29.

The 701-versus-643 difference was caused by the input interval, not
headless execution. Saved notebook output does not change automatically
when the CSV changes. Its final comparison cell also reads a historical
reference list and filters the date `10-20`, rather than using live output
from the preceding matching cell.

## Original filter: why 30 candidates produced only 2 detail rows

The initial detail query selected sessions with API messages and no more
than 3 rows across their full histories. Direct SQL inspection found:

- All 30 IDs existed in UD39.
- 27 sessions had more than 3 rows.
- 4 sessions had no API rows.
- These rejection groups overlapped; only 2 sessions passed both checks.

Those 2 rows did not establish that both sessions were abandoned.
Session `204554` had received an API reply, while genuinely unanswered
sessions could contain more than 3 messages. The row-count filter was
therefore removed. `unmatched_sessions.csv` still preserves the complete
initial SQL-minus-Grafana candidate list.

## Workflow stages

1. Grafana exports the requested interval using the Yeastar log filter.
2. `join.py` processes only that download, extracts IDs as strings, and
   replaces `data/processed/merged.csv`.
3. `sql_server.py` fetches ChatMessage sessions using the same interval.
4. `match_sessions.py` normalizes IDs, calculates SQL minus Grafana,
   deduplicates candidates, and preserves SQL first/last message times.
5. The detail query checks full histories. The terminal lists only final
   IDs; the initial candidate CSV is retained separately.

Regression tests use IDs exclusive to each side so reversing the
comparison cannot pass unnoticed. The investigation included live
headless execution and both SQL queries, in addition to local tests.

## Unanswered-message rule

Find the latest incoming customer-to-API message, then check for a later
outbound reply. Order messages by timestamp and then MsgID for ties.
If no reply exists, retain the latest incoming message. There is no limit
on message count and no requirement for a system closure event. The full
candidate history is examined.

Direct SQL verification excluded `204554` and retained `196772` and
`196777`. Tests cover eight repeated incoming messages, a new customer
message after an old reply, open sessions, system-only sessions, and
incoming/outgoing messages with equal timestamps.

Before agent replies were included, the October 20 run produced 19 final
sessions from 30 initial candidates. All 19 had more than 3 history rows
and would have been missed by the old filter. Independent replay of raw
SQL histories in Python confirmed those results under the rules at that
time. This is a historical result, not a current count.

## Agent replies count too

Session `205111` was initially included because its replies came from
`extension`, not `api`. Both now count as valid replies: `MsgType_c = out`,
recipient `external`, and sender `api` or `extension`, after the latest
customer-to-API message. An old agent reply does not cover a newer
unanswered customer message.

Live SQL verification excluded `205111` and `204554` while retaining
`196772` and `196777`. Tests cover extension replies and subsequent
customer follow-ups.

## Sessions ever picked up by an agent are excluded

Any history event with sender `extension`, type `system`, and code `5`
excludes the session. No outbound reply is required for this exclusion.
An API transfer to a queue, code `6`, is not sufficient on its own.

Live SQL verification excluded `201420` and retained `196772` and
`196777`. Tests also cover a pickup before the latest incoming message.

The historical 13-ID summary was generated before this pickup rule and
has not been recomputed. Daily caches now check the matching-rule hash
and do not reuse results generated under old rules.
