# Orto-Nova legacy import

Import of **Orto-Nova**'s survey history from before the platform (EU, `insider-prod`). The legacy invites run from Nov 2022 to May 2025. The first platform invite was on 19 May 2025.

| | |
|---|---|
| Linear | [DEV-406](https://linear.app/insidercx/issue/DEV-406) build → [DEV-408](https://linear.app/insidercx/issue/DEV-408) staging → [DEV-410](https://linear.app/insidercx/issue/DEV-410) production · parent [DEV-375](https://linear.app/insidercx/issue/DEV-375) |
| Load code | `ORTONOVA_LEGACY_V1` |
| Account / Location / Surveys | 49 / 112 / **three Surveys** on EU prod (not in UK): 30 Orto-Nova (Alchemer **90492015**), 29 Orto-Nova-IT (**90509784**), 28 Orto-Nova-SLO (**90509787**) |
| Owner | Ana |
| Status | **Built and mock-tested 25 Nov 2026** (ALL CHECKS PASSED), linking to all three Surveys. Assumptions for Karlo in DEV-408. Next: EU staging |

All numbers are **real**, read from the EU prod replica or the input files on 25 Nov 2026, unless marked estimated.

## 1. Inputs

| File | What it is | SHA-256 |
|---|---|---|
| `Pacijenti_Joined_OrtoNova.csv` | Karlo, 24 Nov 2026. 35,557 rows + header, current format + `location`, `p`. UTF-8 with BOM | `422bfed8670c5e8665da7c15c6e8859e5847433aa42e387e54d85f1d675a490c` |
| `Survey_responses_OrtoNova.csv` | Alchemer export of **all three Surveys in one table**, 3,548 responses (2,756 Complete, 792 Partial), 139 columns. Response IDs repeat across Surveys (1,062 ids twice) | `91590c06f88d2ae610ad1e3f45b0820763e8af7024443ccddcf4a72bc6df626b` |
| `db_unlinked_responses_2026-11-25.csv` | Unlinked Survey Responses from the prod replica (2,403), with their Alchemer survey | `9f89d03f86560c8b9951483c2f10b2991ffc88888bf53318d9c046a384626dbe` |
| `db_visit_msg_ids_2026-11-25.csv` | The Account's Visit Msg ids on prod (9,758) | `66302b24d8b6cc6ad89ad8898d1697d636ccb715fc73a08f0968cecb8b08750c` |

All files hold Patient PII and live in `data/` (git-ignored).

## 2. Facts that shape the build

1. **Region:** EU only. One Location (112), `Europe/Zagreb`, quarantine 90 days, age limit 18. Templates SURVEY_INVITE HR (#255), IT (#258), SL (#261). Sending `INFOBIP_SMS_MAIN`, sender `OrtoNova`.
2. **Platform rows:** 9,718 file rows are Visit Msgs (`id` = `visit_msg.id`). 40 Visit Msgs on prod are not in the file (newer than the file).
3. **Legacy rows: 25,839**, all numeric ids, **no visit date, send date, phone or source id**. Only name, language and procedure (1,877 without procedure).
4. **The legacy id has a prefix:** the first digit is the invite type, the rest is a counter.

   | Prefix | Procedure | Legacy rows |
   |---|---|---|
   | 1 | Prvi put | 3,927 (172 without procedure) |
   | 2 | Prethodni mjesec | 20,221 (1,553 without procedure) |
   | 3 | Gotovi radovi | 1,691 (152 without procedure) |

   Within each prefix and id length, ids rise with time: Spearman 0.945–0.999. Mixed together they don't (0.56).
5. **Languages:** HR 18,298, IT 13,488, SLO 2,485, SL 924, EN 205, DE 157 (whole file). `SLO` and `SL` both appear and need mapping to the template's `SL`.
6. **Three Surveys:** every one of the 3,548 export rows matches exactly one Survey Response on prod by (Response ID, sguid): Orto-Nova 2,161, Orto-Nova-IT 1,289, Orto-Nova-SLO 98. Language agrees with the Survey (IT → IT Survey, except 167 Italian answers on the HR Survey). **The builder and SQL support one Survey per Account today.**
7. **Dates are day-first**, Zagreb local.

## 3. Unlinked Survey Responses (2,403)

| Group | Count | Linkable? |
|---|---|---|
| Numeric sguid = a legacy row id | **1,995** | yes (if Karlo agrees to three Surveys) |
| Numeric sguid, not in the file | 26 (22 Deleted) | no; list for ops |
| Empty sguid | 326 (222 Deleted) | no |
| Test (sguid or flag) | 22 (4 Deleted) | no |
| Text sguid | 34 (all Deleted) | no |

- By year: 2022 475, 2023 902, 2024 827, 2025 179, 2026 20.
- Every legacy id is answered at most once.
- 378 unlinked responses are in the database but not in the export (282 Deleted, 97 Complete, 29 Partial). Mostly empty or test sguids; check in step 2.

## 4. Platform benchmarks (19 May 2025 – 24 Nov 2026)

| Benchmark | Value |
|---|---|
| Sent / delivered | 9,736 / 9,160 → delivery rate **94.1%** |
| Response rate over delivered | **17.6%** (1,611) |
| Visit → send median | 27.0 h |
| Send → response median | 2.0 h |
| Most common send hour (Zagreb) | 12:00 |
| Quarantine / age limit | 90 days / 18 |
| Baseline on prod: Patients / Patient Visits / Patient Tickets / Visit Msgs | 7,113 / 18,242 / 0 / 9,758 |

## 5. What would be estimated (proposal, not approved)

| Value | Proposal | Real or estimated |
|---|---|---|
| Send date | isotonic fit id → (response start − 2.0 h) **per prefix**, on the 1,995 anchors | estimated |
| Visit date | send − 27.0 h | estimated |
| Delivery status | 94.1%, deterministic by hash; answered rows DELIVERED | estimated |
| Invite or not | every legacy row was sent (it has an invite id) | real |
| Procedure where empty | from the id prefix (1/2/3) | estimated, if Ana agrees |
| Survey a response belongs to | prod match by (Response ID, sguid) | real |

## 6. Open items

- Questions for Karlo: in [DEV-408](https://linear.app/insidercx/issue/DEV-408) (three Surveys, column `p`, legacy rows without dates).
- **Builder and SQL: support for more than one Survey per Account** (new option; the other Accounts must rebuild byte-identical).
- Legacy rows have no phone: Patients can't be matched by phone. One new Patient per row unless Ana decides otherwise.

## Step 2–4: load file, mock test (25 Nov 2026)

Built without waiting for Karlo (Ana, 25 Nov 2026). Every assumption below is listed in DEV-408 for him to confirm.

```bash
python3 -I scripts/1_build_load_file.py data/Pacijenti_Joined_OrtoNova.csv data/db_unlinked_responses_2026-11-25.csv data/ortonova_full_v1.csv data/db_visit_msg_ids_2026-11-25.csv
```

| | |
|---|---|
| Load file | `data/ortonova_full_v1.csv`, SHA-256 `fda0bc45719ed589d8ead09ff32cb8e706c284a37c861c026bf65367d4889416` |
| Row kinds | 35,557 rows: 9,718 platform / 25,839 legacy_invite (`invite_rule` all_rows: every legacy row has its own invite id) |
| Responses | **1,995 linked**, on all three Surveys (`extra_alchemer_ids`; assumption, Karlo to confirm) |
| Send date (estimated) | per id scheme (`len_prefix`: invite type digit + digit count), isotonic fit of id → response − 2.0 h, 15:00 Zagreb. Scheme 5-digit/type 1 (846 rows) has Spearman 0.944 → anchors' quantiles; 8 rows of a 4-digit scheme with 1 anchor → median date. 1,010 anchors' fitted sends were after their response and moved to 2 min before it. Range Nov 2022 – Mar 2025 |
| Visit date (estimated) | send − 27 h |
| Status (estimated) | DELIVERED 24,368 / UNDELIVERABLE 1,471 (94.1 %; answered = DELIVERED) |
| Patients | 25,180 legacy rows have no phone → one new Patient per row (Ana). 659 rows with a phone attach to the one existing Patient with that phone if there is exactly one |
| Legacy response rate | **8.2 %** (platform 17.6 %), about 7–13 % every quarter. `rate_tolerance` 12; question for Karlo (are these all invites?) |

SQL: `sql_config.json` (layout 2, `extra_alchemer_ids` 90509784, 90509787). Mock test: `bash tests/run_mock_test.sh data/Pacijenti_Joined_OrtoNova.csv` → **ALL CHECKS PASSED** (25 Nov 2026), with responses spread over three mock Surveys.
