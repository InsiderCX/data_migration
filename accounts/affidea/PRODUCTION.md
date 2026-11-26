# Production run: Affidea legacy import

> **Draft, 26 Nov 2026. Not run yet** (DEV-411). Waiting for: Ana's check (DEV-412), Karlo's answers (DEV-409), the ops sign-off (COPS task) and **two decisions below** (split characters, rollback). If an answer changes the build, the numbers below change with it.

Same flow as the six Accounts of 23 Nov 2026 (DEV-185). Worked examples: `docs/production-run-2026-11-23.md` (run sheet, rules, Beekeeper lessons) and `accounts/apolonija/runs/2026-11-23_production.md` (the split-character fix). Plan: [`docs/plans/2026-11-24_bolnica-colic-and-next.md`](../../docs/plans/2026-11-24_bolnica-colic-and-next.md).

## Before production

1. **Apply Karlo's answers** (DEV-409, among them the 3,532 responses whose invite is missing from the file). Any change means rebuild, re-render, mock test and staging rerun.
2. **Decide how to avoid split characters** (see below), and prepare it.
3. **Freeze the scripts:** copy `sql/` to `production/DEV-375/3_affidea/` and add the hashes to `production/DEV-375/SHA256SUMS`. Ana runs only the frozen copies.
4. **Preflight:** build `out/00_preflight.sql` with `tools/preprod/build_preflight.py` (point it at `production/DEV-375`).
5. **Refresh from the prod replica on the day:** export `db_unlinked_responses_<date>.csv` and `db_visit_msg_ids_<date>.csv`, rebuild the load file, compare its SHA-256 with the one below. If it differs, compare the values and write down why, and re-run the split-character check (a new file has new chunk edges).
6. Re-check the schema facts in `docs/database-facts.md` (link trigger, identity columns, foreign keys).

## Go / no-go

- [ ] DEV-412 done (Ana) and ops sign-off in the COPS task (Karlo).
- [ ] Every DEV-409 answer applied; the staging run after it passed. Run log in `runs/`.
- [ ] **Split-character decision taken and prepared** (below).
- [ ] A dev has reviewed PR #11; it is merged right before the production session.
- [ ] A recent prod backup / point-in-time recovery is available.
- [ ] **Rollback decision written down** (below).
- [ ] Ana gives Claude explicit permission for each production write, or runs it herself.
- [ ] Input hashes (25 Nov 2026; update if step 5 rebuilt the load file):
  - `Pacijenti_JOINED_Affidea.csv` `c62a96ab70ccee12795399a43010c60ac2e785c459992904fe2702e8c197add5`
  - `Survey_responses_Affidea.csv` `ebda077f2430c5d68463b91c88189bd250ef73401d8868fab87664d7d20ab6a5`
  - `data/affidea_full_v1.csv` `c4cf313757cd9d6c5c325f085a46118a1f12e0d7077ea9495716a623ed6aef21`
  - `data/affidea_full_v1_discarded_rows.csv` `81e572cab9614ca1ef05c88106eb5dfb0d56ed8cd94448d73d20de272547f454`

## Steps (EU prod `insider-prod`, Beekeeper)

Expected numbers are **real**: from the load file, the mock test and the staging run of 26 Nov 2026 (batch 13113). Prod baseline on the replica, 26 Nov 2026: 11,323 unlinked Survey Responses (same as the build input), 127,041 platform Visit Msgs, no `AFFIDEA_LEGACY_V1` batch.

