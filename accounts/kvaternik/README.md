# Kvaternik legacy import

Import of the first weeks of **Kvaternik** (EU, `insider-prod`) that the platform never stored as Visit Msgs: one bulk send on 21 Feb 2024, before the first platform invite on 5 Mar 2024. The clinic's original file can be exported back exactly.

| | |
|---|---|
| Linear | [DEV-232](https://linear.app/insidercx/issue/DEV-232/upload-legacy-data-for-kvaternik-mazalin-and-opticalexpress-to-the-stg) · plan: [`docs/plans/2026-11-06_kvaternik-mazalin-opticalexpress.md`](../../docs/plans/2026-11-06_kvaternik-mazalin-opticalexpress.md) |
| Load code | `KVATERNIK_LEGACY_V1` |
| Account / Locations / Survey | 21 / 27 Kvaternik Kostanjevec, 28 Kvaternik Subiceva / 11 on EU prod. Scripts resolve them from Alchemer survey **90677816** |
| Owner | Ana (ana@insidercx.com) |
| Status | **Loaded on EU staging 6 Nov 2026**, validated, export identical, rollback tested. Run log: [`runs/2026-11-06_staging.md`](runs/2026-11-06_staging.md). Ops package sent (DEV-232, COPS ticket). **Production only after ops sign-off**: [`PRODUCTION.md`](PRODUCTION.md) |

All numbers are **real**, read from the EU prod replica or the input files on 6 Nov 2026, unless marked estimated.

## 1. Inputs

| File | What it is | SHA-256 |
|---|---|---|
| `Pacijenti_joined_Kvaternik.csv` | 8,407 rows + header, 18 columns (base 15 + `account`, `location_id`, `sent_at`). 7,680 rows are platform Visit Msgs (`id` = `visit_msg.id`); **727 are legacy** (uuid id, no `sent_at`, Visit Msg missing) | `f043591a1401afe6da68cdf118530b04e150ccfcf8576a70003e80530c6266e1` |
| `Surevy_responses_Kvaternik.csv` | Alchemer export joined with patient fields: 1,720 responses, all uuid sguids. 1,588 already linked, 132 point to legacy rows | `da60d3126f0c9c071e68207fcf0ee6faa3ce077280efad5e3ccec0550e30b1ee` |
| `db_unlinked_responses_2026-11-06.csv` | Unlinked Survey Responses from the prod replica (id, sguid, start, status, test flag) | — |

All files hold Patient PII and live in `data/` (git-ignored).

## 2. Facts that shape the build

1. **Region:** EU only.
2. **Legacy rows:** 727, all with `source_id` and phone. Location as text: `Subiceva` 557 (→ 28), `Kostanjevec` 170 (→ 27). Platform rows use the numeric ids 27 / 28.
3. **Visit date is a placeholder:** every legacy row says 21/02/2024 12:00:00.
4. **Real responses show one bulk send:** 109 responses on 21 Feb 2024 (first 14:57 UTC = 15:57 Zagreb), 10 on 22 Feb, 13 later up to 30 Apr 2024. Visit → response is 0.2 days for 90% of them.
5. **SMS status is filled on every legacy row** (real): DELIVERED 696, REJECTED 13, PENDING 12, UNDELIVERABLE 5, EXPIRED 1. All 132 answered rows are DELIVERED.
6. **Year of birth** is a year (1855–2017), not an age. 1 legacy row has shifted columns (`#VALUE!`, a date in `language_code`): open item O6.
7. **Dates are day-first** (`DD/MM/YYYY HH:MM:SS`, Zagreb local). Alchemer `Time Started` = DB `dateStarted` + 1 h (checked on responses 10, 100).
8. **Templates:** SURVEY_INVITE HR 40 (Location 27), HR 39 (Location 28). Language is empty on every legacy row → HR.

## 3. Unlinked Survey Responses (137)

| Group | Count | Linkable? |
|---|---|---|
| uuid sguid = a legacy row id | **132** | yes, but **not linked now** (decision 2) |
| Text / test sguid | 4 | no |
| Empty sguid | 1 | no |
| Deleted | 0 | — |

Responses in the survey export but missing from the DB: 0. In the DB but not in the export: 5 (the text / empty ones).

## 4. Platform benchmarks (all platform invites to 6 Nov 2026)

| Benchmark | Value |
|---|---|
| Delivery rate (2024 – Oct 2026) | 96.6% |
| Response rate over delivered | 21.4% (1,574 / 7,367) |
| Visit → send median | 28.0 h |
| Send → response median | 0.37 h |
| Most common send hour (Zagreb) | 16:00 |
| Quarantine / age limit | 180 days / 18 |
| Sending | `INFOBIP_SMS_MAIN`, sender `Kvaternik` |
| Baseline on prod: Patients / Patient Visits / Patient Tickets / Visit Msgs | 7,729 / 8,091 / 0 / 7,680 |

## 5. What gets estimated

| Value | Rule | Real or estimated |
|---|---|---|
| Send date | 21 Feb 2024 14:50 Zagreb for all 727 | estimated |
| Visit date | file's 21 Feb 2024 12:00 | real value, but a placeholder |
| Delivery status | file | real |
| Invite or not | every legacy row was sent | real (the file lists sent messages) |

Expected legacy figures, **if linked**: 696 delivered of 727 (95.7%), 132 responses, response rate 19.0% (platform 21.4%). Without linking (decision 2): 727 invites, 0 responses.

## 6. Open items

See the plan: O1 (link?), O6 (shifted row).

## Step 2: load file (built 6 Nov 2026)

```bash
python3 -I scripts/1_build_load_file.py data/Pacijenti_joined_Kvaternik.csv data/db_unlinked_responses_2026-11-06.csv data/kvaternik_full_v1.csv data/db_visit_msg_ids_2026-11-06.csv
```

| | |
|---|---|
| Load file | `data/kvaternik_full_v1.csv`, SHA-256 `be1e9022de0a4c077b59a4ad4c111276a881fcc7721d88d10a44b1ddedbbfb79` (6 Nov 2026, with `country_out`) |
| Row kinds | 8,407 rows: 7,680 platform / 727 legacy_invite |
| Platform rows | decided by the Visit Msg ids on prod (`data/db_visit_msg_ids_2026-11-06.csv`), not by `sent_at`: 6 platform rows have no `sent_at` |
| Send date | all 727 on 21 Feb 2024 14:50 Zagreb (estimated); 0 sends had to be moved before their response |
| Status | all 727 from the file (real): DELIVERED 696, REJECTED 13, PENDING 12, UNDELIVERABLE 5, EXPIRED 1 |
| Location | by name: Subiceva 557 → Kvaternik Subiceva, Kostanjevec 170 → Kvaternik Kostanjevec; each with its own template |
| Responses | 132 real responses on legacy invites, **not linked** (decision 2). If linked: 19.0% (platform 21.4%) |
| Year of birth | 1900–2026 only; the shifted row's `#VALUE!` → empty (O6) |
| Original columns | `raw_*`, byte-identical; the export back (`04`) equals the clinic file (mock test) |

SQL: `sql_config.json` (`layout` 2, `link_responses` false) rendered by `tools/render_legacy_sql.py`. Mock test: `bash tests/run_mock_test.sh data/Pacijenti_joined_Kvaternik.csv` → ALL CHECKS PASSED (6 Nov 2026), including: no existing row changed, no `legacy_invite_map` rows, 0 responses linked even after a simulated Alchemer sync.
