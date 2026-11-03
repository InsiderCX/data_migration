# Stomatološka poliklinika Apolonija: staging run

Runbook for the person with write access to **EU staging**. Claude can't reach staging; paste each result back.
Plan: [`docs/plans/2026-11-03_videntis-arcadia-apolonija.md`](../../docs/plans/2026-11-03_videntis-arcadia-apolonija.md) (step 4). Account card: [`README.md`](README.md).

## Before you start

- Load file: `data/apolonija_full_v1.csv`, SHA-256 `800c54df6452f30261edf79d8b8bfdb27ec0c6aba113aab01f43a2b625f8e8ef`. If the hash differs, compare the values before rejecting it (a lost final newline changes the hash).
- Staging is used as it is, without a fresh snapshot (decision 2). Responses that reached prod after the staging copy was made can be missing there.
- Ops SQL (05–08) is not written yet. This run covers the load, validation, export and rollback.
- Run every file in the GUI as a whole, unless the step says "one query at a time". Check the GUI's commit mode before `02`.

## Steps

| # | Do | Expect | Paste back |
|---|---|---|---|
| 0 | `SELECT current_database() AS db, (SELECT name FROM account a JOIN survey s ON s."accountId" = a.id WHERE s."alchemerId" = '90492576') AS account, (SELECT count(*) FROM survey_response sr JOIN survey s ON s.id = sr."surveyId" WHERE s."alchemerId" = '90492576' AND sr.visit_msg_id IS NULL) AS unlinked;` | EU staging, `Stomatološka poliklinika Apolonija`, unlinked close to 1,566 (prod, 3 Nov 2026) | the row |
| 1 | `sql/01_before_import.sql` | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_apolonija_full / 0` | the row, or the error |
| 2 | GUI import of `data/apolonija_full_v1.csv` into the **existing** `stg_apolonija_full`. Every column as TEXT, header row on, empty = NULL | — | any warning |
| 3 | The count query at the bottom of `01` (uncomment it) | 67,895 / 11,420 / 10,516 / 20,383 / 25,576 | the row |
| 4 | `sql/02_load.sql` | `APOLONIJA_LEGACY_V1`, legacy_visits 30,899, legacy_invites 10,516, linked_responses 1,517, source_rows_stored 67,895. `platform_rows_linked` can be below 11,420 on an older copy | the row, or the error |
| 5 | `sql/03_validation.sql`, **one query at a time** | Query 1: source_rows 67,895, legacy_visits 30,899, legacy_invites 10,516, linked 1,517, deleted_linked 0, existing_patients_changed 0, legacy_rows_without_patient 0 | all three results |
| 6 | `sql/04_export_original_csv.sql`, export as CSV (comma, header, UTF-8) | 67,895 rows | save it to `accounts/apolonija/out/` (git-ignored); Claude compares it with the clinic file by value |
| 7 | `sql/99_rollback.sql` | source_rows_removed 67,895, legacy_visits_removed 30,899, remaining_batches 0 | the row |
| 8 | Steps 1–4 again, so the load stays on staging for ops | same as above | the 02 row |

## If something fails

- `Survey 90492576 found 0 times`: wrong database (UK?) or staging lacks the Account. Stop.
- `unlinked legacy responses found N, expected 1,517`: staging lacks some responses. Paste the message; Claude renders a staging-specific SQL with the real number. Don't edit the SQL by hand.
- `raw_visit_date was converted` or `raw_phone was converted`: the GUI typed a column. Drop `stg_apolonija_full`, run `01` again and re-import with every column as TEXT.
- Any other error: run `ROLLBACK;` and paste the message.

## Afterwards

Claude writes the run log in `runs/<date>_staging.md` from what you pasted.
