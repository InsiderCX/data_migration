-- SIE legacy import: remove EVERYTHING from all earlier attempts (import_batch approach, v3, and v4 if ever loaded).
-- Restores the original schema and trigger. For EU stg (data + schema) and UK stg (schema only). Never needed on prod.
-- Safe to run when parts were never applied. Run the WHOLE file. On any error: run ROLLBACK; and send the message.

BEGIN;

DO $$
BEGIN
  -- 1) legacy_invite_map first, so the link trigger can no longer re-link anything
  IF to_regclass('public.legacy_invite_map') IS NOT NULL THEN
    EXECUTE 'DELETE FROM public.legacy_invite_map';
  END IF;

  -- 2) v3 / v4 data: everything hanging off legacy (mock) sending batches and legacy_source_row
  IF to_regclass('public.legacy_sending_batch') IS NOT NULL THEN
    EXECUTE 'CREATE TEMP TABLE _lb ON COMMIT DROP AS SELECT sending_batch_id, account_id, loaded_at FROM public.legacy_sending_batch';
    EXECUTE 'CREATE TEMP TABLE _pv (id int) ON COMMIT DROP';
    EXECUTE 'INSERT INTO _pv SELECT patient_visit_id FROM public.visit_msg WHERE sending_batch_id IN (SELECT sending_batch_id FROM _lb)';
    IF to_regclass('public.legacy_source_row') IS NOT NULL THEN
      EXECUTE 'INSERT INTO _pv SELECT patient_visit_id FROM public.legacy_source_row
               WHERE patient_visit_id IS NOT NULL AND coalesce(raw->>''visit_date'', '''') = ''''';
      EXECUTE 'DELETE FROM public.legacy_source_row';
    END IF;
    -- stop with a clear message if anything else now references the legacy data
    IF EXISTS (SELECT 1 FROM public.patient_ticket WHERE patient_visit_id IN (SELECT id FROM _pv)) THEN
      RAISE EXCEPTION 'Patient Tickets exist on legacy visits - send me: SELECT id, patient_visit_id, created_at FROM patient_ticket WHERE patient_visit_id IN (...)';
    END IF;
    IF EXISTS (SELECT 1 FROM public.survey_invite_reminder_prep_log WHERE sending_batch_id IN (SELECT sending_batch_id FROM _lb)) THEN
      RAISE EXCEPTION 'Reminder logs reference legacy sending batches - send me this message';
    END IF;
    EXECUTE 'UPDATE public.survey_response SET visit_msg_id = NULL
             WHERE visit_msg_id IN (SELECT id FROM public.visit_msg WHERE sending_batch_id IN (SELECT sending_batch_id FROM _lb))';
    EXECUTE 'DELETE FROM public.visit_msg WHERE sending_batch_id IN (SELECT sending_batch_id FROM _lb)';
    -- batches before visits: visit_msg_sending_batch.last_processed_visit_id references patient_visit
    EXECUTE 'DELETE FROM public.visit_msg_sending_batch WHERE id IN (SELECT sending_batch_id FROM _lb)';
    EXECUTE 'DELETE FROM public.patient_visit_param WHERE patient_visit_id IN (SELECT id FROM _pv)';
    EXECUTE 'DELETE FROM public.patient_visit WHERE id IN (SELECT id FROM _pv)';
    EXECUTE 'DELETE FROM public.patient p USING (SELECT DISTINCT account_id, loaded_at FROM _lb) l
             WHERE p.account_id = l.account_id AND p.created = l.loaded_at
               AND NOT EXISTS (SELECT 1 FROM public.patient_visit pv WHERE pv.patient_id = p.id)
               AND NOT EXISTS (SELECT 1 FROM public.patient_ticket t WHERE t.patient_id = p.id)';
  END IF;

  -- 3) import_batch approach data (rows tagged with import_batch_id)
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'visit_msg' AND column_name = 'import_batch_id') THEN
    EXECUTE 'UPDATE public.survey_response SET visit_msg_id = NULL
             WHERE visit_msg_id IN (SELECT id FROM public.visit_msg WHERE import_batch_id IS NOT NULL)';
    EXECUTE 'DELETE FROM public.visit_msg WHERE import_batch_id IS NOT NULL';
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'patient_visit' AND column_name = 'import_batch_id') THEN
    EXECUTE 'DELETE FROM public.patient_visit_param WHERE patient_visit_id IN (SELECT id FROM public.patient_visit WHERE import_batch_id IS NOT NULL)';
    EXECUTE 'DELETE FROM public.patient_visit WHERE import_batch_id IS NOT NULL';
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'patient' AND column_name = 'import_batch_id') THEN
    EXECUTE 'DELETE FROM public.patient p WHERE p.import_batch_id IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM public.patient_visit pv WHERE pv.patient_id = p.id)';
  END IF;
