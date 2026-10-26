-- SIE legacy full migration v4: rollback of the load (data only; v4 Part 1 tables/trigger stay).
-- Run the WHOLE file. On any error: run ROLLBACK; and send the message.

BEGIN;

CREATE TEMP TABLE lr ON COMMIT DROP AS
SELECT r.* FROM public.legacy_source_row r
JOIN public.survey s ON s."accountId" = r.account_id AND s."alchemerId"::text = '90558103'
WHERE r.source_file = 'Pacijenti_JOINED_Stomatologija_i_estetika.csv';

CREATE TEMP TABLE lb ON COMMIT DROP AS
SELECT lsb.sending_batch_id, lsb.account_id, lsb.loaded_at FROM public.legacy_sending_batch lsb
WHERE lsb.code = 'SIE_LEGACY_V4' AND lsb.account_id = (SELECT min(account_id) FROM lr);

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM public.patient_ticket WHERE patient_visit_id IN (SELECT patient_visit_id FROM lr WHERE row_kind <> 'platform')) THEN
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
DELETE FROM public.patient_visit_param WHERE patient_visit_id IN (SELECT patient_visit_id FROM lr WHERE row_kind <> 'platform');
DELETE FROM public.patient_visit       WHERE id               IN (SELECT patient_visit_id FROM lr WHERE row_kind <> 'platform');
DELETE FROM public.patient p
WHERE p.account_id = (SELECT min(account_id) FROM lr) AND p.created = (SELECT min(loaded_at) FROM lr)
  AND NOT EXISTS (SELECT 1 FROM public.patient_visit pv WHERE pv.patient_id = p.id)
  AND NOT EXISTS (SELECT 1 FROM public.patient_ticket t WHERE t.patient_id = p.id);

SELECT (SELECT count(*) FROM lr) AS source_rows_removed,
       (SELECT count(*) FROM lr WHERE row_kind <> 'platform') AS legacy_visits_removed,
       (SELECT count(*) FROM public.legacy_sending_batch WHERE code = 'SIE_LEGACY_V4') AS remaining_batches;   -- 0
COMMIT;
