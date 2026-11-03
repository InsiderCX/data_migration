# Production run: SIE legacy full migration (v4)

> **Done on 28 Oct 2026**: see [`runs/2026-10-28_production.md`](runs/2026-10-28_production.md) for results and open items. Step 8 (export check) was skipped by decision. It stays documented below and can be run at any time (read-only).

Run **only after stg is confirmed** (validation in README §8, ops sign-off, Clinicdash checked). Prod was never touched by earlier attempts, so `00_cleanup_all.sql` is **not** used here.

## Go / no-go before starting

- [ ] Ops have reviewed the stg exports (`05_ops_exports.sql`) and the stg Clinicdash for Stomatologija i estetika.
- [ ] The CTO approves: 3 new tables + trigger change + data load on `insider-prod`.
- [ ] Dev confirms that code listing sending batches tolerates `trigger = 'legacy_import'`, or uses `legacy_sending_batch` to label it.
- [ ] A recent prod backup / point-in-time recovery is available.
- [ ] The input files match these hashes (`sha256sum`). If one differs, compare the values before rejecting it (a lost final newline changes the hash):
  - `Pacijenti_JOINED_Stomatologija_i_estetika.csv` `15ac2b3a88297a9f83397bce800f3d6efad8c7646ade4c76d9d2c1640daf8ffa`
  - `Sie_surveys.csv` `2d5ff2af674606f270bf22aa4ac7b0c09ef2c2e9f1d9768107635599c5b632cf`
  - `data/sie_full_v4.csv` `194cc2c20f5e7457a664a4d022b3c3130a5ee6813cb01b3592055237f180f434`
- [ ] Pick a quiet time. The Alchemer Sync and Visit Msg Sending Batches can keep running; the load is one short transaction.

## Steps (connection: EU prod `insider-prod`, write access)

