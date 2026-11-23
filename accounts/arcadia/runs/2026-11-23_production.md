# Arcadia production run, 23 Nov 2026

Run log of the `ARCADIA_LEGACY_V1` load on **EU production** (`insider-prod`), part of DEV-185 (all six legacy Accounts in one session). Ana ran every step in Beekeeper Studio. Claude read only the prod replica (Zamera) and the files Ana exported. Scripts: the frozen copies in `production/DEV-185/`, checked against `SHA256SUMS` before each copy. Session run sheet: `docs/production-run-2026-11-23.md`.

- Load file: `data/arcadia_full_v1.csv`, SHA-256 `3e913556433cd525e1fbf099153380c721290384024d021305de861b524edf01` (same as the Account card and the 17 Nov staging run).
- Ops sign-off of staging: COPS-333 (Karlo, "Ready for production - all accounts").

## Steps

| # | Step | Who | Result | Check |
|---|---|---|---|---|
| 0 | `00_preflight.sql` (read-only) | Ana | `insider-prod`, Account ok, 1 Location; 5,097 new Visit Msg ids, none present; 1,072 unlinked legacy Survey Responses = expected; trigger unchanged | ✓ |
| 1 | `01_before_import.sql` | Ana | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_arcadia_full / 0` | ✓ |
| 2 | GUI import of `data/arcadia_full_v1.csv` (Beekeeper) | Ana | — | — |
| 3 | Count check | Ana | 13,306 / 6,497 / 5,097 / 1,712 / 0 (total / platform / invite / visit / raw) | ✓ |
| 3b | Space check (were edge spaces kept?) | Ana | 61 / 61 ✓ | ✓ |
| 4 | `02_load.sql` | Ana | `ARCADIA_LEGACY_V1`, batch **13484**, new Patients 6,613, 6,809 / 5,097 / **1,072** / 6,497 / 13,306 (legacy visits / invites / linked / platform rows linked / source rows) | ✓ |
| 5 | `03_validation.sql`, query 1 | Claude on the replica | Same numbers as step 4; see Results | ✓ |
| 6 | `04_export_original_csv.sql`, compared by value with the clinic file | Ana, Claude | Identical, 13,306 rows (clinic file minus the 289 discarded reused-id rows) | ✓ |
| 7 | `DROP TABLE public.stg_arcadia_full;` | Ana | Replica: table gone | ✓ |

## Results (prod replica, after the load)

| Check | Value | Expected |
|---|---|---|
| Source rows stored | 13,306 | 13,306 ✓ |
| Legacy Patient Visits / Survey Invites | 6,809 / 5,097 | ✓ |
| Legacy Survey Responses linked | 1,072 | 1,072 ✓ |
| Platform rows linked | 6,497 | = platform rows ✓ |
| New Patients | 6,613 | ≤ 6,623 on staging ✓ (Patients created since the staging copy are reused) |
| Existing Patients changed | **0** | 0 ✓ |
| Legacy rows without a Patient | **0** | 0 ✓ |
| Deleted Survey Responses linked | **0** | 0 ✓ |
| Survey Responses still unlinked | 20 | not part of this load |

**Legacy NPS (real):** 1,072 scored responses, 994 promoters, 36 detractors, **NPS 89.4**.
**Legacy send dates (estimated):** 29 Jun 2023 – 4 Feb 2025. Sent, delivered and response rate for the legacy period are estimates; responses and NPS are real.

**Clinicdash numbers (prod replica, 23 Nov 2026):** every month before November 2026 equals the 17 Nov projection that ops signed off in COPS-333; November 2026 differs only by Survey Responses that came in after 17 Nov.

## Identifiers on production (to find or undo this load)

- Load code `ARCADIA_LEGACY_V1`, `legacy_sending_batch.loaded_at` = 2026-11-23 10:19:34 UTC
- Mock sending batch `visit_msg_sending_batch.id = 13484` (`trigger = 'legacy_import'`), Account 45, Alchemer survey 90534273
- Patients created by the load: `patient.created = loaded_at` (6,613)
- Source rows: `legacy_source_row.source_file = 'Pacijenti_Joined_Arcadia.csv'`
- Undo (data only): `production/DEV-185/3_arcadia/99_rollback.sql` (slow; locks `patient` / `patient_visit` while it runs)

## Still open

- [ ] Ops validate production and sign off: COPS-338 (Karlo)
- [ ] With COPS-338: tell the CSM that legacy message figures (sent, delivered, response rate) are estimates; responses and NPS are real
- [ ] After COPS-338: delete the local clinic files, load file and exports (`data/`, `out/`, `~/Downloads/export_prod_*`)
