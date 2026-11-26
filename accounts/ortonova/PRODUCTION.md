# Production run: Orto-Nova legacy import

> **Draft, 26 Nov 2026. Not run yet** (DEV-410). Waiting for: Ana's check (DEV-412), Karlo's answers (DEV-408), the ops sign-off (COPS task) and the rollback decision below. If an answer changes the build, the numbers below change with it.

Same flow as the six Accounts of 23 Nov 2026 (DEV-185). Worked examples: `docs/production-run-2026-11-23.md` (run sheet, rules, Beekeeper lessons) and `accounts/kvaternik/runs/2026-11-23_production.md`. Plan: [`docs/plans/2026-11-24_bolnica-colic-and-next.md`](../../docs/plans/2026-11-24_bolnica-colic-and-next.md).

## Before production

1. **Apply Karlo's answers** (DEV-408: three Surveys, column `p`, legacy rows without dates). If he wants only the HR Survey linked, `extra_alchemer_ids` goes and linked responses drop. Any change means rebuild, re-render, mock test and staging rerun.
2. **Freeze the scripts:** copy `sql/` to `production/DEV-375/2_ortonova/` and add the hashes to `production/DEV-375/SHA256SUMS`. Ana runs only the frozen copies.
3. **Preflight:** build `out/00_preflight.sql` with `tools/preprod/build_preflight.py` (point it at `production/DEV-375`; it must check all three Surveys).
4. **Refresh from the prod replica on the day:** export `db_unlinked_responses_<date>.csv` and `db_visit_msg_ids_<date>.csv`, rebuild the load file, compare its SHA-256 with the one below. If it differs, compare the values and write down why.
5. Re-check the schema facts in `docs/database-facts.md` (link trigger, identity columns, foreign keys).

## Go / no-go

- [ ] DEV-412 done (Ana) and ops sign-off in the COPS task (Karlo).
- [ ] Every DEV-408 answer applied; the staging run after it passed. Run log in `runs/`.
- [ ] A dev has reviewed PR #11; it is merged right before the production session.
- [ ] A recent prod backup / point-in-time recovery is available.
- [ ] **Rollback decision written down** (see "Rollback" below).
- [ ] Ana gives Claude explicit permission for each production write, or runs it herself.
- [ ] Input hashes (25 Nov 2026; update if step 4 rebuilt the load file):
  - `Pacijenti_Joined_OrtoNova.csv` `422bfed8670c5e8665da7c15c6e8859e5847433aa42e387e54d85f1d675a490c`
  - `Survey_responses_OrtoNova.csv` `91590c06f88d2ae610ad1e3f45b0820763e8af7024443ccddcf4a72bc6df626b`
  - `data/ortonova_full_v1.csv` `fda0bc45719ed589d8ead09ff32cb8e706c284a37c861c026bf65367d4889416`

## Steps (EU prod `insider-prod`, Beekeeper)

Expected numbers are **real**: from the load file, the mock test and the staging run of 25 Nov 2026 (batch 13112). Prod baseline on the replica, 26 Nov 2026: 2,403 unlinked Survey Responses on the three Surveys (same as the build input), 9,788 platform Visit Msgs, no `ORTONOVA_LEGACY_V1` batch.

| # | Do | Expected | If not |
|---|---|---|---|
| 0 | `00_preflight.sql` (read-only; Claude on the replica or Ana on prod) | `insider-prod`, Account `Orto-Nova`, 1 Location, three Surveys found, every `*_present` / `*_already_*` 0, unlinked legacy responses 1,995, trigger unchanged | **Stop.** Wrong database (EU vs UK) or prod changed |
| 1 | `01_before_import.sql` | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_ortonova_full / 0` | `ROLLBACK;`, send the error |
| 2 | Beekeeper import of `data/ortonova_full_v1.csv` into the **existing** `stg_ortonova_full`, every column TEXT. **Untick "Automatically Trim Whitespace"** | — | Drop the table, run `01` again |
| 3 | Count check (bottom of `01`), then the space check | 35,557 / 9,718 / 25,839 / 0 / 0. Spaces kept: `raw_comment` 710, `raw_lead_source` 6 | Drop, `01`, re-import (trim was on) |
| 4 | Check the GUI's commit mode, then `02_load.sql` (whole file). Wait for the result row (about 1 minute on staging) | `ORTONOVA_LEGACY_V1`, legacy_visits 25,839, legacy_invites 25,839, **linked_responses 1,995**, **platform_rows_linked 9,718** (staging 8,701: older copy), source_rows_stored 35,557, new Patients ≤ 25,663 | Nothing saved (one transaction). `ROLLBACK;`, send the error |
| 5 | Claude: `03` query 1 on the replica | Same numbers; deleted_linked 0, existing_patients_changed 0, legacy_rows_without_patient 0, still unlinked 408 | Stop the session (run sheet rule 3) |
| 6 | `04_export_original_csv.sql` → CSV; Claude compares by value with `Pacijenti_Joined_OrtoNova.csv` | Identical, 35,557 rows (under Beekeeper's 50,000-row export limit) | Investigate |
| 7 | `DROP TABLE public.stg_ortonova_full;` | Claude confirms on the replica | — |
| 8 | Clinicdash (prod): legacy months visible from Nov 2022, on all three Surveys; the platform period unchanged | Zoho per year: 2022 168 / NPS 86.3, 2023 835 / 86.1, 2024 812 / 83.9, 2025 174 / 89.7. **Check NPS here**: on staging it was wrong (staging data) | Investigate |

Space check for step 3 (one result set):

```sql
SELECT count(*) FILTER (WHERE raw_comment <> btrim(raw_comment, ' ')) AS comment_spaces,
       count(*) FILTER (WHERE raw_lead_source <> btrim(raw_lead_source, ' ')) AS lead_source_spaces
FROM public.stg_ortonova_full;
```

**Beekeeper risks checked on the load file (26 Nov 2026):** 716 values have edge spaces (raw columns only, `raw_comment` and `raw_lead_source`); with trimming on, Patients would not change, but the `04` export would differ. No 64 KB chunk edge falls inside a character.

## Rollback

`99_rollback.sql` deletes only this load's rows, but it is slow: `legacy_source_row` (`visit_msg_id`, `patient_visit_id`, `patient_id`) and `legacy_invite_map.visit_msg_id` have no index. On staging it ran more than an hour and did not finish (estimate about 2.5 hours). It locks `patient` / `patient_visit` while it runs, which on prod means the app waits that long.

**Ana decides before go:**
- add the indexes first (dev ticket; then rerun the rollback on staging to time it), or
- accept the risk as on 23 Nov (rollback only if existing data changed, run sheet rule 3), and run it out of hours if needed.

## After

- Write `runs/<date>_production.md` and mark this file "done, see run log".
- Claude compares prod with Zoho by year and Survey, as in the 25 Nov comparison.
- With the ops sign-off on prod: tell the CSM that legacy sent, delivered and response rate are **estimated**; responses and NPS are real.
- After the sign-off: delete the local clinic files, load file and exports (`data/`, `out/`).