| # | Do | Expected | If not |
|---|---|---|---|
| 1 | `SELECT current_database(), (SELECT name FROM account WHERE id = 36) AS account_36;` | `insider-prod`, `Stomatologija i estetika` | **Stop.** Wrong database (watch EU vs UK) |
| 2 | Baseline (keep the output): see query A below | unlinked ≈ 507, legacy batches 0 | Stop and investigate |
| 3 | Run `sql/01_before_import.sql` (whole file) | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_sie_full / 0` | `ROLLBACK;` and send the error |
| 4 | GUI: import `data/sie_full_v4.csv` into the **existing** `stg_sie_full` (all columns text, no key) | — | If the GUI insists on a new table: `DROP TABLE stg_sie_full;`, let it create the table with **every column TEXT** |
| 5 | Count check: query B | `14254 / 2681 / 2692 / 8881` | Re-import |
| 6 | Check the GUI's commit mode, then run `sql/02_load.sql` (whole file). Wait for the result row | `SIE_LEGACY_V4`, 36 / 57 / 17, legacy_visits **11573**, legacy_invites **2692**, linked_responses **480**, **platform_rows_linked 2681**, source_rows_stored **14254** | Nothing was saved (one transaction). `ROLLBACK;` and send the error. No result row = not finished or not committed |
| 6b | Ask Claude Code to confirm the load on the prod replica (read-only) | Same counts as step 6 | Don't continue until the replica shows the load |
| 7 | Run the 3 queries of `sql/03_validation.sql`, one at a time (or Claude Code runs them on the replica) | README §8. On prod `platform_rows_linked` = 2681 | `sql/99_rollback.sql`, investigate |
| 8 | Run `sql/04_export_original_csv.sql` → export CSV, compare with the original (`sha256sum` after export, or a diff) | Identical, 14,254 rows | Investigate (usually GUI export settings: comma, header, UTF-8) |
| 9 | Clinicdash (prod), Stomatologija i estetika: NPS Trends, General, Message performance for May 2023 – Oct 2024; 16 Oct 2024 onward unchanged against step 2 | Legacy period visible, NPS 86.5, ~18.5% legacy response rate | `sql/99_rollback.sql` |
| 9b | Run `sql/06_compare_bi_responses.sql` (4 queries, one at a time) | Query 1: bi 863, found 863, shown 863, not_found 0, score/sguid mismatch 0, status mismatch 1 (response 905 finished after the BI export). Query 2: no rows. Query 3: the 27 known + responses newer than 21 Oct 2026. Query 4: legacy 86.5, platform 90.3 | Investigate before go-live |
| 10 | Ops deliverables from prod: `sql/07_report_by_period.sql` (R1, R2, R5, R6, R7 as CSV) and `sql/08_ops_lists.sql` (invites.csv, responses.csv) | R7: all 41 months `match` | — |
| 10b | Build the ops workbook: `python3 -I scripts/3_build_ops_workbook.py invites.csv responses.csv SIE_invites_and_responses.xlsx --bi Joined.csv --source "EU production, <date>"`, then `recalc.py` | Legacy row: 2692 / 2592 / 480 / 18.5% / NPS 86.5 | — |
| 10c | Refresh the visual report (ask Claude Code / Claude to swap the five datasets of "SIE legacy migration review" for the prod R1, R2, R5, R6, R7 exports) | Every month green | — |
| 10d | (optional) `sql/05_ops_exports.sql` for field-level exports (11 CSVs) | — | — |
| 11 | `DROP TABLE public.stg_sie_full;` | — | — |
| 12 | Delete local copies of all CSVs and exports (PII). Keep this folder **without** `data/` | — | — |

**Query A: baseline, before step 3**
```sql
SELECT (SELECT count(*) FROM survey_response sr JOIN survey s ON s.id = sr."surveyId"
          WHERE s."alchemerId"::text = '90558103' AND sr.visit_msg_id IS NULL)            AS unlinked,           -- ≈ 507
       (SELECT count(*) FROM visit_msg WHERE account_id = 36)                              AS visit_msgs,
       (SELECT count(*) FROM patient_visit WHERE account_id = 36)                          AS visits,
       (SELECT count(*) FROM patient WHERE account_id = 36)                                AS patients,
       (SELECT count(*) FROM visit_msg_sending_batch WHERE trigger = 'legacy_import')      AS legacy_batches;     -- 0
```
After the load, expect: unlinked = baseline − 480; visit_msgs + 2,692; visits + 11,573; patients + (new Patients from step 6); legacy_batches 1.

**Query B: staging count**
```sql
SELECT count(*) AS total,                                          -- 14254
       count(*) FILTER (WHERE row_kind = 'platform')      AS platform,      -- 2681
       count(*) FILTER (WHERE row_kind = 'legacy_invite') AS legacy_invite, -- 2692
       count(*) FILTER (WHERE row_kind = 'legacy_visit')  AS legacy_visit   -- 8881
FROM public.stg_sie_full;
```

## Undo

- **Data only** (keeps the tables and trigger): `sql/99_rollback.sql`. It returns to the pre-load state; `02_load.sql` can then be run again. It stops if a Patient Ticket was created on a legacy visit.
- **Everything, including schema:** `sql/00_cleanup_all.sql`. It restores the original trigger and drops the 3 tables. Don't use it on prod unless the whole migration is abandoned.

## After the prod load

- [ ] Tell the clinic / CSM that 2023 – Oct 2024 **message figures (sent, delivered, response rate) are estimates**, while responses and NPS are real.
- [ ] Retire or hide the Zoho pages "Profili pacijenata" and "Ocjene iskustva" once ops agree.
- [ ] Restrict access to `legacy_source_row` like `patient` (it holds names and phones).
- [ ] Open a separate bug ticket: `patient_visit.visit_date` stores Zagreb wall-clock time labelled as UTC.
- [ ] UK stg: run `sql/00_cleanup_all.sql` once to remove the accidental schema change, if not done yet. Expect `unlinked_sie = 0`.
