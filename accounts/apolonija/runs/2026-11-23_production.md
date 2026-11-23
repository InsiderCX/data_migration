# Stomatološka poliklinika Apolonija production run, 23 Nov 2026

Run log of the `APOLONIJA_LEGACY_V1` load on **EU production** (`insider-prod`), part of DEV-185 (all six legacy Accounts in one session). Ana ran every step in Beekeeper Studio. Claude read only the prod replica (Zamera) and the files Ana exported. Scripts: the frozen copies in `production/DEV-185/`, checked against `SHA256SUMS` before each copy. Session run sheet: `docs/production-run-2026-11-23.md`.

- Load file: `data/apolonija_full_v1.csv`, SHA-256 `b4781a162ca29fadf639c6243574fb6a0f1184a4746823badf785bc174feeaf5` (same as the Account card and the 17 Nov staging run).
- Ops sign-off of staging: COPS-333 (Karlo, "Ready for production - all accounts").

## Steps

| # | Step | Who | Result | Check |
|---|---|---|---|---|
| 0 | `00_preflight.sql` (read-only) | Ana | `insider-prod`, Account ok, 1 Location; 10,516 new Visit Msg ids, none present; 1,515 unlinked legacy Survey Responses = expected; trigger unchanged | ✓ |
| 1 | `01_before_import.sql` | Ana | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_apolonija_full / 0` | ✓ |
| 2 | GUI import of `data/apolonija_full_v1.csv` (Beekeeper) | Ana | — | — |
| 3 | Count check | Ana | 67,895 / 11,420 / 10,516 / 20,383 / 25,576 (total / platform / invite / visit / raw) | ✓ |
| 3b | Space check (were edge spaces kept?) | Ana | `link_sguid` 44 / `raw_lead_source` 128 ✓ (the 44 survey link ids that start with a space survived) | ✓ |
| 4 | `02_load.sql` | Ana | `APOLONIJA_LEGACY_V1`, batch **13487**, new Patients 3,290, 30,899 / 10,516 / **1,515** / 11,420 / 67,895 (legacy visits / invites / linked / platform rows linked / source rows) | ✓ |
| 5 | `03_validation.sql`, query 1 | Claude on the replica | Same numbers as step 4; see Results | ✓ |
| 6 | `04_export_original_csv.sql`, compared by value with the clinic file | Ana, Claude | Beekeeper exported only the first 50,000 rows; rows 50,001–67,895 exported again with `OFFSET 50000`. Identical except 3 cells: see Problems | ✓ after the fix |
| 7 | `DROP TABLE public.stg_apolonija_full;` | Ana | Replica: table gone | ✓ |

## Results (prod replica, after the load)

| Check | Value | Expected |
|---|---|---|
| Source rows stored | 67,895 | 67,895 ✓ |
| Legacy Patient Visits / Survey Invites | 30,899 / 10,516 | ✓ |
| Legacy Survey Responses linked | 1,515 | 1,515 ✓ |
| Platform rows linked | 11,420 | = platform rows ✓ |
| New Patients | 3,290 | ≤ 3,301 on staging ✓ (Patients created since the staging copy are reused) |
| Existing Patients changed | **0** | 0 ✓ |
| Legacy rows without a Patient | **0** | 0 ✓ |
| Deleted Survey Responses linked | **0** | 0 ✓ |
| Survey Responses still unlinked | 51 (same as staging 17 Nov) | not part of this load |

**Legacy NPS (real):** 1,515 scored responses, 1,342 promoters, 76 detractors, **NPS 83.6**.
**Legacy send dates (estimated):** 16 Nov 2022 – 18 Oct 2024. Sent, delivered and response rate for the legacy period are estimates; responses and NPS are real.

**Clinicdash numbers (prod replica, 23 Nov 2026):** every month before November 2026 equals the 17 Nov projection that ops signed off in COPS-333; November 2026 differs only by Survey Responses that came in after 17 Nov.

## Problems and fixes

**Three letters split by the GUI import.** Beekeeper reads the file in 64 KB chunks. Where a chunk edge fell inside a two-byte letter (š, ć), it stored two U+FFFD replacement characters. The 12 MB load file has exactly 3 such edges, and they are exactly the 3 broken cells: source rows 6410 (`doctor`), 27587 and 54045 (`lead_source`). Platform effect: the doctor name on 1 legacy Patient Visit (id 2323869). The two `lead_source` rows belong to existing Patients, which the load does not change. `03` cannot see this (it counts, it does not compare text). The other five load files have no chunk edge inside a letter.

- `out/05_fix_split_characters.sql` (git-ignored; holds a doctor name). One transaction, checks before and after. Mock-tested (pass 3 / 1 / 0 / 0, second run refuses). Ana ran it on prod: **3 / 1 / 0 / 0**. Replica: the 3 cells now equal the clinic file, visit 2323869 has the correct doctor name (the same spelling as 2,169 other Apolonija visits), and no U+FFFD is left in any of the six Accounts' source rows.

## Identifiers on production (to find or undo this load)

- Load code `APOLONIJA_LEGACY_V1`, `legacy_sending_batch.loaded_at` = 2026-11-23 10:58:38 UTC
- Mock sending batch `visit_msg_sending_batch.id = 13487` (`trigger = 'legacy_import'`), Account 39, Alchemer survey 90492576
- Patients created by the load: `patient.created = loaded_at` (3,290)
- Source rows: `legacy_source_row.source_file = 'Pacijenti_JOINED_Apolonija.csv'`
- Undo (data only): `production/DEV-185/6_apolonija/99_rollback.sql` (slow; locks `patient` / `patient_visit` while it runs)

## Still open

- [ ] Ops validate production and sign off: COPS-338 (Karlo)
- [ ] With COPS-338: tell the CSM that legacy message figures (sent, delivered, response rate) are estimates; responses and NPS are real
- [ ] After COPS-338: delete the local clinic files, load file and exports (`data/`, `out/`, `~/Downloads/export_prod_*`)
