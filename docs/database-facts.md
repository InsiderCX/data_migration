# Database facts the scripts depend on

Verified on the EU prod replica on 23–26 Oct 2026. **Re-verify each one before a new Account** (queries below); if anything differs, update the scripts and this file.

| # | Fact | Why it matters | Check |
|---|---|---|---|
| 1 | Link trigger `survey_response__set_visit_msg_id` is BEFORE INSERT **OR UPDATE** and sets `visit_msg_id` from `sguid::uuid`, NULL on cast failure | Legacy numeric sguids never link; manual links get wiped → fallback to `legacy_invite_map` | `SELECT pg_get_triggerdef(oid) FROM pg_trigger WHERE tgrelid='survey_response'::regclass AND NOT tgisinternal;` and `pg_get_functiondef` of the function |
| 2 | `patient.id`, `patient_visit.id`, `visit_msg_sending_batch.id` are `GENERATED ALWAYS` identity | Explicit ids need `OVERRIDING SYSTEM VALUE` | `information_schema.columns` `is_identity`, `identity_generation` |
| 3 | FKs into touched tables: `visit_msg_sending_batch.last_processed_visit_id → patient_visit`, `patient_ticket → patient, patient_visit`, `survey_invite_reminder_prep_log → visit_msg_sending_batch`, `visit_msg → patient_visit, visit_msg_sending_batch`, `survey_response.visit_msg_id → visit_msg ON DELETE SET NULL` | Delete order in rollback / cleanup; guards for tickets | `SELECT conrelid::regclass, pg_get_constraintdef(oid) FROM pg_constraint WHERE contype='f' AND confrelid IN ('patient'::regclass,'patient_visit'::regclass,'visit_msg'::regclass,'visit_msg_sending_batch'::regclass);` |
| 4 | Unique `uq_source_id_per_account (account_id, source_id)` on `patient` | `ON CONFLICT DO NOTHING` for existing Patients | `pg_indexes` |
| 5 | `visit_msg.sending_batch_id` NOT NULL | Legacy invites need a (mock) sending batch | `information_schema.columns` |
| 6 | `patient_visit.visit_date` stores **local wall-clock time labelled UTC** | Legacy visit dates must follow it; display uses `AT TIME ZONE 'UTC'` (open platform bug) | Compare a few platform rows with the clinic file |
| 7 | Extensions `hstore`, `uuid-ossp` present | `meta` hstore, `uuid_generate_v5` | `SELECT extname FROM pg_extension;` |
| 8 | `visit_msg.status` is free text; SMS delivery names `DELIVERED_TO_HANDSET`, `UNDELIVERABLE_NOT_DELIVERED` | Imported rows look like real ones | `SELECT status, sms_status_name, count(*) FROM visit_msg WHERE account_id=… GROUP BY 1,2;` |
| 9 | Clinicdash definitions (NPS by `"dateStarted"`, Message performance by `sent_at`, response rate over delivered, half-up rounding) | Report and validation queries must match the dashboards | `icx-database` skill, `references/metrics.md` |
| 10 | Staging is an older copy of prod and may not contain every Account | Validation differences, "Survey not found" | Check survey + unlinked counts before running |
| 11 | Alchemer export `Time Started` is local time, month-first `MM/DD/YYYY` | Anchors for send-date estimation | Compare with `survey_response."dateStarted"` for a few ids |
