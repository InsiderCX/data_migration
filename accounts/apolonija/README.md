# Apolonija legacy import

Import of the pre-platform history of **Stomatološka poliklinika Apolonija** (EU, `insider-prod`), so Clinicdash shows Nov 2022 – 20 Oct 2024 like any other period, and the clinic's original file can be exported back exactly.

| | |
|---|---|
| Linear | [DEV-162](https://linear.app/insidercx/issue/DEV-162/upload-the-legacy-data) · plan: [`docs/plans/2026-11-03_videntis-arcadia-apolonija.md`](../../docs/plans/2026-11-03_videntis-arcadia-apolonija.md) |
| Load code | `APOLONIJA_LEGACY_V1` |
| Account / Location / Survey | 39 / 60 / 20 on EU prod. Scripts resolve them from Alchemer survey **90492576** |
| Owner | Ana (ana@insidercx.com) |
| Status | **Loaded on EU staging 3 Nov 2026** (mock sending batch 13091), validated, export identical, rollback tested. Run log: [`runs/2026-11-03_staging.md`](runs/2026-11-03_staging.md). Next: ops SQL (05–08), ops sign-off |

All numbers below are **real**, read from the EU prod replica or the input files on 3 Nov 2026, unless marked estimated.

## 1. Inputs

| File | What it is | SHA-256 |
|---|---|---|
| `Pacijenti_JOINED_Apolonija.csv` | 67,895 rows + header, 23 columns. 11,420 rows **with** `visit_date` are platform-era invites (`id` = `visit_msg.id`, uuid). 30,928 rows have a numeric or text id and no date (legacy). **25,547 rows have no id at all** (open item P1) | `c04325052d5cbb4363bac8918715d2965788c0393699c2e108bbaf375ed860c2` |
| `Survey_responses_Apolonija.csv` | Alchemer export joined with patient fields: 2,468 responses. 1,471 have numeric legacy sguids | `abb6b20be148037440b088f6a4fd3a3a6365ca9ef71968f32d6a7a3c906105e3` |

Columns compared with SIE: the 15 base columns plus `roditelj`, `ortodoncija`, `hzzo`, `next_reservation_timestamp`, `parent_ortho_comment`, `parent_phone`, `age`, `Spol2`.

Both files contain Patient PII. They live in `data/` (git-ignored).

## 2. Facts that shape the build

1. **Region:** EU only (no match on UK).
2. **Dates are day-first.** `Time Started` and `visit_date` are `DD/MM/YYYY HH:MM:SS`, Europe/Zagreb local. Checked against `survey_response."dateStarted"` for 5 response ids: all identical in Zagreb time.
3. **Legacy rows have no `age`, no `year_of_birth` and no `language_code`.** Per decision 4, `year_of_birth` stays empty and the invite replay skips the age rule (age limit is 25). All invites get the HR template.
4. **Rows without an id (25,547):** only name, phone and, in 21,436 of them, a comment are filled. Every phone also appears on a legacy row with an id. Kept as raw rows until ops say what they are.
5. **Template:** SURVEY_INVITE 84 HR (the only one).
6. **Legacy period:** responses with numeric sguids run 16 Nov 2022 – Oct 2024. Platform's first invite: 21 Oct 2024. One legacy response started later (Jun 2025).
7. **Legacy id schemes:** `10…` (5 and 6 digits) and `40…` (6 digits), Nov 2022 – Sep 2023, then `77` + sequence (6 and 7 digits, Feb 2023 – Oct 2024).

## 3. Unlinked Survey Responses (1,566)

| Group | Count | Linkable? |
|---|---|---|
| Numeric sguid, id in the clinic file, in the survey export | **1,471** | yes |
| Numeric sguid, id in the clinic file, missing from the survey export | **5** | yes |
| Numeric sguid, id not in the clinic file (`0001`, `0002`, test-like `1111…`, `40275…`, four `7764…`/`7765…`) | 13 | no |
| Empty sguid | 18 | no |
| Sguid with a leading space (36, like `" 402293"`) or an `apo…` id (9): matches a clinic id after trimming | 45 | yes, if confirmed (checks C07) |
| Text / test sguid (`" 101"`, 7 other `apo`/`appo`, test links) | 14 | no |
| **Total** | **1,566** | **1,521** |

Also in the clinic file: **29 rows with the id `#N/A`** (an Excel error, checks C06).

## 4. Platform benchmarks (initial invites sent 21 Oct 2024 – 3 Nov 2026)

| Benchmark | Value |
|---|---|
| Initial invites sent / delivered | 11,446 / 11,000 |
| Delivery rate | 96.1% |
| Responses linked / response rate (over delivered) | 1,135 / 10.3% |
| Visit → send median | 63.0 h |
| Send → response median | 0.67 h |
| Most common send hour (Zagreb) | 16:00 |
| Reminders | none |
| Quarantine / age limit | 90 days / **25** |
| Sending | `INFOBIP_SMS_MAIN`, sender `Apolonija`; SMS status names as SIE |
| Baseline on prod: Patients / Patient Visits / Patient Tickets | 4,760 / 36,702 / 0 |

Note: 1,902 of the 11,446 initial invites have no `template_id`.

## 5. Estimation check (decision 7: Spearman ≥ 0.95)

Legacy id vs response start, all 1,471 responded legacy rows: **0.992, passes overall.**

| Id group | Responses | Spearman | Period |
|---|---|---|---|
| 5 digits `10…` | 192 | 0.438 (weak) | Nov 2022 – Aug 2023 |
| 6 digits `10…` | 119 | 0.216 (weak) | Nov 2022 – Sep 2023 |
| 6 digits `40…` | 36 | 0.041 (weak) | Dec 2022 – Jan 2023 |
| 6 digits `77…` | 376 | 0.968 | Feb – Dec 2023 |
| 7 digits `77…` | 738 | 0.995 | Sep 2023 – Oct 2024 |

**347 of 1,471 responses (24%) are in weakly ordered groups** (open item P2).

## 6. Open items

| # | Item | Who |
|---|---|---|
| P1 | What are the 25,547 rows without an id? | Ops (asked by Ana) |
| P2 | Send dates for non-responded rows in the `10…` / `40…` groups (Nov 2022 – Sep 2023) can't be fitted from id order | Decide in step 2 |

## Step 2: load file (built 3 Nov 2026)

```bash
python3 -I scripts/1_build_load_file.py data/Pacijenti_JOINED_Apolonija.csv data/db_unlinked_responses_2026-11-03.csv data/apolonija_full_v1.csv
```

| | |
|---|---|
| Load file | `data/apolonija_full_v1.csv`, SHA-256 `800c54df6452f30261edf79d8b8bfdb27ec0c6aba113aab01f43a2b625f8e8ef` |
| Row kinds | 67,895 rows: 25,576 legacy_raw / 20,383 legacy_visit / 11,420 platform / 10,516 legacy_invite |
| Responses linked (real) | 1,517 (1,476 + 45 trimmed/`apo` sguids − 4 Deleted) |
| Original columns | `raw_*`, values identical; 157 lines differ only in quoting |
| Year of birth | empty (decision 4) |

Responses come from the prod replica (`data/db_unlinked_responses_2026-11-03.csv`), not from the survey export, because the DB has linkable responses the export lacks.

**Legacy period, estimated** (sent, delivered and send dates are estimates; responses are real):

| Period | Sent (est.) | Delivered (est.) | Responses (real) | Response rate (est.) | Platform delivery / response rate (real) |
|---|---|---|---|---|---|
| 16 Nov 2022 – 18 Oct 2024 | 10,516 | 10,127 (96.3%) | 1,517 | 15.0% | 96.1% / 10.3% |

- Invite replay on platform data: recall 89.8% (+4.2%) without an age rule. The platform does not apply its limit 25 either: 5,810 real invites went to Patients under 25. Passes decision 7 (≥ 85%).
- Legacy rows without a phone are invites only when a real response proves it (decision 15).
- Median estimated invites per send day: 14 (busiest 1,138 on 16 Nov 2022, the launch batch: 246 real responses that day).

- Send-date method differs from SIE in two ways (check C10): dates are interpolated between isotonic block midpoints instead of steps, and id schemes with Spearman < 0.95 get the anchors' send-time quantiles by id rank. Weekend dates move to Monday.
