# SIE production run, 28 Oct 2026

Run log of the `SIE_LEGACY_V4` load on **EU production** (`insider-prod`). Ana ran every write in her GUI SQL client. Claude only read the prod replica (Zamera `icx-prod-eu__execute_sql`) to check the state before and after. No other Account was touched.

Use this log as the template for the next Account's run: same order, same checks, same "what was real / what was estimated" wording.

## Step 0: preparing the load file (done before staging)

The load file holds **everything from the clinic's file that wasn't already in the database**, plus estimates for the values the clinic's file doesn't have. How it was built is in the account card (`README.md` §5). In short:

| Clinic's file had | Missing, so estimated | How the estimate was fitted to the real data |
|---|---|---|
| Patients (name, phone, age), doctor, comment, legacy invite id | Visit date, send date, which visits got an invite, delivery status, year of birth, procedure | Send dates come from an isotonic fit of legacy invite id against the real response times (Spearman 0.994). Invites come from replaying the platform's quarantine and age rules. Delivery status uses the platform delivery rate (95.2%). Visit date = send − the platform's visit→send median (27 h) |
| Survey Responses (from the Alchemer export) | — | Real. They are only linked to the estimated invites, never changed |

The result: estimated legacy response rate 18.5%, against 15.0% on the platform. Replayed on platform-era visits, the invite rule recovered 93% of real invites and over-counted by about 10%. So the real legacy response rate is probably 1–2 points **higher** than shown. NPS 86.5 is real.

- File: `data/sie_full_v4.csv`, 14,254 rows. SHA-256 `194cc2c20f5e7457a664a4d022b3c3130a5ee6813cb01b3592055237f180f434`. Ana's local copy was re-checked on 28 Oct 2026 and matches exactly.
- Staging (EU) was validated on 23–26 Oct 2026, and ops confirmed it.

## Pre-flight (prod replica, before any write)

| Check | Value |
|---|---|
| Database / Account 36 | `insider-prod` / Stomatologija i estetika |
| Unlinked Survey Responses (survey 90558103) | 507 (486 numeric legacy sguids) |
| Earlier attempts present (`import_batch`, `import_batch_id` columns, `legacy_import` batches, `legacy_*` tables) | none |
| `visit_msg.sending_batch_id` nullable | NO (original) |
| Link trigger has the legacy fallback | no (original) |
| Extensions `hstore`, `uuid-ossp` | present |
| Baseline: Patients / Patient Visits / initial invites sent (Account 36) | 2,021 / 5,569 / 2,704 |

Production had never been touched, so `00_cleanup_all.sql` was **not** run.

## Steps

