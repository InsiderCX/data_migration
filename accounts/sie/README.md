# SIE legacy full migration (v4)

Import of the pre-platform history of **Stomatologija i estetika** (EU, `insider-prod`) into the InsiderCX database, so that Clinicdash shows May 2023 – 15 Oct 2024 like any other period, and so that the clinic's original patient file can be exported back from the database exactly.

Written as a runbook for Claude Code (or a person) who needs to redo, check or undo this. Production steps: [`PRODUCTION.md`](PRODUCTION.md).

| | |
|---|---|
| Load code | `SIE_LEGACY_V4` |
| Account / Location / Survey | 36 / 57 / 17 on EU prod. Scripts resolve them from Alchemer survey **90558103**, so other environments can use other ids |
| Owner | Ana (ana@insidercx.com) |
| Status | Validated on EU stg 23–26 Oct 2026; ops confirmed. **Loaded on EU prod 28 Oct 2026** (mock sending batch 13128). Run log: [`runs/2026-10-28_production.md`](runs/2026-10-28_production.md) |

---

## 1. What problem this solves

- Before the platform (launched 16 Oct 2024), the clinic's survey invites were sent outside InsiderCX. The **480 Survey Responses** from that period exist in the DB (Alchemer Sync), but they aren't linked to any Visit Msg. All three Clinicdash reports reach responses through `visit_msg`, so those responses showed **nowhere**.
- The old data was only visible in Zoho pages ("Profili pacijenata", "Ocjene iskustva").
- Ops need the clinic's file `Pacijenti_JOINED_Stomatologija_i_estetika.csv` reproducible from the DB.

## 2. Inputs

| File | From | What it is | SHA-256 |
|---|---|---|---|
| `Pacijenti_JOINED_Stomatologija_i_estetika.csv` | Clinic / ops | 14,254 rows + header, 18 columns. Rows **with** `visit_date` (2,681) are platform-era invites already in the DB (`id` = `visit_msg.id`). Rows **without** `visit_date` (11,573) are legacy visits (`id` = numeric legacy invite id = the `sguid` in old survey links) | `15ac2b3a…0daf8ffa` |
| `Sie_surveys.csv` | Data analyst (Alchemer export) | 863 responses with `URL Variable: sguid`, `Time Started` (**Europe/Zagreb, month-first** `MM/DD/YYYY`), Q1 score. 480 have numeric legacy sguids | `2d5ff2af…c5b632cf` |
| `data/sie_full_v4.csv` | Built by `scripts/` | The load file, see §5 | `194cc2c2…f180f434` |

Full hashes are in [`PRODUCTION.md`](PRODUCTION.md). **All three files contain Patient PII.** Don't share them, and delete local copies after the prod load.

## 3. Where things run and what we connected to

| Purpose | How | Notes |
|---|---|---|
| Analysis / read checks | **Zamera MCP** connector `InsiderCX_Zamera_Central`, tools `icx-prod-eu__execute_sql` (and `icx-prod-uk__…`) | **Read-only streaming replica of prod.** Writes are impossible. Use the `icx-database` skill for schema and metric definitions |
| Zoho Analytics (old pages) | `zoho-analytics__*` | Token lacked scope (error 8540). Not needed in the end |
| Writes (stg, prod) | Ana's GUI SQL client (TablePlus-style) with write access | CSV import through the GUI. `psql` meta-commands (`\set`, `\copy`) do **not** work there |
| Script testing | Local PostgreSQL 16 mock: `tests/run_mock_test.sh` | Mirrors the real constraints. Run it after **any** change to the SQL |

⚠️ **Check EU vs UK every time.** EU and UK are separate databases with the same schema and different data. One stg session was accidentally on **UK stg** ("Account 36 mismatch"). Run this first: `SELECT current_database(), (SELECT name FROM account WHERE id = 36);`

## 4. Facts that shaped the design (verified on prod replica)

