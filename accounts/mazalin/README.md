# Poliklinika Mazalin legacy import

Import of the first months of **Poliklinika Mazalin** (EU, `insider-prod`) that the platform never stored as Visit Msgs: two bulk sends (12 Feb and 27 Mar 2024) for visits from Dec 2023 to Mar 2024, before the first platform invite on 23 Apr 2024. The clinic's original file can be exported back exactly.

| | |
|---|---|
| Linear | [DEV-232](https://linear.app/insidercx/issue/DEV-232/upload-legacy-data-for-kvaternik-mazalin-and-opticalexpress-to-the-stg) · plan: [`docs/plans/2026-11-06_kvaternik-mazalin-opticalexpress.md`](../../docs/plans/2026-11-06_kvaternik-mazalin-opticalexpress.md) |
| Load code | `MAZALIN_LEGACY_V1` |
| Account / Location / Survey | 24 / 31 / 13 on EU prod. Scripts resolve them from Alchemer survey **90553181** |
| Owner | Ana (ana@insidercx.com) |
| Status | Step 1 (discovery) done 6 Nov 2026. Next: load file and mock test |

All numbers are **real**, read from the EU prod replica or the input files on 6 Nov 2026, unless marked estimated.

## 1. Inputs

| File | What it is | SHA-256 |
|---|---|---|
| `Pacijenti_Joined_Mazalin.csv` | 30,481 rows + header, 16 columns (base 15 + `sent_at`). 28,028 rows are platform Visit Msgs (`id` = `visit_msg.id`); **2,453 are legacy** (uuid id, no `sent_at`, Visit Msg missing) | `73e39f554fbd6dc51ebff25e61593bedd32fc336e9f6a6b9dc08fa74b135b773` |
| `Surevy_responses_Mazalin.csv` | Alchemer export joined with patient fields: 5,529 responses, all uuid sguids. 5,092 already linked, 437 point to legacy rows | `4a0bf901ba9c85f0f03c498ae33adbc61a2905f37447e715085ed589a48c365b` |
| `db_unlinked_responses_2026-11-06.csv` | Unlinked Survey Responses from the prod replica | — |

All files hold Patient PII and live in `data/` (git-ignored).

## 2. Facts that shape the build

1. **Region:** EU only. One Location (31).
2. **Legacy rows:** 2,453, visits 1 Dec 2023 – 26 Mar 2024 (Dec 645, Jan 921, Feb 886, Mar 1), all with phone, 2,452 with `source_id`.
3. **Real responses show two bulk sends:** 248 responses on 12–14 Feb 2024 (first 15:02 UTC), 152 on 27–29 Mar 2024. Wave 1 answers come from visits Dec–Jan, wave 2 from visits Feb–Mar (plus 8 late answers from January visits).
4. **SMS status is filled on every legacy row** (real): DELIVERED 2,384, PENDING 28, UNDELIVERABLE 21, EXPIRED 13, REJECTED 7. **15 answered rows have a non-delivered status** (open item O4).
5. **Year of birth** is a year; 76 values are junk (3-digit, 1-digit, `1072`) → empty.
6. **Dates are day-first**, Zagreb local. Alchemer `Time Started` = DB `dateStarted` + 1 h (checked on responses 100, 102).
7. **Template:** SURVEY_INVITE HR 44 (no Location). Legacy language is almost always empty → HR.

## 3. Unlinked Survey Responses (471)

| Group | Count | Linkable? |
|---|---|---|
| uuid sguid = a legacy row id | **437** | yes, but **not linked now** (decision 2) |
| Empty sguid | 28 (4 Deleted) | no |
| Text / test sguid | 6 (1 Deleted, 1 test) | no |

Responses in the survey export but missing from the DB: 0. In the DB but not in the export: 34 (the empty / text ones).

## 4. Platform benchmarks (all platform invites to 6 Nov 2026)

| Benchmark | Value |
|---|---|
| Delivery rate (2024 – Oct 2026) | 95.2% |
| Response rate over delivered | 19.0% (5,030 / 26,505) |
| Visit → send median | 36.1 h |
| Send → response median | 0.23 h |
| Most common send hour (Zagreb) | 16:00 |
| Quarantine / age limit | 90 days / 18 |
| Sending | `INFOBIP_SMS_MAIN`, sender `PolMazalin` |
| Baseline on prod: Patients / Patient Visits / Patient Tickets / Visit Msgs | 19,517 / 38,255 / 0 / 28,028 |

## 5. What gets estimated

| Value | Rule | Real or estimated |
|---|---|---|
| Send date | visits ≤ 31 Jan 2024 → 12 Feb 2024 15:00 Zagreb; later → 27 Mar 2024, before that day's first response | estimated |
| Visit date | file | real |
| Delivery status | file; 15 answered non-delivered → DELIVERED | real, 15 corrected |
| Invite or not | every legacy row was sent | real |

Expected legacy figures, **if linked**: 2,399 delivered of 2,453 (97.8%), 437 responses, response rate 18.2% (platform 19.0%). Without linking (decision 2): 2,453 invites, 0 responses.

## 6. Open items

See the plan: O1 (link?), O4 (15 corrected statuses).
