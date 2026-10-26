# Design (v4)

What a legacy load creates, how it is marked, and how it links, so dashboards treat it like platform data and it can be found, exported and removed later.

## Principles

1. **Add, never update.** Existing Patients, Visits, Visit Msgs and Survey Responses keep their values. The only change to existing rows: an empty `survey_response.visit_msg_id` gets filled (through the trigger).
2. **No new columns or constraints on existing tables.** All bookkeeping lives in three new tables.
3. **Every source row is kept untouched** and linked to what it became, so the clinic's file can be reproduced exactly.
4. **Estimates are labelled** at the batch level (`legacy_sending_batch.comment`), per Visit Msg (`meta send_algo=legacy_import`), and in every export.
5. **Idempotent and reversible.** Visit Msg ids are deterministic (`uuid_generate_v5(namespace, '<prefix>-legacy-' || legacy_id)`), the load refuses to run twice, and `99_rollback.sql` removes it exactly.

## New tables (`01_before_import.sql`, shared by all Accounts)

| Table | Purpose |
|---|---|
| `legacy_sending_batch (sending_batch_id PK→visit_msg_sending_batch, account_id, code, comment, source_files, loaded_by, loaded_at)` | Marks which sending batches are legacy (mock) batches, and says in words what is real and estimated |
| `legacy_invite_map (account_id, legacy_sguid, visit_msg_id)` | Legacy numeric sguid → imported Visit Msg; read by the link trigger |
| `legacy_source_row (account_id, source_file, row_no, row_kind, raw jsonb, patient_id, patient_visit_id, visit_msg_id, sending_batch_id, loaded_at)` | Every source row as received; `row_kind` = `platform` (already existed, only linked) / `legacy_invite` / `legacy_visit` |

**Trigger change:** `survey_response__set_visit_msg_id_from_sguid` keeps its uuid path; for a non-uuid sguid it looks up `legacy_invite_map` scoped by the response's Survey Account. Without this, the next Alchemer Sync would wipe the links (the trigger fires on UPDATE too).

## What one load writes (`02_load.sql`)

| Object | Rows | Notes |
|---|---|---|
| `patient` | new Patients only | `ON CONFLICT (account_id, source_id) DO NOTHING`; `created` = load time (used by rollback) |
| `patient_visit` | every legacy row | estimated `visit_date` in the existing convention (local wall-clock labelled UTC); real doctor and comment |
| `patient_visit_param` | 3 per visit | the Account's usual params + `ignore_for_survey = true` so the platform never surveys them |
| `visit_msg_sending_batch` | **1** | `trigger = 'legacy_import'`, realistic counters |
| `visit_msg` | invited legacy visits | initial invites (`id = invite_id`), template by language, the Account's sender, Infobip-style status names, quarantine expiry, `meta send_algo=legacy_import` |
| `legacy_*` tables | as above | |
| `survey_response` | responses to link | `UPDATE … SET sguid = sguid` re-fires the trigger; nothing else changes |

## How dashboards see it

- **NPS Trends / General dashboard:** responses linked through `visit_msg`, dated by `"dateStarted"`, so legacy NPS is real.
- **Message performance:** initial invites with `sent_at`, so legacy sent / delivered / response rate are estimates.
- **Breakdowns:** doctor (real), gender (real), age (derived year of birth), procedure (derived).

## Finding a load later

```sql
-- legacy invites of a load
SELECT vm.* FROM visit_msg vm JOIN legacy_sending_batch l ON l.sending_batch_id = vm.sending_batch_id WHERE l.code = '<CODE>';
-- every source row and what it became
SELECT row_no, row_kind, raw, patient_id, patient_visit_id, visit_msg_id FROM legacy_source_row WHERE source_file = '<file>' ORDER BY row_no;
-- Patients created by the load
SELECT p.* FROM patient p JOIN legacy_sending_batch l ON l.account_id = p.account_id AND p.created = l.loaded_at WHERE l.code = '<CODE>';
```

## History

v1–v2 added `import_batch_id` columns to existing tables; v3 used one mock batch per day; v4 (current) uses one batch, keeps every source row, and changes no existing table. `accounts/sie/sql/00_cleanup_all.sql` removes every earlier version.