1. **Link trigger** `survey_response__set_visit_msg_id_from_sguid` (BEFORE INSERT **OR UPDATE**) sets `visit_msg_id` from `sguid::uuid` and NULLs it on a cast failure. Numeric legacy sguids can never link, and a hand-set link would be wiped by the next Alchemer Sync update. → The trigger gets a fallback to `legacy_invite_map` (scoped by Account).
2. `patient.id`, `patient_visit.id` and `visit_msg_sending_batch.id` are **`GENERATED ALWAYS` identity** columns → explicit ids need `OVERRIDING SYSTEM VALUE`.
3. Foreign keys into touched tables: `visit_msg_sending_batch.last_processed_visit_id → patient_visit` (**delete batches before visits**), `patient_ticket → patient / patient_visit`, `survey_invite_reminder_prep_log → visit_msg_sending_batch`, `survey_response.visit_msg_id → visit_msg ON DELETE SET NULL`.
4. **`patient_visit.visit_date` convention:** Zagreb wall-clock time stored as UTC (`10:00` local is stored `10:00+00`). Legacy visits follow the same convention. This is a separate bug for the platform; it's not fixed here.
5. **CSV `age` = age at the visit**, not "as of 2026" (verified on 999 existing Patients: 668 exact, 328 ±1). → `year_of_birth = year(visit) − age`. The first attempt got this wrong.
6. CSV `status` on legacy rows is **unreliable**: filled on exactly ~25% of each 1,000 ids, and empty on 348 of the 480 responded invites. It isn't used.
7. **Legacy ids are time-ordered:** Spearman 0.994 against response time, and legacy sends happened around 17:05 Zagreb. The basis for send-date estimation.
8. Platform benchmarks for this Account:
   - response rate 15.0%, delivery 95.2%
   - visit → send median 27 h, send → response median 0.8 h
   - 90-day quarantine, age limit 18, SMS sender `SiE`
   - templates 70 HR / 71 EN / 72 IT / 73 SL
   - Infobip SMS status names `DELIVERED_TO_HANDSET`, `UNDELIVERABLE_NOT_DELIVERED`
9. Of 507 unlinked responses, **480** match a legacy row. The other **27** can't be linked: 9 test links, 9 without sguid, 6 early ids (103, 106, 112, 116, 1014, 1015) missing from the clinic file, and 3 test-like long ids.

## 5. How the load file is built

```bash
python3 -I scripts/1_build_invites.py  Pacijenti_JOINED_Stomatologija_i_estetika.csv  Sie_surveys.csv  invites.csv
python3 -I scripts/2_build_full_v4.py  Pacijenti_JOINED_Stomatologija_i_estetika.csv  Sie_surveys.csv  invites.csv  data/sie_full_v4.csv
sha256sum data/sie_full_v4.csv    # must equal the hash in PRODUCTION.md (rebuild is byte-identical)
```
Built with Python 3.13, pandas 3.0, scikit-learn 1.9 (`IsotonicRegression`).

**Step 1: which legacy visits got an invite, and when** (`invites.csv`, 2,692 rows)
- **Anchors:** the 480 legacy rows whose `id` appears as a numeric sguid in `Sie_surveys.csv`.
- **Send time:** isotonic fit of legacy id → (response start − 0.8 h), done separately for short ids (< 1000) and `100`-prefixed ids (sequence = id without `100`). Snapped to 17:05 Zagreb on the predicted day. Responded rows are capped at response − 2 min.
- **Invite selection:** replay the platform rules per phone number. Invite the first visit, then nothing within 90 days; Patient ≥ 18 at the visit. Responded rows are always invited.
- **Status:** responded = DELIVERED. Others are DELIVERED except a deterministic 4.8% (`md5(id) mod 1000 < 48`) set to UNDELIVERABLE.
- **Validation of the rule:** replayed on platform-era visits, it produced 2,933 simulated vs 2,677 actual invites. 93% of real invites were recovered, with a ~10% overestimate, so the legacy response rate is probably 1–2 pp **higher** than shown.

**Step 2: one row per source row** (`data/sie_full_v4.csv`, 14,254 rows, 29 columns)
- `row_no` (file position), `row_kind` = `platform` 2,681 / `legacy_invite` 2,692 / `legacy_visit` 8,881.
- `raw_*`: the 18 original columns, **unchanged**.
- Computed for legacy rows:
  - `legacy_sguid`, `phone_clean` (digits only)
  - `est_visit_date` = send − 27 h, stored as wall-clock labelled `+00`
  - `est_sent_at` (UTC), `est_status`, `has_response`
  - `procedure_mock`: "Prvi pregled" if the comment contains `PP`/"prvi pregled", else "Zahvat". 95% accurate on the clinic's real visits
  - `derived_year_of_birth`, `sort_ts`
