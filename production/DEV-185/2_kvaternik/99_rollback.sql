-- Kvaternik legacy import (KVATERNIK_LEGACY_V1). Rendered by tools/render_legacy_sql.py from sql_config.json - do not edit by hand.
-- Rollback of the load (data only; the legacy tables and the trigger fallback stay - other Accounts use them).
-- Run the WHOLE file. On any error: run ROLLBACK; and send the message.

BEGIN;

CREATE TEMP TABLE lr ON COMMIT DROP AS
SELECT r.* FROM public.legacy_source_row r
JOIN public.survey s ON s."accountId" = r.account_id AND s."alchemerId"::text = '90677816'
WHERE r.source_file = 'Pacijenti_joined_Kvaternik.csv';

CREATE TEMP TABLE lb ON COMMIT DROP AS
SELECT lsb.sending_batch_id, lsb.account_id, lsb.loaded_at FROM public.legacy_sending_batch lsb
JOIN public.survey s ON s."accountId" = lsb.account_id AND s."alchemerId"::text = '90677816'
WHERE lsb.code = 'KVATERNIK_LEGACY_V1';

DO $$ BEGIN
  IF (SELECT count(*) FROM lb) > 1 THEN RAISE EXCEPTION 'more than one KVATERNIK_LEGACY_V1 batch - stop and check'; END IF;
  IF EXISTS (SELECT 1 FROM public.patient_ticket WHERE patient_visit_id IN (SELECT patient_visit_id FROM lr WHERE row_kind IN ('legacy_invite','legacy_visit'))) THEN
    RAISE EXCEPTION 'Patient Tickets exist on legacy visits - resolve them before rolling back';
  END IF;
  IF EXISTS (SELECT 1 FROM public.survey_invite_reminder_prep_log WHERE sending_batch_id IN (SELECT sending_batch_id FROM lb)) THEN
    RAISE EXCEPTION 'Reminder logs reference the legacy sending batch - resolve before rolling back';
  END IF;
END $$;

-- unlink responses (map first so the trigger leaves the link empty)
DELETE FROM public.legacy_invite_map WHERE visit_msg_id IN (SELECT id FROM public.visit_msg WHERE sending_batch_id IN (SELECT sending_batch_id FROM lb));
UPDATE public.survey_response SET visit_msg_id = NULL
WHERE visit_msg_id IN (SELECT id FROM public.visit_msg WHERE sending_batch_id IN (SELECT sending_batch_id FROM lb));

DELETE FROM public.legacy_source_row r USING lr
WHERE r.account_id = lr.account_id AND r.source_file = lr.source_file AND r.row_no = lr.row_no;

DELETE FROM public.visit_msg WHERE sending_batch_id IN (SELECT sending_batch_id FROM lb);
-- batches before visits: last_processed_visit_id references patient_visit (cascades legacy_sending_batch)
DELETE FROM public.visit_msg_sending_batch WHERE id IN (SELECT sending_batch_id FROM lb);
DELETE FROM public.patient_visit_param WHERE patient_visit_id IN (SELECT patient_visit_id FROM lr WHERE row_kind IN ('legacy_invite','legacy_visit'));
DELETE FROM public.patient_visit       WHERE id               IN (SELECT patient_visit_id FROM lr WHERE row_kind IN ('legacy_invite','legacy_visit'));
DELETE FROM public.patient p
WHERE p.account_id = (SELECT min(account_id) FROM lb) AND p.created = (SELECT min(loaded_at) FROM lb)
  AND NOT EXISTS (SELECT 1 FROM public.patient_visit pv WHERE pv.patient_id = p.id)
  AND NOT EXISTS (SELECT 1 FROM public.patient_ticket t WHERE t.patient_id = p.id);

SELECT (SELECT count(*) FROM lr) AS source_rows_removed,
       (SELECT count(*) FROM lr WHERE row_kind IN ('legacy_invite','legacy_visit')) AS legacy_visits_removed,
       (SELECT count(*) FROM public.legacy_sending_batch WHERE code = 'KVATERNIK_LEGACY_V1') AS remaining_batches;   -- 0
COMMIT;