| # | Action | Who | Result | Check |
|---|---|---|---|---|
| 1 | `SELECT current_database(), (SELECT name FROM account WHERE id = 36);` | Ana | `insider-prod`, `Stomatologija i estetika` | ✓ |
| 2 | `sql/01_before_import.sql` (whole file) | Ana | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_sie_full / 0` | ✓ 3 tables, trigger fallback, empty staging table |
| 3 | GUI import of `data/sie_full_v4.csv` into the existing `stg_sie_full` | Ana | — | One uploaded copy's SHA-256 differed only by a missing final newline; the values were identical (pandas compare), so it was accepted |
| 4 | Count check on `stg_sie_full` | Ana | 14,254 total / 2,681 platform / 2,692 legacy_invite / 8,881 legacy_visit | ✓ |
| 5 | `sql/02_load.sql` (whole file) | Ana | `SIE_LEGACY_V4`, account 36, location 57, survey 17, **mock_sending_batch_id 13128**, new_patients **1,334**, legacy_visits 11,573, legacy_invites 2,692, linked_responses 480, platform_rows_linked **2,681**, source_rows_stored 14,254 | ✓ The first replica check showed nothing yet, because the run hadn't finished or committed. Once the result row appeared, the replica had everything |
| 6 | `sql/03_validation.sql`, 3 queries one at a time | Ana, and Claude on the replica | see below | ✓ |
| 7 | BI comparison: `06_compare_bi_responses.sql` and R7 of `07_report_by_period.sql` | Claude on the replica, Ana on the new dashboard | **41 of 41 months match**, 863 = 863 responses | ✓ |
| 8 | `04_export_original_csv.sql`, export compared with the clinic file | — | **Not run, by decision.** Proven on staging and in the mock test. It stays in `PRODUCTION.md` and can be run at any time (read-only) | skipped |
| 9 | Clinicdash on prod: NPS Trends and Message performance May 2023 – Oct 2024; 16 Oct 2024 onward unchanged | Ana | Verified on the new dashboard | ✓ |
| 10 | `DROP TABLE public.stg_sie_full;` | Ana | Done. Replica check: table gone | ✓ |

### Step 6 details (prod replica, after the load; re-checked 28 Oct 2026 afternoon)

| Check | Value | Expected |
|---|---|---|
| Patients / visits (Account 36) | 3,355 / 17,142 | baseline + 1,334 / + 11,573 ✓ |
| Initial invites sent (Account 36) | 5,396 | baseline + 2,692 ✓ |
| Legacy invites in batch 13128 / rows in `legacy_invite_map` | 2,692 / 2,692 | ✓ |
| Source rows / legacy rows / platform rows linked | 14,254 / 11,573 / 2,681 | ✓ |
| Unlinked Survey Responses | **27** | 507 − 480 ✓ |
| Legacy responses linked | 480 | ✓ |
| Existing Patients changed (`created < loaded_at AND updated >= loaded_at`) | **0** | ✓ |
| Legacy Patients present / missing (`legacy_source_row`) | 2,121 / 0 | ✓ |
| Legacy rows without a visit | 0 | ✓ |
| Legacy NPS (real) | 480 responses, 436 promoters, 21 detractors, **86.5** | = staging = BI ✓ |
| Platform NPS (real) | 390 responses, NPS 90.0 (383 up to the BI cut-off of 21 Oct 2026 14:31) | 7 responses newer than the BI export ✓ |

Legacy Message performance by quarter, identical to staging. **Sent and delivered are estimates; responses are real.**

| Quarter | Sent (est.) | Delivered (est.) | Responses | Response rate (est.) |
|---|---|---|---|---|
| 2023 Q2 | 543 | 520 | 113 | 21.7 |
| 2023 Q3 | 456 | 446 | 86 | 19.3 |
| 2023 Q4 | 477 | 455 | 57 | 12.5 |
| 2024 Q1 | 414 | 400 | 78 | 19.5 |
| 2024 Q2 | 367 | 347 | 69 | 19.9 |
| 2024 Q3 | 361 | 352 | 68 | 19.3 |
| 2024 Q4 (to 15 Oct) | 74 | 72 | 9 | 12.5 |
| **Total** | **2,692** | **2,592** | **480** | **18.5** |

## Identifiers on production (to find or undo this load)

- Load code: `SIE_LEGACY_V4`, `legacy_sending_batch.loaded_at` = 2026-10-28 09:01:01 UTC
- Mock sending batch: `visit_msg_sending_batch.id = 13128` (`trigger = 'legacy_import'`), registered in `legacy_sending_batch`
- Patients created by the load: `patient.created = legacy_sending_batch.loaded_at` for code `SIE_LEGACY_V4` (1,334)
- Source rows: `legacy_source_row.source_file = 'Pacijenti_JOINED_Stomatologija_i_estetika.csv'`
- Undo (data only): `sql/99_rollback.sql`

## Still open after this run

No dates or owners have been set for these yet.

- [ ] Tell the CSM / clinic: 2023 – Oct 2024 message figures (sent, delivered, response rate) are estimates; responses and NPS are real
- [ ] Restrict access to `legacy_source_row` like `patient` (it holds names and phones)
- [ ] Delete local copies of the clinic CSV, the load file (`~/Downloads/sie_full_v4.csv` and `data/`) and any exports
- [ ] UK staging: run `00_cleanup_all.sql` once (removes the accidental schema change from 23 Oct)
- [ ] Ops refresh from prod: R1/R2/R5/R6/R7 of `07_report_by_period.sql` and `08_ops_lists.sql`, then update the visual report and the ops workbook
- [ ] Retire the old Zoho pages once ops agree
- [ ] Open a separate bug ticket: `patient_visit.visit_date` stores local wall-clock time labelled as UTC

## Lessons from this run

These are now in `docs/pitfalls.md`, `docs/playbook.md` and `PRODUCTION.md`.

- In a GUI client, check the load's result row **and** the commit mode. No result row means the run didn't finish or isn't committed. Confirm on the replica before you move on.
- A file that passes through upload or download can lose its final newline. Compare the values, not only the hash, before deciding a file is different.
- Claude can run the read-only validation on the replica right after the load. That saves a round trip of pasting results.