- Visit dates for the 8,881 non-invited rows come from the same id timeline.

## 6. What the load creates (`sql/02_load.sql`)

| Object | Rows | Real / estimated |
|---|---|---|
| `patient`: only Patients not yet present | ~1,340 on stg | Real clinic data, plus derived year of birth. **Existing Patients are never updated** (`ON CONFLICT DO NOTHING`) |
| `patient_visit` | 11,573 | Doctor and comment real. Visit date estimated. Procedure derived |
| `patient_visit_param` | 34,719 | `accommodation` / `organized_transport` from the file, plus `ignore_for_survey = true` so no survey is ever sent |
| `visit_msg_sending_batch` | **1** mock batch | `trigger = 'legacy_import'` |
| `visit_msg` | 2,692 | Filled like real SMS invites (template, sender, status names, quarantine expiry, `meta send_algo=legacy_import`). Send time and status estimated |
| `legacy_sending_batch` | 1 | Marks the batch as LEGACY DATA, with a comment on what's real and what's estimated |
| `legacy_invite_map` | 2,692 | legacy sguid → Visit Msg, used by the trigger |
| `survey_response` | 480 updated | Only the empty `visit_msg_id` is filled, through the trigger. Scores, comments and dates untouched |
| `legacy_source_row` | 14,254 | Every original row as `raw` jsonb, linked to `patient_id`, `patient_visit_id`, `visit_msg_id`, `sending_batch_id`. Platform rows are **only linked**, never created |

**Identifying the load later:**
- Legacy invites: `visit_msg.sending_batch_id IN (SELECT sending_batch_id FROM legacy_sending_batch WHERE code = 'SIE_LEGACY_V4')`
- Legacy visits: `legacy_source_row.patient_visit_id` where `row_kind <> 'platform'`
- Created Patients: `patient.created = legacy_sending_batch.loaded_at`. The whole load is one transaction, so `now()` is identical for every row.

Existing tables get **no new columns or constraints**. The schema change is 3 new tables plus the trigger fallback (`sql/01_before_import.sql`).

## 7. Run order

