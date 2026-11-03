# Videntis legacy import

Import of the pre-platform history of **Videntis Dental Centar** (EU, `insider-prod`), so Clinicdash shows Nov 2022 – 20 Oct 2024 like any other period, and the clinic's original file can be exported back exactly.

| | |
|---|---|
| Linear | [DEV-162](https://linear.app/insidercx/issue/DEV-162/upload-the-legacy-data) · plan: [`docs/plans/2026-11-03_videntis-arcadia-apolonija.md`](../../docs/plans/2026-11-03_videntis-arcadia-apolonija.md) |
| Load code | `VIDENTIS_LEGACY_V1` |
| Account / Location / Survey | 38 / 59 / 19 on EU prod. Scripts resolve them from Alchemer survey **90508475** |
| Owner | Ana (ana@insidercx.com) |
| Status | **Step 2 (load file) built 3 Nov 2026, waiting for Ana's check.** No SQL yet |

All numbers below are **real**, read from the EU prod replica or the input files on 3 Nov 2026, unless marked estimated.

## 1. Inputs

| File | What it is | SHA-256 |
|---|---|---|
| `Pacijenti_JOINED_Videntis.csv` | 16,416 rows + header, 19 columns. 5,483 rows **with** `visit_date` are platform-era invites (`id` = `visit_msg.id`, uuid). 10,933 rows **without** `visit_date` are legacy rows with a numeric id (= the `sguid` in old survey links) | `6ce5844e54d3f3daa3e9d8e8657b1de74ec798106eb810003646d8e8f921f4e0` |
| `Survey_responses_Videntis.csv` | Alchemer export joined with patient fields: 981 responses. 502 have numeric legacy sguids | `7632c12509ccc3a9cd6d1cada864ad20a21f564b85c143bfe54401e2719af964` |

Columns compared with SIE: same 15 base columns, plus `roditelj` (always empty), `age`, `Spol2`, `Punoljetan`. No `accommodation` / `organized_transport`. `procedure` and `comment` are empty on every row.

Both files contain Patient PII. They live in `data/` (git-ignored).

## 2. Facts that shape the build

1. **Region:** EU only (no match on UK).
2. **Dates are day-first.** `Time Started` and `visit_date` are `DD/MM/YYYY HH:MM:SS`, Europe/Zagreb local. Checked against `survey_response."dateStarted"` for 5 response ids: all identical in Zagreb time. SIE's files were month-first, so the builder's date parsing must change.
3. **Legacy rows have `age` (10,916 of 10,933) and `language_code` (10,918), but no `year_of_birth`.** Year of birth can be derived as in SIE (`year(visit) − age`, once "age at visit" is re-checked on existing Patients). Languages: HR 9,243, EN 947, DE 335, FR 260, SL 120.
4. **Templates:** SURVEY_INVITE 79 HR, 80 EN, 81 FR, 82 DE, 83 IT. No SL template; SL rows fall back to HR (SIE's rule).
5. **Legacy period:** responses with numeric sguids run 29 Nov 2022 – 27 Oct 2024. Platform's first invite: 21 Oct 2024. Only 1 legacy response started on or after that date.
6. **Legacy id schemes** (from responded rows): `10xxx` (5 digits, Nov 2022 – Jan 2023), then `77` + sequence (5, 6 and 7 digits, Feb 2023 – Oct 2024). Of the clinic file's legacy ids, 10,209 start with `77`.

## 3. Unlinked Survey Responses (619)

| Group | Count | Linkable? |
|---|---|---|
| Numeric sguid, id present in the clinic file | **502** | yes |
| Numeric sguid, id **not** in the clinic file (64 `77…`, 4 `10xx`, 2 test-like `111111111…`) | 70 | no: the invite is missing from the clinic file (open item V1) |
| Empty sguid | 38 | no |
| Text sguid `vid66`, `vid62`: both are clinic ids | 2 | yes, if confirmed (checks C08) |
| Text / test sguid (5 test, `vid5`, `vid51`) | 7 | no |
| **Total** | **619** | **504** |

The 70 missing ones are in the DB but not in the survey export either (the export is older or filtered). Responses on the survey export that are missing from the DB: **0**.

## 4. Platform benchmarks (initial invites sent 21 Oct 2024 – 3 Nov 2026)

| Benchmark | Value |
|---|---|
| Initial invites sent / delivered | 5,502 / 5,110 |
| Delivery rate | 92.9% |
| Responses linked / response rate (over delivered) | 480 / 9.4% |
| Visit → send median | 63.0 h |
| Send → response median | 0.79 h |
| Most common send hour (Zagreb) | 16:00 |
| Reminders | none |
| Quarantine / age limit | 90 days / **0** (no age rule) |
| Sending | `INFOBIP_SMS_MAIN`, sender `Videntis`; SMS status names as SIE (`DELIVERED_TO_HANDSET`, `UNDELIVERABLE_NOT_DELIVERED`, …) |
| Baseline on prod: Patients / Patient Visits / Patient Tickets | 3,816 / 15,692 / 0 |

Note: 961 of the 5,502 initial invites have no `template_id`. Imported invites will use the language template.

## 5. Estimation check (decision 7: Spearman ≥ 0.95)

Legacy id vs response start, all 502 responded legacy rows: **0.998, passes.**

| Id group | Responses | Spearman | Period |
|---|---|---|---|
| 5 digits `10…` | 52 | 0.707 (weak) | Nov 2022 – Jan 2023 |
| 5 digits `77…` | 51 | 0.962 | Feb – May 2023 |
| 6 digits `77…` | 331 | 0.999 | May 2023 – Oct 2024 |
| 7 digits `77…` | 48 | 0.987 | Aug – Oct 2024 |

The early `10…` group is weakly ordered (open item V2). The replay-recall check (≥ 85%) is done in step 2.

## 6. Open items

| # | Item | Who |
|---|---|---|
| V1 | 70 legacy responses (sguids `77…` / `10xx`, Nov 2022 – Oct 2024) point to invites that aren't in the clinic file. Ask the clinic for those rows, or leave the responses unlinked and listed | Ana / ops |
| V2 | Send dates for non-responded rows in the early `10…` group (Nov 2022 – Jan 2023) can't be fitted well from id order | Decide in step 2 |

## Step 2: load file (built 3 Nov 2026)

```bash
python3 -I scripts/1_build_load_file.py data/Pacijenti_JOINED_Videntis.csv data/db_unlinked_responses_2026-11-03.csv data/videntis_full_v1.csv
```

| | |
|---|---|
| Load file | `data/videntis_full_v1.csv`, SHA-256 `ded1fb0d3325e49e5e5662e1239b787c9f6628862781c9f1d42f68144cbdc47f` |
| Row kinds | 16,416 rows: 6,562 legacy_visit / 5,483 platform / 4,371 legacy_invite |
| Responses linked (real) | 504 (502 + `vid66`, `vid62`) |
| Original columns | `raw_*`, byte-identical |
| Year of birth | `2026 − age` for 10,916 rows. The file's `age` is age **in 2026** (5,454 of 5,483 platform rows exact), not age at the visit as in SIE |

Responses come from the prod replica (`data/db_unlinked_responses_2026-11-03.csv`), not from the survey export, because the DB has linkable responses the export lacks.

**Legacy period, estimated** (sent, delivered and send dates are estimates; responses are real):

| Period | Sent (est.) | Delivered (est.) | Responses (real) | Response rate (est.) | Platform delivery / response rate (real) |
|---|---|---|---|---|---|
| 29 Nov 2022 – 18 Oct 2024 | 4,371 | 4,078 (93.2%) | 504 | 12.4% | 92.9% / 9.4% |

- Invite replay on platform data: recall 92.6% (+9.5% over). Passes decision 7 (≥ 85%).
- Legacy rows without a phone are invites only when a real response proves it (decision 15).
- Median estimated invites per send day: 7 (busiest 316 on 29 Nov 2022, a real batch day: 33 real responses).
- One artifact day remains: 17 Jun 2024 with 70 estimated invites and no real response.
- Send-date method differs from SIE in two ways (check C10): dates are interpolated between isotonic block midpoints instead of steps, and id schemes with Spearman < 0.95 get the anchors' send-time quantiles by id rank. Weekend dates move to Monday.
