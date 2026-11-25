# Bolnica Colić legacy import

Import of **Bolnica Colić**'s survey history from before the platform (EU, `insider-prod`). The Account's first platform invite was on 11 Nov 2026, so almost the whole history is legacy: invites from Feb 2023 to Apr 2026 that the platform never stored as Visit Msgs.

| | |
|---|---|
| Linear | [DEV-376](https://linear.app/insidercx/issue/DEV-376) build → [DEV-377](https://linear.app/insidercx/issue/DEV-377) staging → [DEV-378](https://linear.app/insidercx/issue/DEV-378) production · parent [DEV-375](https://linear.app/insidercx/issue/DEV-375) · plan: [`docs/plans/2026-11-24_bolnica-colic-and-next.md`](../../docs/plans/2026-11-24_bolnica-colic-and-next.md) |
| Load code | `BOLNICACOLIC_LEGACY_V1` |
| Account / Location / Survey | 68 / 259 / 47 on EU prod (not in UK). Scripts resolve them from Alchemer survey **90511513** |
| Owner | Ana |
| Status | **Built and mock-tested 25 Nov 2026** (ALL CHECKS PASSED). Assumptions for Karlo in DEV-377. Next: EU staging |

All numbers are **real**, read from the EU prod replica or the input files on 25 Nov 2026, unless marked estimated.

## 1. Inputs

| File | What it is | SHA-256 |
|---|---|---|
| `Pacijenti_DrColic.csv` | Karlo, 11 Nov 2026. 2,452 rows + header, **old 12-column structure** (`Spol, Dob, Izvor, Jezik, Telefon, Doktor, Sguid, Ime, Prezime, R, Spol2, Telefon2`). Must be converted to the current format | `ac63605dfbf891d333355f8476f5770b38c1f3293b79b192066b4fcf9e73c8b7` |
| `Survey_responses_DrColic.csv` | Alchemer export, 720 responses (606 Complete, 114 Partial), 53 columns, day-first dates | `161b78690461690c79c52026059e7b2b3928ffcd2ab732ce2ffd8548ab13013d` |
| `db_unlinked_responses_2026-11-25.csv` | Unlinked Survey Responses from the prod replica (746) | `621ac383136ed55d8fa01453c128539b1daf054aa4cea183dca497a668b4434e` |
| `db_visit_msg_ids_2026-11-25.csv` | The Account's Visit Msg ids on prod (988) | `c7059756532d106778ce40aa50e59a539db225aec9acadfb01394e0c0a6e7e94` |

All files hold Patient PII and live in `data/` (git-ignored).

## 2. Facts that shape the build

1. **Region:** EU only. One Location (259), time zone `Europe/Belgrade`, country `SER`, quarantine 90 days, **no age limit**. Default language `SR`, one template: SURVEY_INVITE SR (#370). Sending `INFOBIP_SMS_MAIN`, sender `DrColic`.
2. **No file row is on the platform.** All 2,452 rows are legacy: 686 numeric ids and 1,766 uuid ids. The uuids are the old system's link ids, not Visit Msg ids (0 of 1,766 match).
3. **The platform history is one bulk send:** all 988 Visit Msgs went out on 11 Nov 2026, and all 988 Patient Visits are dated `1970-01-01`. So the Account has **no usable visit → send time** and only one day of delivery and response data.
4. **The old file has no dates at all:** no visit date and no send date. Columns `Izvor`, `Jezik`, `Doktor` and `R` are empty on every row. Names are filled on about a third of rows. `Telefon` and `Telefon2` hold the same values.
5. **Gender:** `Spol` has 7 spellings (Ž, ž, z, M, m, žž, t). `Spol2` is clean (Ženski 1,898, Muški 552, plus one `ŽenskiŽenski` and one `t`). Question for Karlo in DEV-377.
6. **Age `Dob`:** 2,385 filled, values 0–92. Whether it is age at the visit or today is a question for Karlo (DEV-377).
7. **Numeric ids rise with time:** Spearman 0.942 between id and response start (166 answered, ids 2–686, Feb–Oct 2023). **uuid ids carry no order**, so the 1,766 uuid rows have no time signal except their own response.

## 3. Unlinked Survey Responses (746)

| Group | Count | Linkable? |
|---|---|---|
| Numeric sguid = a legacy row id | **166** | yes |
| uuid sguid = a legacy row id | **554** | yes (COPS-234 A1, as Mazalin and Kvaternik) |
| Empty sguid | 15 (8 Deleted) | no |
| Test sguid | 9 (1 Deleted) | no |
| Text sguid | 2 | no |

- By year: 2023 171, 2024 223, 2025 175, 2026 177.
- Every legacy id is answered at most once. All 720 responses in the export are among these 746.
- The other 26 (in the database, not in the export) are the 9 Deleted, 8 test, 7 empty and 2 text ones. That explains the 746 vs 720.

## 4. Platform benchmarks (thin: one bulk send on 11 Nov 2026)

| Benchmark | Value |
|---|---|
| Visit Msgs / delivered | 988 / 870 → delivery rate **88.1%** |
| Responses on them | 154 → response rate over delivered **17.7%** (two weeks only) |
| Send → response median | 0.04 h (bulk send, not typical) |
| Visit → send | **not usable** (visits dated 1970) |
| Send hour (Belgrade) | 15:00 (one day) |
| Baseline on prod: Patients / Patient Visits / Patient Tickets / Visit Msgs | 988 / 988 / 0 / 988 |

**These benchmarks are too thin to fit estimates to.** Proposal for step 3: use the numeric-id anchors for send dates, and similar EU Accounts (Mazalin, Kvaternik, Videntis) for visit → send and delivery rate. Ana decides.

## 5. What would be estimated (proposal, not approved)

| Value | Proposal | Real or estimated |
|---|---|---|
| Send date, answered rows (720) | response start − send→response median | estimated |
| Send date, unanswered numeric rows | isotonic fit id → send on the 166 numeric anchors | estimated |
| Send date, unanswered uuid rows (1,212) | **no time signal**: spread over the uuid responses' months, or leave out. Ana decides | estimated |
| Visit date | send − visit→send median of similar Accounts | estimated |
| Delivery status | 88.1% (Account's one-day rate) or similar Accounts, deterministic by hash; answered rows DELIVERED | estimated |
| Gender, year of birth, phone | file, after Karlo's answers | real |

## 6. Open items

- Questions for Karlo: in [DEV-377](https://linear.app/insidercx/issue/DEV-377) (age, empty columns, gender).
- Step 2: mapping old columns → current format, script in `scripts/`.
- Step 3: benchmark source and the 1,212 unanswered uuid rows (Ana).
- Staging is a 28 Sep 2026 copy, older than the Account's first platform invite (11 Nov 2026). Whether Account 68 and Survey 47 exist there is not checked yet (DEV-377 step 1). Staging can't be reached from here.

## Step 2–4: conversion, load file, mock test (25 Nov 2026)

Built without waiting for Karlo (Ana, 25 Nov 2026). Every assumption below is listed in DEV-377 for him to confirm.

```bash
python3 -I scripts/0_convert_old_format.py data/Pacijenti_DrColic.csv data/Pacijenti_Joined_BolnicaColic.csv
python3 -I scripts/1_build_load_file.py data/Pacijenti_Joined_BolnicaColic.csv data/db_unlinked_responses_2026-11-25.csv data/bolnicacolic_full_v1.csv data/db_visit_msg_ids_2026-11-25.csv
```

| | |
|---|---|
| Converted clinic file | `data/Pacijenti_Joined_BolnicaColic.csv` (current 16 columns + `age`), SHA-256 `59719773733c7b8a95d16efe4a532f3a29d5ee22a207410ad8f617ad3f111f31`. Mapping and checks in `scripts/0_convert_old_format.py`. Dropped: `Telefon2` (= `Telefon` on every row), `R` (empty), `Spol` (= `Spol2`). This file is what the load stores and `04` exports back |
| Load file | `data/bolnicacolic_full_v1.csv`, SHA-256 `3ab8932fa8aa22b6b574db01b5c8a6eba5f579ca5ac41201311d4cb64102cc6e` |
| Row kinds | 2,452 rows: 2,443 legacy_invite / 9 legacy_visit (no phone, no response) |
| Responses | **720 linked** (166 numeric ids via `legacy_invite_map`, 554 uuid ids keep the uuid as Visit Msg id) |
| Send date (estimated) | answered rows: own response − 0.73 h (Ana: use the responses). Unanswered numeric ids (Spearman 0.942): the anchors' send-time quantiles by id rank. Unanswered uuid ids (no order): spread over the uuid responses' send times (Ana). The uuid responses come in bulk-send months (Feb, May, Aug 2024; Jun 2025; Mar 2026), so the busiest estimated days (5 Mar 2026: 554, 25 Jun 2025: 381) match real bulk sends |
| Visit date (estimated) | send − 49.6 h (median of the six done Accounts) |
| Status (estimated) | DELIVERED 2,220, UNDELIVERABLE 223 (88.1 %, the Account's own rate; answered = DELIVERED) |
| Year of birth (estimated) | visit year − `Dob` (age at the visit, to confirm); 0 → empty |
| Legacy response rate | **32.4 %** (platform 17.7 %, two weeks only). The file has 720 answered of 2,452 rows, so it may lack unanswered invites. `rate_tolerance` 20; question for Karlo |
| Time zone | the builder and SQL use `Europe/Zagreb`; the Location is `Europe/Belgrade`, which has the same offset all year |

SQL: `sql_config.json` (layout 2, `uuid_legacy_ids`) rendered by `tools/render_legacy_sql.py`. Mock test: `bash tests/run_mock_test.sh data/Pacijenti_Joined_BolnicaColic.csv` → **ALL CHECKS PASSED** (25 Nov 2026).