| # | Script | What it does | Expected |
|---|---|---|---|
| 00 | `00_cleanup_all.sql` | **Only where earlier attempts ran** (EU and UK stg). Removes all data and schema of earlier attempts and v4, and restores the original trigger. Stops with a message if a Patient Ticket references legacy data | Check row: `0 / NULL ×4 / NO / 0 / 507` (UK: `… / 0`) |
| 01 | `01_before_import.sql` | Refuses if leftovers exist. Drops old staging, creates the 3 tables and trigger fallback, creates an empty all-text `stg_sie_full` | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_sie_full / 0` |
| — | GUI import | `data/sie_full_v4.csv` into **existing** `stg_sie_full` | Count check `14254 / 2681 / 2692 / 8881` |
| 02 | `02_load.sql` | The load: one transaction, checks before and after, aborts on any mismatch | `SIE_LEGACY_V4`, legacy_visits 11573, legacy_invites 2692, linked_responses 480, source_rows_stored 14254 |
| 03 | `03_validation.sql` | 3 read-only queries; run each on its own | See §8 |
| 04 | `04_export_original_csv.sql` | Re-creates the clinic file from `legacy_source_row` | Identical to the original (14,254 rows) |
| 05 | `05_ops_exports.sql` | 11 exports for ops; columns prefixed `actual_` / `derived_` / `est_` / `mock_`. No names or phones | — |
| 06 | `06_compare_bi_responses.sql` | Current BI system (Joined.csv = Alchemer export, 863 responses) vs DB: presence, values, what dashboards show | Prod after load: 863 / 863 / 863 shown, 1 status diff (905). stg 26 Oct: 846 / 846 (17 newer than the stg copy), legacy 86.5 = BI |
| 07 | `07_report_by_period.sql` | Report for ops: Message performance, NPS Trends / General KPIs, score distribution, breakdowns, visits, DB-vs-BI per month. Bucket week / month / quarter / year set in the parameter block | — |
| 08 | `08_ops_lists.sql` | Every invite sent and every response, labelled actual / estimated, no PII. Feed to `scripts/3_build_ops_workbook.py` for the ops Excel | Legacy: 2692 sent / 2592 delivered / 480 responses |
| 99 | `99_rollback.sql` | Removes the v4 data (keeps the 3 tables and trigger) | Back to the pre-load state |

## 8. Expected validation results (EU stg, 23 Oct 2026)

| Check | Value |
|---|---|
| Source rows / legacy visits / legacy invites / linked responses | 14,254 / 11,573 / 2,692 / 480 |
| Platform rows linked | 2,593 on stg (an older copy, missing the latest 88 invites). **Must be 2,681 on prod** |
| Existing Patients changed / unlinked responses | 0 / 27 |
| Legacy Patients present / missing | 2,121 / 0 |
| Legacy NPS | 480 responses, 436 promoters, 21 detractors, **86.5** (= the analyst's Alchemer export) |

| Quarter | Sent | Delivered | Responses | Response rate |
|---|---|---|---|---|
| 2023 Q2 | 543 | 520 | 113 | 21.7 |
| 2023 Q3 | 456 | 446 | 86 | 19.3 |
| 2023 Q4 | 477 | 455 | 57 | 12.5 |
| 2024 Q1 | 414 | 400 | 78 | 19.5 |
| 2024 Q2 | 367 | 347 | 69 | 19.9 |
| 2024 Q3 | 361 | 352 | 68 | 19.3 |
| 2024 Q4 (to 15 Oct) | 74 | 72 | 9 | 12.5 |
| **Total** | **2,692** | **2,592** | **480** | **18.5** |

Message performance sent and delivered counts for the legacy period are **estimates**. Responses and NPS are real.

## 9. Pitfalls we hit (and the fix that's now built in)

| Symptom | Cause | Now |
|---|---|---|
| `Account 36 mismatch` / `Survey 90558103 not found` | Connected to **UK** stg | Check the environment first; ids are resolved via the Alchemer id |
| `value "385…" (a phone number) is out of range for type integer` | GUI typed `phone` as integer | `01` creates the staging table as all-text |
| `duplicate key … stg_…_pkey` | GUI added a primary key on a repeating column | Same as above, plus a unique `row_no` |
| `relation "stg_…" already exists` | GUI only imports into new tables in some modes | Import into the existing table; if impossible, drop it and let the GUI create it as **all TEXT** |
| `syntax error at or near "\"` | `\set` / `\copy` are psql-only | Not used in the scripts |
| Only the last result shown | GUI shows only the last statement of a file | Run validation queries one at a time |
| JSON result with a single `count` | Duplicate column names collapsed | All columns are aliased |
| `cannot insert a non-DEFAULT value into column "id"` (prevented) | Identity `GENERATED ALWAYS` | `OVERRIDING SYSTEM VALUE` |
| `violates foreign key constraint "fk_last_processed_visit_id"` | Visits deleted before batches | Batches are deleted first |
| Year of birth 2–3 years off | `age` misread as "age in 2026" | `year(visit) − age` |
| Silent change of `raw_*` | GUI auto-typing dates or numbers | `02` refuses if `raw_visit_date` / `raw_phone` were converted |

## 10. History (for context only; superseded by v4)

1. `import_batch` design with `import_batch_id` columns on existing tables and a nullable `sending_batch_id`. Dropped: it changed existing tables.
2. v3: 366 per-day mock batches and `legacy_sending_batch`. Dropped: one batch is enough, and not every source row was in the DB.
3. **v4** (this): one mock batch, all 11,573 legacy visits, and an exact source copy in `legacy_source_row`.

`00_cleanup_all.sql` removes all of them.

## 11. Redoing this with Claude Code

1. Give Claude Code this folder, the two input files and access to the Zamera MCP connector. Ask it to read this README and `PRODUCTION.md` first.
2. Verify the inputs by hash. If the inputs changed (a new clinic export), rebuild with §5 and expect the counts in §8 to change. Then update the hard-coded expectations in `02_load.sql` (row-kind counts, 480 responses, 34,719 params) and `03_validation.sql`.
3. Re-check the facts in §4 on the prod replica (trigger definition, identity columns, foreign keys, templates). Schema drift is the main risk.
4. Run `bash tests/run_mock_test.sh <Pacijenti_JOINED…csv>`. Everything must pass (export identical, ops exports without errors, rollback and cleanup back to baseline).
5. Then run stg as in §7, then prod as in `PRODUCTION.md`.
6. Claude Code can only **read** stg and prod through Zamera. The writes are run by a person with write access.
