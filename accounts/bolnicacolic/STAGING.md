# Bolnica Colić: staging run

Runbook for **EU staging** (DEV-377). Claude runs it with `bash tools/run_staging.sh bolnicacolic Pacijenti_Joined_BolnicaColic.csv` (Ana's permission for staging only, 25 Nov 2026; the script refuses anything but `insider-eu-stg`). A person with a GUI can follow the same steps. Account card: [`README.md`](README.md).

## Before you start

- Load file: `data/bolnicacolic_full_v1.csv`, SHA-256 `3ab8932fa8aa22b6b574db01b5c8a6eba5f579ca5ac41201311d4cb64102cc6e`. If the hash differs, compare the values before rejecting it (a lost final newline changes the hash).
- Staging needs the private network (VPN). Without it the connection times out.
- The clinic file is the **converted** file (`scripts/0_convert_old_format.py` from Karlo's `Pacijenti_DrColic.csv`). `04` must equal the converted file.
- 554 legacy Visit Msgs keep the old system's uuid as their id (`uuid_legacy_ids`); 166 numeric ids link through `legacy_invite_map`.
- Karlo's open questions and the assumptions this build makes are in DEV-377. A different answer means a rebuild and a rerun.
- Run every file as a whole, unless the step says "one query at a time".

## Steps

| # | Do | Expect | Paste back |
|---|---|---|---|
| 0 | `SELECT current_database() AS db, s."alchemerId" AS survey, a.name AS account, (SELECT count(*) FROM location l WHERE l.account_id = a.id) AS locations, (SELECT count(*) FROM survey_response sr WHERE sr."surveyId" = s.id AND sr.visit_msg_id IS NULL) AS unlinked FROM survey s JOIN account a ON a.id = s."accountId" WHERE s."alchemerId" IN ('90511513');` | `insider-eu-stg`, `Bolnica Colić`, 1 Location(s), 1 row(s); unlinked in total close to 746 (prod, 25 Nov 2026). **The staging copy is from 28 Sep 2026; the Account may be missing there** (first platform invite 11 Nov 2026). If it is missing, stop: staging needs a fresh copy | the rows |
| 1 | `sql/01_before_import.sql` | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_bolnicacolic_full / 0` | the row, or the error |
| 2 | Import `data/bolnicacolic_full_v1.csv` into the **existing** `stg_bolnicacolic_full`. Every column as TEXT, header on, empty = NULL, trim whitespace **off** | — | any warning |
| 3 | The count query at the bottom of `01` | 2,452 / 0 / 2,443 / 9 / 0 (total / platform / legacy_invite / legacy_visit / legacy_raw) | the row |
| 4 | `sql/02_load.sql` | `BOLNICACOLIC_LEGACY_V1`, legacy_visits 2,452, legacy_invites 2,443, linked_responses **720**, source_rows_stored 2,452. `platform_rows_linked` can be below 0 (older copy) | the row, or the error |
| 5 | `sql/03_validation.sql`, **one query at a time** | Query 1: source_rows 2,452, legacy_visits 2,452, legacy_invites 2,443, linked 720, deleted_linked 0, existing_patients_changed 0, legacy_rows_without_patient 0. Query 2: 2023 Q1 – 2026 Q2: sent 2,443 in total, delivered 2,220, responses 720 (32.4 %) | all results |
| 6 | `sql/04_export_original_csv.sql` as CSV | 2,452 rows, identical to the converted clinic file | saved in `out/` (git-ignored) |
| 7 | `sql/99_rollback.sql` | source_rows_removed 2,452, legacy_visits_removed 2,452, remaining_batches 0 | the row |
| 8 | Steps 1–4 again, so the load stays on staging for ops | same as above | the 02 row |

## If something fails

- `Survey 90511513 found 0 times`: wrong database (UK?) or staging lacks the Account. Stop.
- `unlinked legacy responses found N, expected 720`: staging lacks some responses (older copy). Claude renders a staging-specific SQL with the real number. Don't edit the SQL by hand.
- `legacy rows that already exist as Visit Msgs`: the staging copy has Visit Msgs the prod export didn't. Stop and compare.
- `raw_visit_date was converted` / `raw_phone was converted`: a GUI typed a column. Drop `stg_bolnicacolic_full`, run `01` again, re-import as TEXT.
- Any other error: `ROLLBACK;` and paste the message.

## Afterwards

Claude writes the run log in `runs/<date>_staging.md`.
