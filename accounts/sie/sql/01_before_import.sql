-- SIE legacy full migration v4 - EVERYTHING BEFORE THE CSV IMPORT, in order. Run the WHOLE file once.
-- 1) stop if leftovers from earlier attempts exist   2) drop old staging tables
-- 3) v4 migration (3 new tables + link trigger)      4) create empty staging table stg_sie_full (all text)
-- After this: import sie_full_v4.csv INTO stg_sie_full, run the count check, then 02_load.sql.
-- On any error: run ROLLBACK; and send the message.

BEGIN;

-- 1) Leftovers from earlier attempts -> run 00_cleanup_all.sql first
DO $$ DECLARE src int := 0; BEGIN
  IF to_regclass('public.legacy_source_row') IS NOT NULL THEN
    EXECUTE 'SELECT count(*) FROM public.legacy_source_row WHERE source_file = ''Pacijenti_JOINED_Stomatologija_i_estetika.csv''' INTO src;
  END IF;
  IF to_regclass('public.import_batch') IS NOT NULL
     OR EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND column_name = 'import_batch_id')
     OR EXISTS (SELECT 1 FROM public.visit_msg_sending_batch WHERE trigger = 'legacy_import')
     OR src > 0 THEN
    RAISE EXCEPTION 'Leftovers from an earlier attempt found - run 00_cleanup_all.sql first, then this file again';
  END IF;
END $$;

-- 2) Old staging tables
DROP TABLE IF EXISTS public.stg_sie_legacy;
DROP TABLE IF EXISTS public.stg_sie_patients;
DROP TABLE IF EXISTS public.stg_sie_full;

-- 3) v4 migration
-- Marks which visit_msg_sending_batch rows are legacy (mock) batches
CREATE TABLE IF NOT EXISTS public.legacy_sending_batch (
  sending_batch_id int PRIMARY KEY REFERENCES public.visit_msg_sending_batch(id) ON DELETE CASCADE,
  account_id       int  NOT NULL REFERENCES public.account(id),
  code             text NOT NULL,
  comment          text NOT NULL,
  source_files     text[],
  loaded_by        text,
  loaded_at        timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE public.legacy_sending_batch IS
  'Sending batches that are LEGACY DATA: mock batches holding imported pre-platform survey invites. '
  'Their visit_msg rows have estimated dates/status; linked Survey Responses are real.';

-- Legacy numeric sguid -> imported Visit Msg (used by the link trigger)
CREATE TABLE IF NOT EXISTS public.legacy_invite_map (
  account_id   int  NOT NULL,
  legacy_sguid text NOT NULL,
  visit_msg_id uuid NOT NULL REFERENCES public.visit_msg(id) ON DELETE CASCADE,
  PRIMARY KEY (account_id, legacy_sguid)
);

-- Every source row exactly as received, linked to what it is in the live data
CREATE TABLE IF NOT EXISTS public.legacy_source_row (
  account_id       int  NOT NULL REFERENCES public.account(id),
  source_file      text NOT NULL,
  row_no           int  NOT NULL,                 -- position in the source file (1 = first data row)
  row_kind         text NOT NULL,                 -- platform | legacy_invite | legacy_visit
  raw              jsonb NOT NULL,                -- the original columns, values exactly as in the file
  patient_id       int  REFERENCES public.patient(id)       ON DELETE SET NULL,
  patient_visit_id int  REFERENCES public.patient_visit(id) ON DELETE SET NULL,
  visit_msg_id     uuid REFERENCES public.visit_msg(id)     ON DELETE SET NULL,
  sending_batch_id int  REFERENCES public.visit_msg_sending_batch(id) ON DELETE SET NULL,
  loaded_at        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (account_id, source_file, row_no)
);
COMMENT ON TABLE public.legacy_source_row IS
  'Untouched copy of imported source files (contains Patient PII). One query on raw re-creates the original file exactly.';

-- Link trigger: uuid sguid as before; numeric legacy sguid -> legacy_invite_map (scoped by Account)
CREATE OR REPLACE FUNCTION public.survey_response__set_visit_msg_id_from_sguid()
 RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
  BEGIN
    SELECT id INTO NEW.visit_msg_id FROM public.visit_msg WHERE id = NEW.sguid::uuid;
  EXCEPTION WHEN invalid_text_representation THEN
    SELECT m.visit_msg_id INTO NEW.visit_msg_id
    FROM public.legacy_invite_map m
    JOIN public.survey s ON s.id = NEW."surveyId"
    WHERE m.account_id = s."accountId" AND m.legacy_sguid = NEW.sguid;
  END;
  RETURN NEW;
END $fn$;

-- 4) Empty staging table for the import (all text, no key)
CREATE TABLE public.stg_sie_full (
  row_no                  text,
  row_kind                text,
  raw_id                  text,
  raw_first_name          text,
  raw_last_name           text,
  raw_source_id           text,
  raw_phone               text,
  raw_lead_source         text,
  raw_year_of_birth       text,
  raw_gender_code         text,
  raw_country_code        text,
  raw_language_code       text,
  raw_visit_date          text,
  raw_procedure           text,
  raw_comment             text,
  raw_doctor              text,
  raw_status              text,
  raw_accommodation       text,
  raw_organized_transport text,
  raw_age                 text,
  legacy_sguid            text,
  phone_clean             text,
  est_visit_date          text,
  est_sent_at             text,
  est_status              text,
  has_response            text,
  procedure_mock          text,
  derived_year_of_birth   text,
  sort_ts                 text
);

COMMIT;

-- Check: expect legacy_sending_batch | legacy_invite_map | legacy_source_row | stg_sie_full | 0
SELECT to_regclass('public.legacy_sending_batch') AS t1,
       to_regclass('public.legacy_invite_map')    AS t2,
       to_regclass('public.legacy_source_row')    AS t3,
       to_regclass('public.stg_sie_full')         AS staging,
       (SELECT count(*) FROM public.stg_sie_full) AS staging_rows;
