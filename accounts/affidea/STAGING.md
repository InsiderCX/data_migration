# Affidea: staging run

Runbook for **EU staging** (DEV-409). Claude runs it with `bash tools/run_staging.sh affidea Pacijenti_JOINED_Affidea.csv` (Ana's permission for staging only, 25 Nov 2026; the script refuses anything but `insider-eu-stg`). A person with a GUI can follow the same steps. Account card: [`README.md`](README.md).

## Before you start

- Load file: `data/affidea_full_v1.csv`, SHA-256 `c4cf313757cd9d6c5c325f085a46118a1f12e0d7077ea9495716a623ed6aef21`. If the hash differs, compare the values before rejecting it (a lost final newline changes the hash).
- Staging needs the private network (VPN). Without it the connection times out.
- Four Locations, resolved by name: Čavka, Kalajžić, Sv. Rok, Vita. Step 0 must show all four.
- 16 rows on repeated ids are not loaded (`data/affidea_full_v1_discarded_rows.csv`); `04` is compared with the clinic file minus those rows.
- **163,105 rows: Beekeeper exports stop at 50,000.** Run `04` with `tools/run_staging.sh` (psql, no limit), or ask Claude for a split export. `99` takes several minutes at this size.
- Karlo's open questions and the assumptions this build makes are in DEV-409. A different answer means a rebuild and a rerun.
- Run every file as a whole, unless the step says "one query at a time".

## Steps

| # | Do | Expect | Paste back |
|---|---|---|---|
| 0 | `SELECT current_database() AS db, s."alchemerId" AS survey, a.name AS account, (SELECT count(*) FROM location l WHERE l.account_id = a.id) AS locations, (SELECT count(*) FROM survey_response sr WHERE sr."surveyId" = s.id AND sr.visit_msg_id IS NULL) AS unlinked FROM survey s JOIN account a ON a.id = s."accountId" WHERE s."alchemerId" IN ('90540487');` | `insider-eu-stg`, `Affidea`, 4 Location(s), 1 row(s); unlinked in total close to 11,323 (prod, 25 Nov 2026) | the rows |
| 1 | `sql/01_before_import.sql` | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_affidea_full / 0` | the row, or the error |
| 2 | Import `data/affidea_full_v1.csv` into the **existing** `stg_affidea_full`. Every column as TEXT, header on, empty = NULL, trim whitespace **off** | — | any warning |
| 3 | The count query at the bottom of `01` | 163,105 / 126,684 / 36,408 / 7 / 6 (total / platform / legacy_invite / legacy_visit / legacy_raw) | the row |
| 4 | `sql/02_load.sql` | `AFFIDEA_LEGACY_V1`, legacy_visits 36,415, legacy_invites 36,408, linked_responses **7,628**, source_rows_stored 163,105. `platform_rows_linked` can be below 126,684 (older copy) | the row, or the error |
| 5 | `sql/03_validation.sql`, **one query at a time** | Query 1: source_rows 163,105, legacy_visits 36,415, legacy_invites 36,408, linked 7,628, deleted_linked 0, existing_patients_changed 0, legacy_rows_without_patient 0. Query 2: 2023 Q2 – 2024 Q3: sent 36,408, delivered 35,303, responses 7,628 (21.6 %) | all results |
| 6 | `sql/04_export_original_csv.sql` as CSV | 163,105 rows, identical to the clinic file minus the 16 discarded rows | saved in `out/` (git-ignored) |
| 7 | `sql/99_rollback.sql` | source_rows_removed 163,105, legacy_visits_removed 36,415, remaining_batches 0 | the row |
| 8 | Steps 1–4 again, so the load stays on staging for ops | same as above | the 02 row |

## If something fails

- `Survey 90540487 found 0 times`: wrong database (UK?) or staging lacks the Account. Stop.
- `unlinked legacy responses found N, expected 7,628`: staging lacks some responses (older copy). Claude renders a staging-specific SQL with the real number. Don't edit the SQL by hand.
- `legacy rows that already exist as Visit Msgs`: the staging copy has Visit Msgs the prod export didn't. Stop and compare.
- `raw_visit_date was converted` / `raw_phone was converted`: a GUI typed a column. Drop `stg_affidea_full`, run `01` again, re-import as TEXT.
- Any other error: `ROLLBACK;` and paste the message.

## Afterwards

Claude writes the run log in `runs/<date>_staging.md`.
