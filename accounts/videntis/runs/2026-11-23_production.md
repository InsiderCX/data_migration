# Videntis production run, 23 Nov 2026

Run log of the `VIDENTIS_LEGACY_V1` load on **EU production** (`insider-prod`), part of DEV-185 (all six legacy Accounts in one session). Ana ran every step in Beekeeper Studio. Claude read only the prod replica (Zamera) and the files Ana exported. Scripts: the frozen copies in `production/DEV-185/`, checked against `SHA256SUMS` before each copy. Session run sheet: `docs/production-run-2026-11-23.md`.

- Load file: `data/videntis_full_v1.csv`, SHA-256 `ded1fb0d3325e49e5e5662e1239b787c9f6628862781c9f1d42f68144cbdc47f` (same as the Account card and the 17 Nov staging run).
- Ops sign-off of staging: COPS-333 (Karlo, "Ready for production - all accounts").

## Steps

| # | Step | Who | Result | Check |
|---|---|---|---|---|
| 0 | `00_preflight.sql` (read-only) | Ana | `insider-prod`, Account ok, 1 Location; 4,371 new Visit Msg ids, none present; 504 unlinked legacy Survey Responses = expected; trigger unchanged | ✓ |
| 1 | `01_before_import.sql` | Ana | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_videntis_full / 0` | ✓ |
| 2 | GUI import of `data/videntis_full_v1.csv` (Beekeeper) | Ana | — | — |
| 3 | Count check | Ana | 16,416 / 5,483 / 4,371 / 6,562 / 0 (total / platform / invite / visit / raw) | ✓ |
| 3b | Space check (were edge spaces kept?) | Ana | not run: the only edge spaces in this file are non-standard space characters in raw names, which nothing else uses | — |
| 4 | `02_load.sql` | Ana | `VIDENTIS_LEGACY_V1`, batch **13485**, new Patients 2,307, 10,933 / 4,371 / **504** / 5,483 / 16,416 (legacy visits / invites / linked / platform rows linked / source rows) | ✓ |
| 5 | `03_validation.sql`, query 1 | Claude on the replica | Same numbers as step 4; see Results | ✓ |
| 6 | `04_export_original_csv.sql`, compared by value with the clinic file | Ana, Claude | Identical, 16,416 rows | ✓ |
| 7 | `DROP TABLE public.stg_videntis_full;` | Ana | Replica: table gone | ✓ |

## Results (prod replica, after the load)

| Check | Value | Expected |
|---|---|---|
| Source rows stored | 16,416 | 16,416 ✓ |
| Legacy Patient Visits / Survey Invites | 10,933 / 4,371 | ✓ |
| Legacy Survey Responses linked | 504 | 504 ✓ |
| Platform rows linked | 5,483 | = platform rows ✓ |
| New Patients | 2,307 | ≤ 2,317 on staging ✓ (Patients created since the staging copy are reused) |
| Existing Patients changed | **0** | 0 ✓ |
| Legacy rows without a Patient | **0** | 0 ✓ |
| Deleted Survey Responses linked | **0** | 0 ✓ |
| Survey Responses still unlinked | 115 (same as staging) | not part of this load |

**Legacy NPS (real):** 501 scored responses, 430 promoters, 37 detractors, **NPS 78.4** (3 linked responses have no score and are not counted, as in Clinicdash and Zoho).
**Legacy send dates (estimated):** 29 Nov 2022 – 18 Oct 2024. Sent, delivered and response rate for the legacy period are estimates; responses and NPS are real.

**Clinicdash numbers (prod replica, 23 Nov 2026):** every month before November 2026 equals the 17 Nov projection that ops signed off in COPS-333; November 2026 differs only by Survey Responses that came in after 17 Nov.

## Identifiers on production (to find or undo this load)

- Load code `VIDENTIS_LEGACY_V1`, `legacy_sending_batch.loaded_at` = 2026-11-23 10:27:17 UTC
- Mock sending batch `visit_msg_sending_batch.id = 13485` (`trigger = 'legacy_import'`), Account 38, Alchemer survey 90508475
- Patients created by the load: `patient.created = loaded_at` (2,307)
- Source rows: `legacy_source_row.source_file = 'Pacijenti_JOINED_Videntis.csv'`
- Undo (data only): `production/DEV-185/4_videntis/99_rollback.sql` (slow; locks `patient` / `patient_visit` while it runs)

## Still open

- [ ] Ops validate production and sign off: COPS-338 (Karlo)
- [ ] With COPS-338: tell the CSM that legacy message figures (sent, delivered, response rate) are estimates; responses and NPS are real
- [ ] After COPS-338: delete the local clinic files, load file and exports (`data/`, `out/`, `~/Downloads/export_prod_*`)
