# Poliklinika Mazalin production run, 23 Nov 2026

Run log of the `MAZALIN_LEGACY_V1` load on **EU production** (`insider-prod`), part of DEV-185 (all six legacy Accounts in one session). Ana ran every step in Beekeeper Studio. Claude read only the prod replica (Zamera) and the files Ana exported. Scripts: the frozen copies in `production/DEV-185/`, checked against `SHA256SUMS` before each copy. Session run sheet: `docs/production-run-2026-11-23.md`.

- Load file: `data/mazalin_full_v1.csv`, SHA-256 `1746b50ed83c3619f17d28d6a161805ec22e293b35bce039d807fffe2326d79e` (same as the Account card and the 17 Nov staging run).
- Ops sign-off of staging: COPS-333 (Karlo, "Ready for production - all accounts").

## Steps

| # | Step | Who | Result | Check |
|---|---|---|---|---|
| 0 | `00_preflight.sql` (read-only) | Ana | `insider-prod`, Account ok, 1 Location; 2,453 new Visit Msg ids, none present; 437 unlinked legacy Survey Responses = expected; trigger unchanged | ✓ |
| 1 | `01_before_import.sql` | Ana | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_mazalin_full / 0` | ✓ |
| 2 | GUI import of `data/mazalin_full_v1.csv` (Beekeeper) | Ana | — | — |
| 3 | Count check | Ana | 30,481 / 28,028 / 2,453 / 0 / 0 (total / platform / invite / visit / raw) | ✓ |
| 3b | Space check (were edge spaces kept?) | Ana | 1,190 / 488 / 76 ✓ | ✓ |
| 4 | `02_load.sql` | Ana | `MAZALIN_LEGACY_V1`, batch **13486**, new Patients 1,056, 2,453 / 2,453 / **437** / 28,028 / 30,481 (legacy visits / invites / linked / platform rows linked / source rows) | ✓ |
| 5 | `03_validation.sql`, query 1 | Claude on the replica | Same numbers as step 4; see Results | ✓ |
| 6 | `04_export_original_csv.sql`, compared by value with the clinic file | Ana, Claude | Identical, 30,481 rows | ✓ |
| 7 | `DROP TABLE public.stg_mazalin_full;` | Ana | Replica: table gone | ✓ |

## Results (prod replica, after the load)

| Check | Value | Expected |
|---|---|---|
| Source rows stored | 30,481 | 30,481 ✓ |
| Legacy Patient Visits / Survey Invites | 2,453 / 2,453 | ✓ |
| Legacy Survey Responses linked | 437 | 437 ✓ |
| Platform rows linked | 28,028 | = platform rows ✓ |
| New Patients | 1,056 | ≤ 1,083 on staging ✓ (Patients created since the staging copy are reused) |
| Existing Patients changed | **0** | 0 ✓ |
| Legacy rows without a Patient | **0** | 0 ✓ |
| Deleted Survey Responses linked | **0** | 0 ✓ |
| Survey Responses still unlinked | 34 (same as staging) | not part of this load |

**Legacy NPS (real):** 437 scored responses, 395 promoters, 22 detractors, **NPS 85.4**.
**Legacy send dates (estimated):** 12 Feb 2024 – 27 Mar 2024. Sent, delivered and response rate for the legacy period are estimates; responses and NPS are real.

**Clinicdash numbers (prod replica, 23 Nov 2026):** every month before November 2026 equals the 17 Nov projection that ops signed off in COPS-333; November 2026 differs only by Survey Responses that came in after 17 Nov.

## Identifiers on production (to find or undo this load)

- Load code `MAZALIN_LEGACY_V1`, `legacy_sending_batch.loaded_at` = 2026-11-23 10:33:33 UTC
- Mock sending batch `visit_msg_sending_batch.id = 13486` (`trigger = 'legacy_import'`), Account 24, Alchemer survey 90553181
- Patients created by the load: `patient.created = loaded_at` (1,056)
- Source rows: `legacy_source_row.source_file = 'Pacijenti_Joined_Mazalin.csv'`
- Undo (data only): `production/DEV-185/5_mazalin/99_rollback.sql` (slow; locks `patient` / `patient_visit` while it runs)

## Still open

- [ ] Ops validate production and sign off: COPS-338 (Karlo)
- [ ] With COPS-338: tell the CSM that legacy message figures (sent, delivered, response rate) are estimates; responses and NPS are real
- [ ] After COPS-338: delete the local clinic files, load file and exports (`data/`, `out/`, `~/Downloads/export_prod_*`)
