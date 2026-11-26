# Production run: Bolnica Colić legacy import

> **Draft, 26 Nov 2026. Not run yet** (DEV-378). Waiting for: Ana's check (DEV-412), Karlo's answers (DEV-377) and the ops sign-off (COPS task). If an answer changes the build, the numbers below change with it.

Same flow as the six Accounts of 23 Nov 2026 (DEV-185). Worked examples: `docs/production-run-2026-11-23.md` (run sheet, rules, Beekeeper lessons) and `accounts/kvaternik/runs/2026-11-23_production.md`. Plan: [`docs/plans/2026-11-24_bolnica-colic-and-next.md`](../../docs/plans/2026-11-24_bolnica-colic-and-next.md).

## Before production

1. **Apply Karlo's answers** (DEV-377: age, empty columns, gender, whether the file holds every invite). An answer that changes the load means a config change, rebuild, re-render, mock test and staging rerun.
2. **Freeze the scripts:** copy `sql/` to `production/DEV-375/1_bolnicacolic/` and add the hashes to `production/DEV-375/SHA256SUMS`. Ana runs only the frozen copies.
3. **Preflight:** build `out/00_preflight.sql` with `tools/preprod/build_preflight.py` (point it at `production/DEV-375`).
4. **Refresh from the prod replica on the day:** export `db_unlinked_responses_<date>.csv` and `db_visit_msg_ids_<date>.csv`, rebuild the load file, compare its SHA-256 with the one below. If it differs, compare the values and write down why.
5. Re-check the schema facts in `docs/database-facts.md` (link trigger, identity columns, foreign keys).

## Go / no-go

- [ ] DEV-412 done (Ana) and ops sign-off in the COPS task (Karlo).
- [ ] Every DEV-377 answer applied; the staging run after it passed. Run log in `runs/`.
- [ ] A dev has reviewed PR #11; it is merged right before the production session.
- [ ] A recent prod backup / point-in-time recovery is available.
- [ ] Rollback decision written down (see "Rollback" below).
- [ ] Ana gives Claude explicit permission for each production write, or runs it herself.
- [ ] Input hashes (25 Nov 2026; update if step 4 rebuilt the load file):
  - `Pacijenti_Joined_BolnicaColic.csv` `59719773733c7b8a95d16efe4a532f3a29d5ee22a207410ad8f617ad3f111f31`
  - `Survey_responses_DrColic.csv` `161b78690461690c79c52026059e7b2b3928ffcd2ab732ce2ffd8548ab13013d`
  - `data/bolnicacolic_full_v1.csv` `3ab8932fa8aa22b6b574db01b5c8a6eba5f579ca5ac41201311d4cb64102cc6e`

## Steps (EU prod `insider-prod`, Beekeeper)

Expected numbers are **real**: from the load file, the mock test and the staging run of 25 Nov 2026 (batch 13111). Prod baseline on the replica, 26 Nov 2026: 746 unlinked Survey Responses (same as the build input), 988 platform Visit Msgs (from 11 Nov 2026, not in the clinic file), no `BOLNICACOLIC_LEGACY_V1` batch.

| # | Do | Expected | If not |
|---|---|---|---|
| 0 | `00_preflight.sql` (read-only; Claude on the replica or Ana on prod) | `insider-prod`, Account `Bolnica Colić`, 1 Location, every `*_present` / `*_already_*` 0, unlinked legacy responses 720, trigger unchanged | **Stop.** Wrong database (EU vs UK) or prod changed |
| 1 | `01_before_import.sql` | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_bolnicacolic_full / 0` | `ROLLBACK;`, send the error |
| 2 | Beekeeper import of `data/bolnicacolic_full_v1.csv` into the **existing** `stg_bolnicacolic_full`, every column TEXT. **Untick "Automatically Trim Whitespace"** | — | Drop the table, run `01` again |
| 3 | Count check (bottom of `01`) | 2,452 / 0 / 2,443 / 9 / 0 (total / platform / invite / visit / raw) | Drop, `01`, re-import |
| 4 | Check the GUI's commit mode, then `02_load.sql` (whole file). Wait for the result row | `BOLNICACOLIC_LEGACY_V1`, legacy_visits 2,452, legacy_invites 2,443, **linked_responses 720**, platform_rows_linked 0, source_rows_stored 2,452, new Patients ≤ 2,419 | Nothing saved (one transaction). `ROLLBACK;`, send the error |
| 5 | Claude: `03` query 1 on the replica | Same numbers; deleted_linked 0, existing_patients_changed 0, legacy_rows_without_patient 0, still unlinked 26 | Stop the session (run sheet rule 3) |
| 6 | `04_export_original_csv.sql` → CSV; Claude compares by value with `Pacijenti_Joined_BolnicaColic.csv` | Identical, 2,452 rows | Investigate |
| 7 | `DROP TABLE public.stg_bolnicacolic_full;` | Claude confirms on the replica | — |
| 8 | Clinicdash (prod): legacy months visible from Feb 2023; November 2026 unchanged | Zoho per year: 2023 166 / NPS 91.0, 2024 202 / 88.6, 2025 175 / 73.1 (`docs/validation/2026-11-25_alchemer_zoho_dev375.md`) | Investigate |

**Beekeeper risks checked on the load file (26 Nov 2026):** no value has leading or trailing spaces, and no 64 KB chunk edge falls inside a character. The two problems of 23 Nov cannot happen with this file.

## Rollback

`99_rollback.sql` deletes only this load's rows. Staging: **14 minutes** for 2,452 rows. It locks `patient` / `patient_visit` while it runs. Short enough to keep as the plan if `03` or `04` fails.

## After

- Write `runs/<date>_production.md` and mark this file "done, see run log".
- With the ops sign-off on prod: tell the CSM that legacy sent, delivered and response rate are **estimated**; responses and NPS are real.
- After the sign-off: delete the local clinic files, load file and exports (`data/`, `out/`).