| # | Do | Expected | If not |
|---|---|---|---|
| 0 | `00_preflight.sql` (read-only; Claude on the replica or Ana on prod) | `insider-prod`, Account `Affidea`, 4 Locations (Čavka, Kalajžić, Sv. Rok, Vita), every `*_present` / `*_already_*` 0, unlinked legacy responses 7,628, trigger unchanged | **Stop.** Wrong database (EU vs UK) or prod changed |
| 1 | `01_before_import.sql` | `legacy_sending_batch / legacy_invite_map / legacy_source_row / stg_affidea_full / 0` | `ROLLBACK;`, send the error |
| 2 | Import `data/affidea_full_v1.csv` (40 MB) into the **existing** `stg_affidea_full`, every column TEXT. Beekeeper: **untick "Automatically Trim Whitespace"**. See "Split characters" | — | Drop the table, run `01` again |
| 3 | Count check (bottom of `01`), then the space check and the split-character check | 163,105 / 126,684 / 36,408 / 7 / 6. Spaces kept: `raw_procedure` 5,428, `raw_first_name` 1. Replacement characters: 0 (or 7 if the decision was "import, then fix") | Drop, `01`, re-import |
| 4 | Check the GUI's commit mode, then `02_load.sql` (whole file). Wait for the result row (**4 minutes** on staging) | `AFFIDEA_LEGACY_V1`, legacy_visits 36,415, legacy_invites 36,408, **linked_responses 7,628**, **platform_rows_linked 126,684** (staging 119,094: older copy), source_rows_stored 163,105, new Patients ≤ 22,040 | Nothing saved (one transaction). `ROLLBACK;`, send the error |
| 5 | Claude: `03` query 1 on the replica | Same numbers; deleted_linked 0, existing_patients_changed 0, legacy_rows_without_patient 0, still unlinked 3,695 | Stop the session (run sheet rule 3) |
| 5b | Only if "import, then fix": run the mock-tested `out/05_fix_split_characters.sql` | 7 source cells, 1 legacy Patient Visit, ≤ 1 Patient fixed | Stop and investigate |
| 6 | `04_export_original_csv.sql` → CSV, in **four parts** (Beekeeper exports at most 50,000 rows): Claude prepares the four copies of `04` with `LIMIT 50000 OFFSET 0 / 50000 / 100000 / 150000` (`04` orders by `row_no`, unique). Claude joins them and compares by value with `Pacijenti_JOINED_Affidea.csv` minus the 16 discarded rows | Identical, 163,105 rows | Investigate |
| 7 | `DROP TABLE public.stg_affidea_full;` | Claude confirms on the replica | — |
| 8 | Clinicdash (prod): legacy months visible from Apr 2023 for all four Locations; the platform period unchanged | Per Location and year as in `docs/validation/2026-11-25_alchemer_zoho_dev375.md` (2023 = Zoho; 2024 Zoho +16 late answers, −1 for response 7379); legacy NPS 81.4 on staging, real | Investigate |

Space and split-character check for step 3 (one result set):

```sql
SELECT count(*) FILTER (WHERE raw_procedure <> btrim(raw_procedure, ' '))   AS procedure_spaces,
       count(*) FILTER (WHERE raw_first_name <> btrim(raw_first_name, ' ')) AS first_name_spaces,
       count(*) FILTER (WHERE raw_doctor LIKE '%' || chr(65533) || '%'
                           OR raw_last_name LIKE '%' || chr(65533) || '%')  AS replacement_chars
FROM public.stg_affidea_full;
```

## Split characters (decide before go)

Beekeeper reads a CSV in 64 KB chunks. Where a chunk edge falls inside a two-byte letter (š, ć, ž), it stores two U+FFFD characters instead (Apolonija, 23 Nov). Checked on 26 Nov 2026 with the same method, which finds exactly Apolonija's 3 cells: **Affidea's load file has 7 such edges.**

| `row_no` | Column | Row kind | Effect on the platform if imported with Beekeeper |
|---|---|---|---|
| 46880, 67235, 107612, 118883, 121901 | `raw_last_name` (46880, 107612) / `raw_doctor` | platform | raw copy in `legacy_source_row` only; `04` differs |
| 136940 | `raw_doctor` | legacy_invite | the doctor name of 1 legacy Patient Visit |
| 158821 | `raw_last_name` | legacy_invite | the last name of 1 Patient, if the row creates a new Patient |

Options (Ana decides):
- **Import without Beekeeper's chunking**, e.g. `\copy` from `psql`, as on staging (staging had 0 broken cells). Simplest, but a different tool on prod.
- **Import with Beekeeper, then fix**: Claude writes `out/05_fix_split_characters.sql` as for Apolonija (values matched by md5, one transaction, guards before and after), mock-tests it, and Ana runs it after step 5.

`03` cannot see this problem (it counts, it does not compare text). The step 3 check and the step 6 export comparison do.

## Rollback

`99_rollback.sql` deletes only this load's rows, but it is slow: `legacy_source_row` (`visit_msg_id`, `patient_visit_id`, `patient_id`) and `legacy_invite_map.visit_msg_id` have no index. Not run on staging; estimated **3.5–4 hours** (Colić 14 min for 2,452 rows; Orto-Nova did not finish). It locks `patient` / `patient_visit` while it runs, which on prod means the app waits that long.

**Ana decides before go:**
- add the indexes first (dev ticket; then run the rollback on staging to time it), or
- accept the risk as on 23 Nov (rollback only if existing data changed, run sheet rule 3), and run it out of hours if needed.

## After

- Write `runs/<date>_production.md` and mark this file "done, see run log".
- Claude compares prod with Zoho per Location and year, as in the 25 Nov comparison.
- With the ops sign-off on prod: tell the CSM that legacy sent and delivered are **estimated** (send dates estimated, delivery status real); responses and NPS are real.
- After the sign-off: delete the local clinic files, load file and exports (`data/`, `out/`).
