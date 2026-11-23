# Production run sheet: legacy imports, Mon 23 Nov 2026 (DEV-185)

Ana runs every step in her GUI SQL client on **EU prod (`insider-prod`)**. Claude only reads the prod replica, or reads what Ana pastes. Scripts: `production/DEV-185/<n>_<account>/` only (checked against `SHA256SUMS` on 23 Nov 2026). Preflights: `accounts/<account>/out/00_preflight.sql` (read-only, git-ignored).

Order: Optical Express → Kvaternik → Arcadia → Videntis → Mazalin → Apolonija. Clinicdash: one pass at the end, for all six.

## Rules

1. **Import or count check fails** (wrong types, wrong rows): `DROP TABLE` the staging table, run `01` again, re-import. Continue.
2. **`02` refuses** (a guard fails; nothing is written): skip this Account, continue with the next. Fixed later on its own branch.
3. **After the commit, `03` or `04` fails**: **stop the whole session.** `99_rollback.sql` only if existing data changed (`existing_patients_changed > 0`). Otherwise keep the load and investigate.
4. The next Account starts only after Claude has checked this Account's `03`, from the replica or from Ana's paste.
5. Before `02`: check that the GUI's commit mode is auto-commit, or commit by hand. No result row from `02` = not finished or not committed.
6. Known risk (accepted 23 Nov): `99` is slow. Staging times: Optical 17 min, Kvaternik 2 min, Arcadia 10–30 min, Videntis 5 min, Mazalin 8 min, Apolonija 35–68 min. It locks `patient` / `patient_visit` while it runs.

## Steps per Account

