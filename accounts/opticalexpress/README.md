# Optical Express legacy import

Import of the pre-platform history of **Optical Express** (EU, `insider-prod`): survey invites sent Jun 2023 – Mar 2025 outside InsiderCX, before the first platform invite on 4 Mar 2025. The clinic's original file can be exported back exactly.

| | |
|---|---|
| Linear | [DEV-232](https://linear.app/insidercx/issue/DEV-232/upload-legacy-data-for-kvaternik-mazalin-and-opticalexpress-to-the-stg) · plan: [`docs/plans/2026-11-06_kvaternik-mazalin-opticalexpress.md`](../../docs/plans/2026-11-06_kvaternik-mazalin-opticalexpress.md) |
| Load code | `OPTICALEXPRESS_LEGACY_V1` |
| Account / Location / Survey | 44 / 79 / 25 on EU prod. Scripts resolve them from Alchemer survey **90535032** |
| Owner | Ana (ana@insidercx.com) |
| Status | Step 1 (discovery) done 6 Nov 2026. Next: load file and mock test |

All numbers are **real**, read from the EU prod replica or the input files on 6 Nov 2026, unless marked estimated.

## 1. Inputs

| File | What it is | SHA-256 |
|---|---|---|
| `Pacijenti_joined_OpticalExpress.csv` | 7,931 rows + header, 16 columns (base 15 + `sent_at`). 3,850 rows are platform Visit Msgs (uuid id); **4,081 are legacy** (4,080 numeric ids + 1 text id) | `802a8e335b31f236ec8adbbde0567a34193fb065e4bb6aabdf1a5dc17be43c8a` |
| `Surevy_responses_OpticalExpress.csv` | Alchemer export joined with patient fields: 1,228 responses. 594 uuid (linked), 634 numeric legacy sguids | `46e3a445a9305287764b90e3ebce31cb2077bd77e17bd8e1cc002ce0fb86dfc6` |
| `db_unlinked_responses_2026-11-06.csv` | Unlinked Survey Responses from the prod replica | — |

All files hold Patient PII and live in `data/` (git-ignored).

## 2. Facts that shape the build

1. **Region:** EU only. One Location (79).
2. **Legacy rows have no `source_id`** (0 of 4,081); all have a phone. `year_of_birth` is `0` on every row (→ empty).
3. **Only 700 legacy rows have a visit date** (Jan 2024: 563, Jan 2025: 137). Visit dates can't carry the send-date estimate.
4. **SMS status** (real where filled): DELIVERED 2,512 (mixed case `DELIVERED` / `Delivered`, likely two old SMS providers), REJECTED 104, UNDELIVERED 49, UNDELIVERABLE 46, EXPIRED 8, PENDING 6, **empty 1,356**. Answered: 18.7% of empty-status rows vs 13.9% of filled ones, so empty means "not recorded", not "not sent". **21 answered rows have a non-delivered status** (O4).
5. **56 legacy ids are repeated** (113 rows), each pair with different phones, none answered (decision 7: not loaded).
6. **Legacy id schemes:** 10–423, `70…`, `701…`, `801…`, `7011…`–`7012…`. Id vs response start: **Spearman 0.933 (fails the 0.95 gate)**; schemes overlap in time.
7. **Language:** SLO 3,877, HR 204 on legacy rows. Templates: SURVEY_INVITE HR 112, SL 113 (Location 79). `SLO` / `SL` → SL.
8. **Dates are day-first**, Zagreb local (checked on responses 100, 101).

## 3. Unlinked Survey Responses (683)

| Group | Count | Linkable? |
|---|---|---|
| Numeric sguid = a legacy row id, not Deleted | **634** | yes, but **not linked now** (decision 2) |
| Numeric or text sguid = a legacy id, Deleted | 4 (3 numeric + the one text id) | no (decision 8) |
| Numeric sguid **missing from the clinic file** | 32 | no; open item O3 |
| Other text / test sguid | 9 (4 Deleted) | no |
| Empty sguid | 4 (1 Deleted) | no |

Responses in the survey export but missing from the DB: 0. In the DB but not in the export: 49.

## 4. Platform benchmarks (all platform invites to 6 Nov 2026)

| Benchmark | Value |
|---|---|
| Delivery rate (Mar 2025 – Oct 2026) | 88.2% |
| Response rate over delivered | 17.5% (593 / 3,396) |
| Visit → send median | 183.0 h |
| Send → response median | 3.02 h |
| Most common send hour (Zagreb) | 16:00 |
| Quarantine / age limit | 90 days / none |
| Sending | `INFOBIP_SMS_MAIN`, sender `OpticalExp` |
| Baseline on prod: Patients / Patient Visits / Patient Tickets / Visit Msgs | 3,854 / 3,854 / 0 / 3,850 |

## 5. What gets estimated

| Value | Rule | Real or estimated |
|---|---|---|
| Send date | DEV-162 method per id scheme, quantiles for weak schemes, weekends → Monday. Fails the 0.95 gate | estimated |
| Visit date | file where present (700), else send − 183 h | real / estimated |
| Delivery status | file; empty + answered → DELIVERED; empty + not answered → 88.2% by hash; 21 answered non-delivered → DELIVERED | real / estimated / corrected |
| Invite or not | every legacy row was sent | real |
| Patient | phone match to one existing Patient, else one new Patient per phone | rule |

Expected legacy figures, **if linked** (estimated): ≈3,654 delivered of 3,968 loaded (2,703 real or corrected + ≈951 estimated), 634 responses, response rate ≈17.4% (platform 17.5%). Without linking (decision 2): 3,968 invites, 0 responses.

## 6. Open items

See the plan: O1 (link?), O2 (repeated ids), O3 (32 missing invites), O4 (21 corrected statuses), O5 (no real send dates).
