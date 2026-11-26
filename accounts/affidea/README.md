# Affidea legacy import

Import of **Affidea**'s survey history from before the platform (EU, `insider-prod`). The legacy invites run from Apr 2023 to Jul 2024. The first platform invite was on 9 Jul 2024. Four Locations, and the largest file so far.

| | |
|---|---|
| Linear | [DEV-407](https://linear.app/insidercx/issue/DEV-407) build → [DEV-409](https://linear.app/insidercx/issue/DEV-409) staging → [DEV-411](https://linear.app/insidercx/issue/DEV-411) production · parent [DEV-375](https://linear.app/insidercx/issue/DEV-375) |
| Load code | `AFFIDEA_LEGACY_V1` |
| Account / Locations / Survey | 27 / 34 Čavka, 35 Kalajžić, 36 Sv. Rok, 37 Vita / 6 on EU prod (not in UK). Scripts resolve them from Alchemer survey **90540487** |
| Owner | Ana |
| Status | **Built and mock-tested 25 Nov 2026** (ALL CHECKS PASSED). Assumptions and the 3,532 missing invites for Karlo in DEV-409. Next: EU staging |

All numbers are **real**, read from the EU prod replica or the input files on 25 Nov 2026, unless marked estimated.

## 1. Inputs

| File | What it is | SHA-256 |
|---|---|---|
| `Pacijenti_JOINED_Affidea.csv` | Karlo, 24 Nov 2026. 163,121 rows + header, current format + `location_id` (34–37, matches prod). UTF-8 with BOM, 28 MB | `c62a96ab70ccee12795399a43010c60ac2e785c459992904fe2702e8c197add5` |
| `Survey_responses_Affidea.csv` | Alchemer export, 33,159 responses (28,596 Complete, 4,563 Partial), 70 columns, **month-first dates** (the only one of the three) | `ebda077f2430c5d68463b91c88189bd250ef73401d8868fab87664d7d20ab6a5` |
| `db_unlinked_responses_2026-11-25.csv` | Unlinked Survey Responses from the prod replica (11,323) | `c315461dcb90e5d6be1f0810f6e6b0f80e57b1c39efb74256d852fe88cd0ba42` |
| `db_visit_msg_ids_2026-11-25.csv` | The Account's Visit Msg ids on prod (126,903) | `23fc78f0e58b9fb368d9b5d64164c642470794e04b5647d1634fb250517d46ed` |

All files hold Patient PII and live in `data/` (git-ignored).

## 2. Facts that shape the build

1. **Region:** EU only. Four Locations, all `Europe/Zagreb`, quarantine 90 days, age limit 18. 28 SURVEY_INVITE templates, all per Location (`AA` and `HR`). Sending `INFOBIP_SMS_MAIN`, sender `Affidea`.
2. **Platform rows:** 126,684 file rows are Visit Msgs (`id` = `visit_msg.id`). 219 Visit Msgs on prod are not in the file (newer).
3. **Legacy rows: 36,437**: 36,431 numeric ids and 6 test ids. **No visit date or send date.** Source id, country and language are empty on every row; `location_id` and phone are filled.
4. **Repeated ids:** 12 ids over 30 rows, 9 of them exact copies. Rule: COPS-234 A2 flowchart (DEV-409).
5. **SMS status on legacy rows is real** and written as `GROUP_NAME`, e.g. `DELIVERED_TO_HANDSET` 35,299, `UNDELIVERABLE_NOT_DELIVERED` 447, `PENDING_WAITING_DELIVERY` 379, `UNDELIVERABLE_REJECTED_OPERATOR` 132, `EXPIRED_EXPIRED` 91, `REJECTED_DESTINATION` 44, `PENDING_ENROUTE` 25, `REJECTED_PREFIX_MISSING` 13, `REJECTED_NETWORK` 7. Platform rows use only the group (`DELIVERED`, …), the same as `visit_msg.status` on prod. So the part before the first `_` is the platform status: **legacy delivery rate 96.9%** (35,299 / 36,437, real). Question 1 in DEV-409 can be a simple confirmation.
6. **Legacy ids rise with time:** Spearman **0.998** (11,160 numeric anchors).
7. **Platform era:** 24,898 Visit Msgs in 2024 and 4,406 in 2025 have no `location_id` (the Patient Visit has one). The most common send hour in 2026 is 01:00 Zagreb (13:00 in 2024, 12:00 in 2025). Note only; doesn't affect the legacy rows.

## 3. Unlinked Survey Responses (11,323)

| Group | Count | Linkable? |
|---|---|---|
| Numeric sguid = a legacy row id | **7,628** live (+13 Deleted) | yes |
| Numeric sguid = a repeated legacy id | 1 live (+9 Deleted) | per COPS-234 A2 |
| **Numeric sguid, not in the file** | **3,532 live** (+5 Deleted) | **no: the invite is missing from Karlo's file** |
| Empty sguid | 112 (31 Deleted) | no |
| Test sguid | 21 (9 Deleted) | no |
| Text sguid | 2 | no |

- By year: 2023 4,945, 2024 6,335, 2025 19, 2026 23, plus 1 with `dateStarted` 1970.
- **The 3,532 missing invites are spread over Apr 2023 – Jul 2024**, the same months as the ones in the file. Peaks in Jan–May 2024, about 370–506 a month. So Karlo's file is missing part of the legacy invites, not one period. **New question for Karlo (proposed for DEV-409).**
- 3,694 unlinked responses are in the database but not in the export (3,136 Complete, 491 Partial, 67 Deleted). Check in step 2 whether they are the same 3,532.

## 4. Platform benchmarks (Jul 2024 – 24 Nov 2026)

| Year | Sent | Delivery rate | Response rate over delivered | Visit → send median |
|---|---|---|---|---|
| 2024 | 24,898 | 91.8% | 18.1% | 63 h |
| 2025 | 52,207 | 88.5% | 21.8% | 52 h |
| 2026 | 49,798 | 94.6% | 24.1% | 53 h |

- Send → response median: 11.8 h (all years).
- Baseline on prod: Patients / Patient Visits / Patient Tickets / Visit Msgs = 105,442 / 416,339 / 0 / 126,903.

## 5. What would be estimated (proposal, not approved)

| Value | Proposal | Real or estimated |
|---|---|---|
| Send date | isotonic fit id → (response start − 11.8 h) on the 7,628 anchors (Spearman 0.998) | estimated |
| Visit date | send − 63 h (2024 median, closest to the legacy period) | estimated |
| Delivery status | file (real); answered non-delivered → DELIVERED (as DEV-232) | real, some corrected |
| Invite or not | every legacy row was sent | real |
| Location | file `location_id` | real |

## 6. Open items

- Questions for Karlo: in [DEV-409](https://linear.app/insidercx/issue/DEV-409) (statuses, column `comment`). **Proposed new question: the 3,532 answered invites missing from the file.**
- `04` export check: 163,121 rows is over the Beekeeper 50,000-row export limit. Decide on split exports or a checksum in step 4.
- Template language: legacy language is empty on every row → `HR` per Location.

## Step 2–4: load file, mock test (25 Nov 2026)

Built without waiting for Karlo (Ana, 25 Nov 2026). Every assumption below is listed in DEV-409 for him to confirm.

```bash
python3 -I scripts/1_build_load_file.py data/Pacijenti_JOINED_Affidea.csv data/db_unlinked_responses_2026-11-25.csv data/affidea_full_v1.csv data/db_visit_msg_ids_2026-11-25.csv
```

| | |
|---|---|
| Load file | `data/affidea_full_v1.csv`, SHA-256 `c4cf313757cd9d6c5c325f085a46118a1f12e0d7077ea9495716a623ed6aef21` |
| Row kinds | 163,105 rows: 126,684 platform / 36,408 legacy_invite / 7 legacy_visit (no phone, no response) / 6 legacy_raw (test ids) |
| Discarded | 16 rows on repeated ids (COPS-234 A2 flowchart): 12 identical copies, 4 without phone or SMS status. Ids in `data/affidea_full_v1_discarded_rows.csv` |
| Responses | **7,628 linked**. Not linked: 22 Deleted, the response on a repeated id, and the 3,532 whose invite is missing from the file |
| Send date (estimated) | one id sequence (`scheme_rule` single), isotonic fit of id → response − 11.8 h, 12:00 Zagreb, Apr 2023 – 8 Jul 2024 (none in the platform period). 3,627 anchors' fitted sends were after their response and moved to 2 min before it |
| Visit date (estimated) | send − 63 h |
| Status (real) | from the file, group before `_` (`status_prefix`): DELIVERED 35,303, UNDELIVERABLE 574, PENDING 385, EXPIRED 91, REJECTED 55; **19 answered rows corrected to DELIVERED** |
| Location (real) | file `location_id` → Location name → id on the target database |
| Legacy response rate | **21.6 %** (platform 2024 18.1 %); would be higher with the 3,532 missing invites |

SQL: `sql_config.json` (layout 2, 4 Locations). Mock test: `bash tests/run_mock_test.sh data/Pacijenti_JOINED_Affidea.csv` → **ALL CHECKS PASSED** (25 Nov 2026). The rollback takes several minutes at this size.