| # | Do | Pass when |
|---|---|---|
| 0 | `00_preflight.sql` (Claude on the replica, or Ana on prod; read-only) | `insider-prod`, surveys_found 1, account_ok true, locations as below, every `*_present` / `*_already_*` = 0, unlinked_legacy_responses = expected_unlinked, trigger_same_as_01 true |
| 1 | `01_before_import.sql` | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_<account>_full / 0` |
| 2 | GUI import of the load file into the **existing** `stg_<account>_full`, every column TEXT | — |
| 3 | Count query (commented at the bottom of `01`) | Counts as below |
| 4 | `02_load.sql` (whole file) | Result row as below |
| 5 | `03_validation.sql`, query 1 | Same numbers as step 4; `deleted_linked` 0, `existing_patients_changed` 0, `legacy_rows_without_patient` 0 |
| 6 | `04_export_original_csv.sql` → CSV (comma, header, UTF-8); Claude compares by value with the clinic file | Identical, same rows as `source_rows` |
| 7 | `DROP TABLE public.stg_<account>_full;` | Claude confirms on the replica |

## Expected numbers

Real numbers from the load files, the mock tests and the staging runs of 17 Nov 2026. `new_patients` can be lower on prod (Patients created since the staging copy are reused), and the `02` guards accept that.

| Account | Code | Locations | Count check (total / platform / invite / visit / raw) | `02`: legacy_visits / legacy_invites / linked_responses / platform_rows_linked / source_rows | New Patients (staging) |
|---|---|---|---|---|---|
| 1 Optical Express | `OPTICALEXPRESS_LEGACY_V1` | 1 | 7,903 / 3,850 / 4,051 / 2 / 0 | 4,053 / 4,051 / **634** / 3,850 / 7,903 | 3,961 |
| 2 Kvaternik | `KVATERNIK_LEGACY_V1` | 2 | 8,407 / 7,680 / 727 / 0 / 0 | 727 / 727 / **132** / 7,680 / 8,407 | 675 |
| 3 Arcadia | `ARCADIA_LEGACY_V1` | 1 | 13,306 / 6,497 / 5,097 / 1,712 / 0 | 6,809 / 5,097 / **1,072** / 6,497 / 13,306 | 6,623 |
| 4 Videntis | `VIDENTIS_LEGACY_V1` | 1 | 16,416 / 5,483 / 4,371 / 6,562 / 0 | 10,933 / 4,371 / **504** / 5,483 / 16,416 | 2,317 |
| 5 Mazalin | `MAZALIN_LEGACY_V1` | 1 | 30,481 / 28,028 / 2,453 / 0 / 0 | 2,453 / 2,453 / **437** / 28,028 / 30,481 | 1,083 |
| 6 Apolonija | `APOLONIJA_LEGACY_V1` | 1 | 67,895 / 11,420 / 10,516 / 20,383 / 25,576 | 30,899 / 10,516 / **1,515** / 11,420 / 67,895 | 3,301 |

`platform_rows_linked` was lower on staging (older copy). On prod it must equal the platform count.

## Results (filled in during the run)

| Account | 0 preflight | 3 counts | 4 `02` result | 5 `03` | 6 `04` | 7 dropped | Time |
|---|---|---|---|---|---|---|---|
| Optical Express | skipped (Ana); replica checks OK | 7903 / 3850 / 4051 / 2 / 0 ✓ | batch 13482, new Patients 3,959, 4053 / 4051 / 634 / 3850 / 7903 ✓ (09:47 UTC) | replica ✓: 0 changed, 0 without Patient, 0 Deleted linked, still unlinked 49 | ✓ with note (Ana, 23 Nov): 7,903 rows, identical except 23 names whose trailing space the GUI import trimmed (see note 1); fixed with `05_fix_trailing_spaces.sql` → identical ✓ | ✓ (replica) | |
| Kvaternik | Ana on prod ✓ (unlinked 132 = expected) | 8407 / 7680 / 727 / 0 / 0 ✓; spaces 9 / 6 ✓ (trim off, after one re-import) | batch 13483, new Patients 675, 727 / 727 / 132 / 7680 / 8407 ✓ (10:14 UTC) | replica ✓: 0 changed, 0 without Patient, 0 Deleted linked, still unlinked 5 | identical, 8,407 rows ✓ | ✓ (replica 10:17 UTC) | |
| Arcadia | Ana on prod ✓ (unlinked 1072 = expected) | 13306 / 6497 / 5097 / 1712 / 0 ✓; spaces 61 / 61 ✓ | batch 13484, new Patients 6,613, 6809 / 5097 / 1072 / 6497 / 13306 ✓ (10:19 UTC) | replica ✓: 0 changed, 0 without Patient, 0 Deleted linked, still unlinked 20 | identical, 13,306 rows (clinic file minus 289 discarded) ✓ | ✓ (replica) | |
| Videntis | Ana on prod ✓ (unlinked 504 = expected) | 16416 / 5483 / 4371 / 6562 / 0 ✓ (no 3b) | batch 13485, new Patients 2,307, 10933 / 4371 / 504 / 5483 / 16416 ✓ (10:27 UTC) | replica ✓: 0 changed, 0 without Patient, 0 Deleted linked, still unlinked 115 (= staging) | identical, 16,416 rows ✓ | ✓ (replica) | |
| Mazalin | Ana on prod ✓ (unlinked 437 = expected) | 30481 / 28028 / 2453 / 0 / 0 ✓; spaces 1190 / 488 / 76 ✓ | batch 13486, new Patients 1,056, 2453 / 2453 / 437 / 28028 / 30481 ✓ (10:33 UTC) | replica ✓: 0 changed, 0 without Patient, 0 Deleted linked, still unlinked 34 (= staging) | identical, 30,481 rows ✓ | ✓ (replica) | |
| Apolonija | Ana on prod ✓ (unlinked 1515 = expected) | 67895 / 11420 / 10516 / 20383 / 25576 ✓; spaces link_sguid 44 / lead_source 128 ✓ | batch 13487, new Patients 3,290, 30899 / 10516 / 1515 / 11420 / 67895 ✓ (10:58 UTC) | replica ✓: 0 changed, 0 without Patient, 0 Deleted linked, 44 leading-space sguids linked, still unlinked 51 (= staging 17 Nov) | 67,895 rows (Beekeeper export cut at 50,000; part 2 with `OFFSET 50000`): identical except 3 cells, each one letter stored as two U+FFFD (note 2); fixed with `05_fix_split_characters.sql` (3 / 1 / 0 / 0); replica: the 3 cells now equal the clinic file, so all 67,895 rows identical ✓ | ✓ (replica) | |

### Notes

1. **GUI import trims whitespace (found at Optical Express step 6).** The export matched the clinic file except 21 `first_name` and 2 `last_name` values whose trailing space was trimmed by the GUI import into `stg_opticalexpress_full` (the load file has the spaces; `02` copies raw names unchanged; replica: 0 stored names end in a space). Patients are not affected: `02` trims names before creating Patients. Only the raw copy in `legacy_source_row` lost the spaces. Ana accepted step 6 as passed. From Kvaternik on: untick "Automatically Trim Whitespace" on Beekeeper's Choose file screen (it was ticked; the first Kvaternik import showed 0 / 0 spaces and was dropped and re-imported). Kvaternik/Arcadia/Videntis/Mazalin have edge spaces only in raw columns (names, Mazalin `raw_procedure`), so at worst the same `04` note. **Apolonija:** 44 `link_sguid` values start with a space and `02` links on them exactly; before its `02`, Claude adds a count check that the 44 survived the import. Ana chose to restore the 23 Optical Express trailing spaces: `accounts/opticalexpress/out/05_fix_trailing_spaces.sql` (no names in it, values matched by md5; one transaction, guards before and after; mock-tested on all 7,903 rows: pass 23 / 0, second run refuses; its before-checks pass on the replica). Ana ran it on prod: 23 / 0. Replica: all 23 values equal the clinic file (md5), so all 7,903 rows are identical.

2. **Beekeeper import split 3 characters (Apolonija only).** Beekeeper reads the CSV in 64 KB chunks; where a chunk edge fell inside a two-byte character (š, ć) it stored two U+FFFD replacement characters instead. The load file (12 MB) has exactly 3 such edges, and these are exactly the 3 broken cells on prod: `legacy_source_row` rows 6410 (`doctor`), 27587 and 54045 (`lead_source`). Platform effect: 1 legacy Patient Visit (id 2323869) has the broken doctor name; the 2 lead_source rows belong to existing Patients, which the load does not change, so 0 Patients are affected. The other five load files have no chunk edge inside a character, so their loads are clean (their exports matched exactly). The `03` checks cannot see this. Ana chose to fix it: `accounts/apolonija/out/05_fix_split_characters.sql` (git-ignored; one transaction, guards before and after; mock-tested: pass 3/1/0/0, second run refuses and changes nothing; its before-checks pass on the replica). Ana ran it on prod: 3 / 1 / 0 / 0. Replica: the 3 cells equal the clinic file (md5), visit 2323869 doctor correct, 0 U+FFFD left in the six Accounts' source rows.

## After all six

1. Clinicdash (prod), each Account: the legacy months are visible in NPS Trends; last month's NPS is unchanged.
2. Claude writes `accounts/<account>/runs/2026-11-23_production.md` per Account and marks each `PRODUCTION.md` "done, see run log".
3. Linear: Claude drafts the DEV-185 comment; Ana posts it, sets DEV-185 Done and unblocks DEV-319.
4. Keep local `accounts/*/data/` and `out/` until ops sign off on prod (COPS-338), then delete them.
5. With COPS-338: tell the CSMs that legacy message figures (sent, delivered, response rate) are **estimates**, while responses and NPS are real.
