# Optical Express: staging run

Runbook for **EU staging**. For DEV-232 Claude runs it with `bash tools/run_staging.sh opticalexpress Pacijenti_joined_OpticalExpress.csv` (Ana's permission, 6 Nov 2026; the script refuses anything but `insider-eu-stg`). A person with a GUI can follow the same steps.
Plan: [`docs/plans/2026-11-06_kvaternik-mazalin-opticalexpress.md`](../../docs/plans/2026-11-06_kvaternik-mazalin-opticalexpress.md) (step 3). Account card: [`README.md`](README.md).

## Before you start

- Load file: `data/opticalexpress_full_v1.csv`, SHA-256 `c92691de52ba7335fbfa3b21c3f8c458ef054389de7412f89c364a7b53e4387d`. If the hash differs, compare the values before rejecting it (a lost final newline changes the hash).
- **Append only, no linking** (decision 2): the load must not change any existing row. `linked_responses` is 0 by design.
- Staging is used as it is. Responses that reached prod after the staging copy was made can be missing there.
- Run every file as a whole, unless the step says "one query at a time".

## Steps

| # | Do | Expect | Paste back |
|---|---|---|---|
| 0 | `SELECT current_database() AS db, (SELECT name FROM account a JOIN survey s ON s."accountId" = a.id WHERE s."alchemerId" = '90535032') AS account, (SELECT count(*) FROM survey_response sr JOIN survey s ON s.id = sr."surveyId" WHERE s."alchemerId" = '90535032' AND sr.visit_msg_id IS NULL) AS unlinked;` | EU staging, `Optical Express`, unlinked close to 683 (prod, 6 Nov 2026) | the row |
| 1 | `sql/01_before_import.sql` | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_opticalexpress_full / 0` | the row, or the error |
| 2 | Import `data/opticalexpress_full_v1.csv` into the **existing** `stg_opticalexpress_full`. Every column as TEXT, header on, empty = NULL | — | any warning |
| 3 | The count query at the bottom of `01` | 7,931 / 3,850 / 3,966 / 2 / 113 (total / platform / legacy_invite / legacy_visit / legacy_raw) | the row |
| 4 | `sql/02_load.sql` | `OPTICALEXPRESS_LEGACY_V1`, legacy_visits 3,968, legacy_invites 3,966, linked_responses **0**, source_rows_stored 7,931. `platform_rows_linked` can be below 3,850 | the row, or the error |
| 5 | `sql/03_validation.sql`, **one query at a time** | Query 1: source_rows 7,931, legacy_visits 3,968, legacy_invites 3,966, linked 0, deleted_linked 0, existing_patients_changed 0, legacy_rows_without_patient 0. Query 4 (if linked): 8 quarters 2023 Q2 – 2025 Q1, 3,966 sent, 3,649 delivered, 634 responses_if_linked, linked_now 0 | all results |
| 6 | `sql/04_export_original_csv.sql` as CSV | 7,931 rows, identical values to the clinic file | saved in `out/` (git-ignored) |
| 7 | `sql/99_rollback.sql` | source_rows_removed 7,931, legacy_visits_removed 3,968, remaining_batches 0 | the row |
| 8 | Steps 1–4 again, so the load stays on staging for ops | same as above | the 02 row |

## If something fails

- `Survey 90535032 found 0 times`: wrong database (UK?) or staging lacks the Account. Stop.
- `unlinked legacy responses found N, expected …`: staging lacks some responses. Claude renders a staging-specific SQL with the real number. Don't edit the SQL by hand.
- `legacy rows that already exist as Visit Msgs`: the staging copy has Visit Msgs the prod export didn't. Stop and compare.
- `raw_visit_date was converted` / `raw_phone was converted`: a GUI typed a column. Drop `stg_opticalexpress_full`, run `01` again, re-import as TEXT.
- Any other error: `ROLLBACK;` and paste the message.

## Afterwards

Claude writes the run log in `runs/<date>_staging.md`.
