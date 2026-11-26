# Orto-Nova: staging run

Runbook for **EU staging** (DEV-408). Claude runs it with `bash tools/run_staging.sh ortonova Pacijenti_Joined_OrtoNova.csv` (Ana's permission for staging only, 25 Nov 2026; the script refuses anything but `insider-eu-stg`). A person with a GUI can follow the same steps. Account card: [`README.md`](README.md).

## Before you start

- Load file: `data/ortonova_full_v1.csv`, SHA-256 `fda0bc45719ed589d8ead09ff32cb8e706c284a37c861c026bf65367d4889416`. If the hash differs, compare the values before rejecting it (a lost final newline changes the hash).
- Staging needs the private network (VPN). Without it the connection times out.
- **Three Surveys** (`extra_alchemer_ids`): 90492015 resolves the Account; responses on 90509784 (IT) and 90509787 (SLO) are linked too. Step 0 must show all three.
- 25,180 legacy rows have no phone: one new Patient per row.
- Karlo's open questions and the assumptions this build makes are in DEV-408. A different answer means a rebuild and a rerun.
- Run every file as a whole, unless the step says "one query at a time".

## Steps

| # | Do | Expect | Paste back |
|---|---|---|---|
| 0 | `SELECT current_database() AS db, s."alchemerId" AS survey, a.name AS account, (SELECT count(*) FROM location l WHERE l.account_id = a.id) AS locations, (SELECT count(*) FROM survey_response sr WHERE sr."surveyId" = s.id AND sr.visit_msg_id IS NULL) AS unlinked FROM survey s JOIN account a ON a.id = s."accountId" WHERE s."alchemerId" IN ('90492015', '90509784', '90509787');` | `insider-eu-stg`, `Orto-Nova`, 1 Location(s), 3 row(s); unlinked in total close to 2,403 over the three Surveys (prod, 25 Nov 2026); a few may be missing on the 28 Sep copy | the rows |
| 1 | `sql/01_before_import.sql` | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_ortonova_full / 0` | the row, or the error |
| 2 | Import `data/ortonova_full_v1.csv` into the **existing** `stg_ortonova_full`. Every column as TEXT, header on, empty = NULL, trim whitespace **off** | — | any warning |
| 3 | The count query at the bottom of `01` | 35,557 / 9,718 / 25,839 / 0 / 0 (total / platform / legacy_invite / legacy_visit / legacy_raw) | the row |
| 4 | `sql/02_load.sql` | `ORTONOVA_LEGACY_V1`, legacy_visits 25,839, legacy_invites 25,839, linked_responses **1,995**, source_rows_stored 35,557. `platform_rows_linked` can be below 9,718 (older copy) | the row, or the error |
| 5 | `sql/03_validation.sql`, **one query at a time** | Query 1: source_rows 35,557, legacy_visits 25,839, legacy_invites 25,839, linked 1,995, deleted_linked 0, existing_patients_changed 0, legacy_rows_without_patient 0. Query 2: 2022 Q4 – 2025 Q1: sent 25,839, delivered 24,368, responses 1,995 (8.2 %) | all results |
| 6 | `sql/04_export_original_csv.sql` as CSV | 35,557 rows, identical to the clinic file | saved in `out/` (git-ignored) |
| 7 | `sql/99_rollback.sql` | source_rows_removed 35,557, legacy_visits_removed 25,839, remaining_batches 0 | the row |
| 8 | Steps 1–4 again, so the load stays on staging for ops | same as above | the 02 row |

## If something fails

- `Survey 90492015 found 0 times`: wrong database (UK?) or staging lacks the Account. Stop.
- `unlinked legacy responses found N, expected 1,995`: staging lacks some responses (older copy). Claude renders a staging-specific SQL with the real number. Don't edit the SQL by hand.
- `legacy rows that already exist as Visit Msgs`: the staging copy has Visit Msgs the prod export didn't. Stop and compare.
- `raw_visit_date was converted` / `raw_phone was converted`: a GUI typed a column. Drop `stg_ortonova_full`, run `01` again, re-import as TEXT.
- Any other error: `ROLLBACK;` and paste the message.

## Afterwards

Claude writes the run log in `runs/<date>_staging.md`.
