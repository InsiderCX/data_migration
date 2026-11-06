# Production run: Optical Express legacy import

> **Not started. Production waits for the ops sign-off** (COPS ticket from DEV-232, item C1) and for the answers that change the load (A1 link?, A2 repeated ids, A3 missing invites, A6 other rows). Until then nothing is written to production.

Same flow as Videntis, Arcadia and Apolonija; SIE's 28 Oct 2026 run log (`accounts/sie/runs/2026-10-28_production.md`) is the worked example. Plan: [`docs/plans/2026-11-06_kvaternik-mazalin-opticalexpress.md`](../../docs/plans/2026-11-06_kvaternik-mazalin-opticalexpress.md).

## Before production

1. **Apply the ops answers.** Each answer that changes the load is a config change, a rebuild, a re-render and a mock test, then a staging rerun (about half a day):
   - A1 = link: `link_responses` true in `sql_config.json`; the Visit Msgs of uuid legacy rows (Kvaternik, Mazalin) take the original uuid as id; Optical gets `legacy_invite_map` rows. Expected linked responses: 634.
   - A2 / A3 / A6 (Optical, Kvaternik): change `raw_only_ids` / the clinic file as ops decide.
2. **Refresh from the prod replica on the day:** export `db_unlinked_responses_<date>.csv` and `db_visit_msg_ids_<date>.csv`, rebuild the load file, compare its SHA-256 with the staging one. New platform invites since 6 Nov 2026 must not change the legacy rows; if the hash differs, compare the values and write down why.
3. Re-check the schema facts in `docs/database-facts.md` (trigger, identity columns, foreign keys incl. `fk_country_code`).

## Go / no-go

- [ ] Ops sign-off for Optical Express in the COPS ticket (C1), and every A item answered.
- [ ] Staging rerun after the answers passed (load, validation, export identical, rollback, reload). Run log in `runs/`.
- [ ] A dev has reviewed the PR (DEV-232); it is merged right before the production session.
- [ ] A recent prod backup / point-in-time recovery is available.
- [ ] Ana gives Claude explicit permission for each production write, or runs it herself.
- [ ] Input hashes (6 Nov 2026; update if step 2 rebuilt the load file):
  - `Pacijenti_joined_OpticalExpress.csv` `802a8e335b31f236ec8adbbde0567a34193fb065e4bb6aabdf1a5dc17be43c8a`
  - `Surevy_responses_OpticalExpress.csv` `46e3a445a9305287764b90e3ebce31cb2077bd77e17bd8e1cc002ce0fb86dfc6`
  - `data/opticalexpress_full_v1.csv` `9ade17860b16411f514b61c1b6fc8e796e5370b80cce808ad4c5d2a311099495`

## Steps (EU prod `insider-prod`)

Expected numbers are for the staging load of 6 Nov 2026 (append only, no linking). If the ops answers change the load, `sql_config.json` and these numbers change with it.

| # | Do | Expected | If not |
|---|---|---|---|
| 1 | `SELECT current_database(), (SELECT name FROM account a JOIN survey s ON s."accountId" = a.id WHERE s."alchemerId" = '90535032') AS account;` | `insider-prod`, `Optical Express` | **Stop.** Wrong database (EU vs UK) |
| 2 | Claude: pre-flight on the replica (unlinked responses, no `OPTICALEXPRESS_LEGACY_V1` batch, trigger function md5, baseline counts) | unlinked ≈ 683, 0 legacy rows for Account 44 | Stop and compare |
| 3 | `sql/01_before_import.sql` | `… / stg_opticalexpress_full / 0` | `ROLLBACK;`, send the error |
| 4 | Import `data/opticalexpress_full_v1.csv` into the existing `stg_opticalexpress_full`, every column TEXT | — | Drop the table, run `01` again |
| 5 | Count check (bottom of `01`) | 7,931 / 3,850 / 3,966 / 2 / 113 | Re-import |
| 6 | Check the GUI's commit mode, then `sql/02_load.sql`. Wait for the result row | `OPTICALEXPRESS_LEGACY_V1`, legacy_invites 3,966, linked_responses 0 (or 634 if A1 = link), **platform_rows_linked 3,850**, source_rows_stored 7,931 | Nothing saved (one transaction). `ROLLBACK;`, send the error |
| 7 | Claude: confirm on the replica, run `03` read-only | All checks pass; existing rows unchanged | `99_rollback.sql` |
| 8 | `sql/04_export_original_csv.sql`, compare with the clinic file by value | Identical, 7,931 rows | Investigate |
| 9 | Clinicdash (prod): legacy period visible; platform period unchanged | — | `99_rollback.sql` |
| 10 | Claude: compare prod with Zoho and Alchemer as on staging (`tools/dev232/build_ops_workbook.py` with prod inputs) | Same results as the staging comparison | Investigate |
| 11 | `DROP TABLE public.stg_opticalexpress_full;` and the staging copy; delete local PII | Claude confirms on the replica | — |

`99_rollback.sql` is slow but exact: it deletes only this load's rows (staging: Kvaternik 2 min, Mazalin 7.5 min, Optical 17 min).

Write the run log in `runs/<date>_production.md`.
