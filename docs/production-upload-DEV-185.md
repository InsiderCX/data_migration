# Production upload of the legacy data (DEV-185): what a reviewer needs to know

Linear: [DEV-185](https://linear.app/insidercx/issue/DEV-185). Ops signed off staging for all six Accounts in [COPS-333](https://linear.app/insidercx/issue/COPS-333) (19 Nov 2026).

## What we will do

Add the old survey history (before each clinic used our platform) to six EU Accounts: Videntis, Arcadia, Apolonija, Kvaternik, Poliklinika Mazalin and Optical Express. After the load, Clinicdash shows the legacy months next to the platform months.

The load is **append only**. Existing Patients, Patient Visits and Visit Msgs are never changed. The only existing rows we touch are the legacy Survey Responses that get linked to their legacy invite.

Ana runs it in a GUI SQL client on EU prod, one Account at a time, smallest first. Per Account:

| Step | Script | What it does |
|---|---|---|
| 1 | `production/DEV-185/<n>_<account>/01_before_import.sql` | Guards; makes sure the legacy tables and the trigger fallback exist; creates an empty staging table |
| 2 | GUI import | The load file goes into the staging table (all columns text) |
| 3 | `02_load.sql` | The load: **one transaction**, checks before and after writing; any failed check rolls everything back |
| 4 | `03_validation.sql` | Read-only checks |
| 5 | `04_export_original_csv.sql` | Read-only: rebuilds the clinic file from what was stored; must equal the original |
| if needed | `99_rollback.sql` | Deletes only this load's rows (by its sending batch and source rows) |

## Tables

**Existing tables, rows added:**

| Table | What is added |
|---|---|
| `patient` | Patients from the clinic file that don't exist yet. A Patient that exists (same `source_id`, or one Patient with the same phone) is reused, never updated |
| `patient_visit`, `patient_visit_param` | One Patient Visit per legacy clinic row, with its params |
| `visit_msg_sending_batch` | One mock sending batch per Account, `trigger = 'legacy_import'`, to carry the legacy invites (`visit_msg.sending_batch_id` is NOT NULL). The script also sets this batch's own `last_processed_visit_id` |
| `visit_msg` | One Visit Msg (Survey Invite) per legacy invite. Send date and, where the file has none, delivery status are **estimated**; `meta` says which |

**Existing table, rows changed:**

| Table | Change |
|---|---|
| `survey_response` | Only the legacy responses this load links. The script runs a no-op `UPDATE … SET sguid = sguid`, which fires the existing link trigger and fills `visit_msg_id`. Responses that are Deleted in Alchemer are never linked. No other column changes |

**Legacy tables (no new table on prod):** `legacy_sending_batch`, `legacy_invite_map` and `legacy_source_row` already exist on EU prod since the SIE load (28 Oct 2026); `01` uses `CREATE TABLE IF NOT EXISTS`, so it leaves them as they are. Each load adds rows:

| Table | Why |
|---|---|
| `legacy_sending_batch` | Marks the mock batch as a legacy load (load code, source files, who loaded it, when). The rollback finds the load by it |
| `legacy_invite_map` | Legacy link id → Visit Msg, for numeric legacy ids. The trigger can't cast those to a uuid, so it falls back to this map. Kvaternik and Mazalin legacy invites use the original uuid as the Visit Msg id and don't need the map |
| `legacy_source_row` | Every clinic row, untouched, as JSON, with the ids it became. This is how `04` proves nothing was lost, and how `99` removes exactly this load |

**Temporary table:** `stg_<account>_full`, one per Account, created by `01` and dropped after the run (all text, no key, so the GUI can't auto-type phones or dates).

**Trigger function:** `01` runs `CREATE OR REPLACE FUNCTION survey_response__set_visit_msg_id_from_sguid`. Its body is identical to the one on prod today (compared on the replica on 20 Nov 2026), so this changes nothing.

## Per Account

Counts from the load files and the staging runs of 17 Nov 2026 (real on staging). On prod the new Patients can be a little lower, because prod has Patients created after the staging copy (28 Sep 2026).

| Account | Clinic rows stored | Legacy Patient Visits | Legacy invites (Visit Msgs) | Responses linked | New Patients (staging) |
|---|---|---|---|---|---|
| Optical Express | 7,903 | 4,053 | 4,051 | 634 | 3,961 |
| Kvaternik | 8,407 | 727 | 727 | 132 | 675 |
| Arcadia | 13,306 | 6,809 | 5,097 | 1,072 | 6,623 |
| Videntis | 16,416 | 10,933 | 4,371 | 504 | 2,317 |
| Mazalin | 30,481 | 2,453 | 2,453 | 437 | 1,083 |
| Apolonija | 67,895 | 30,899 | 10,516 | 1,515 | 3,301 |

## Checked on 20 Nov 2026 (before review)

- Prod replica: every Account resolves by its Alchemer survey id, nothing is loaded yet. The unlinked legacy responses the load files expect are unchanged since the snapshots the files were built from (fingerprint match for all six), so `02`'s guards should pass.
- Schema facts the scripts rely on are unchanged (`docs/database-facts.md`): trigger, identity columns, foreign keys, `fk_country_code`.
- Load file hashes match the Account cards. Mock test passes for all six: load, validation, export identical, rollback back to baseline, reload.

## What to look at in review

The scripts that run on production are in `production/DEV-185/`, one folder per Account, numbered in run order. They are copies of `accounts/<account>/sql/` (byte-identical to what passed the mock tests and staging on 17 Nov 2026); `SHA256SUMS` holds their hashes. Ana runs these files and no others. Before the session, check them with `cd production/DEV-185 && shasum -a 256 -c SHA256SUMS`, and that they still equal `accounts/<account>/sql/`.

1. `02_load.sql` of one Account end to end (Kvaternik is short). The other five come from the same template; they differ only by the Account's settings (ids, names, expected counts, linking options).
2. The guards: wrong database or Account, load already present, staging table missing or type-converted by the GUI, expected counts.
3. `99_rollback.sql`: it deletes only rows of this load, in foreign-key order (the mock `visit_msg_sending_batch` before the Patient Visits it references, then Patients the load created). **Known issue:** it is slow on big Accounts (Apolonija took 35–68 min on staging) and holds locks while it runs. It only runs if a load must be undone.
4. Anything that would touch existing rows other than the `survey_response` link above.

Not covered here, and only a person can do it: running on prod, the Clinicdash check, the comparison with Zoho afterwards (DEV-319) and the ops check on prod (COPS-338).