END $$;

-- 4) Schema back to original
DROP TABLE IF EXISTS public.legacy_source_row;
DROP TABLE IF EXISTS public.legacy_invite_map;
DROP TABLE IF EXISTS public.legacy_sending_batch;
ALTER TABLE public.visit_msg DROP CONSTRAINT IF EXISTS visit_msg_batch_or_import_chk;
ALTER TABLE public.visit_msg     DROP COLUMN IF EXISTS import_batch_id;
ALTER TABLE public.patient_visit DROP COLUMN IF EXISTS import_batch_id;
ALTER TABLE public.patient       DROP COLUMN IF EXISTS import_batch_id;
DROP TABLE IF EXISTS public.import_batch;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'visit_msg'
             AND column_name = 'sending_batch_id' AND is_nullable = 'YES') THEN
    IF EXISTS (SELECT 1 FROM public.visit_msg WHERE sending_batch_id IS NULL) THEN
      RAISE EXCEPTION 'visit_msg rows without sending_batch_id exist - cannot restore NOT NULL';
    END IF;
    EXECUTE 'ALTER TABLE public.visit_msg ALTER COLUMN sending_batch_id SET NOT NULL';
  END IF;
END $$;

-- 5) Original link trigger function (exactly as on prod)
CREATE OR REPLACE FUNCTION public.survey_response__set_visit_msg_id_from_sguid()
 RETURNS trigger LANGUAGE plpgsql AS $function$
                BEGIN
                BEGIN
                    SELECT id
                    INTO NEW.visit_msg_id
                    FROM public.visit_msg
                    WHERE id = NEW.sguid::uuid;
                EXCEPTION WHEN invalid_text_representation THEN
                    NEW.visit_msg_id := NULL;
                END;

                RETURN NEW;
                END;
                $function$;

-- 6) Staging tables
DROP TABLE IF EXISTS public.stg_sie_legacy;
DROP TABLE IF EXISTS public.stg_sie_patients;
DROP TABLE IF EXISTS public.stg_sie_full;

COMMIT;

-- Check: expect 0 | NULL | NULL | NULL | NULL | NO | 0 | 507 (EU stg) / 0 (UK stg)
SELECT
  (SELECT count(*) FROM information_schema.columns WHERE table_schema = 'public' AND column_name = 'import_batch_id') AS leftover_columns,
  to_regclass('public.import_batch')          AS import_batch,
  to_regclass('public.legacy_sending_batch')  AS legacy_sending_batch,
  to_regclass('public.legacy_invite_map')     AS legacy_invite_map,
  to_regclass('public.legacy_source_row')     AS legacy_source_row,
  (SELECT is_nullable FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'visit_msg' AND column_name = 'sending_batch_id') AS sending_batch_id_nullable,
  (SELECT count(*) FROM public.visit_msg_sending_batch WHERE trigger = 'legacy_import') AS leftover_mock_batches,
  (SELECT count(*) FROM public.survey_response sr JOIN public.survey s ON s.id = sr."surveyId"
     WHERE s."alchemerId"::text = '90558103' AND sr.visit_msg_id IS NULL) AS unlinked_sie;
