-- Arcadia legacy import (ARCADIA_LEGACY_V1). Rendered by tools/render_legacy_sql.py from sql_config.json - do not edit by hand.
-- Part 1: EVERYTHING BEFORE THE CSV IMPORT. Run the WHOLE file once.
-- 1) stop if this Account's load is already (partly) there   2) make sure the legacy tables and trigger fallback exist
--    (they already exist where SIE was loaded; CREATE ... IF NOT EXISTS / OR REPLACE leaves them as they are)
-- 3) create the empty staging table stg_arcadia_full (all text, no key)
-- After this: import arcadia_full_v1.csv INTO stg_arcadia_full, run the count check at the bottom, then 02_load.sql.
-- On any error: run ROLLBACK; and send the message.

BEGIN;

DO $$ DECLARE acc int; n int; BEGIN
  SELECT count(*), min("accountId") INTO n, acc FROM public.survey WHERE "alchemerId"::text = '90534273';
  IF n <> 1 THEN RAISE EXCEPTION 'Survey 90534273 found % times - wrong database (EU vs UK?) or data not present', n; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.account WHERE id = acc AND name = 'Arcadia') THEN
    RAISE EXCEPTION 'Account % is not Arcadia', acc; END IF;
  IF to_regclass('public.legacy_source_row') IS NOT NULL THEN
    EXECUTE 'SELECT count(*) FROM public.legacy_source_row WHERE account_id = $1 AND source_file = $2' INTO n USING acc, 'Pacijenti_Joined_Arcadia.csv';
    IF n > 0 THEN RAISE EXCEPTION 'Pacijenti_Joined_Arcadia.csv is already loaded (% rows) - run 99_rollback.sql first if you mean to reload', n; END IF;
  END IF;
  IF to_regclass('public.legacy_sending_batch') IS NOT NULL THEN
    EXECUTE 'SELECT count(*) FROM public.legacy_sending_batch WHERE code = $1' INTO n USING 'ARCADIA_LEGACY_V1';
    IF n > 0 THEN RAISE EXCEPTION 'ARCADIA_LEGACY_V1 already exists (% batches) - run 99_rollback.sql first', n; END IF;
  END IF;
  IF EXISTS (SELECT 1 FROM public.visit_msg_sending_batch b WHERE b.account_id = acc AND b.trigger = 'legacy_import') THEN
    RAISE EXCEPTION 'Account % already has a legacy_import sending batch - a leftover; find out where it came from first', acc; END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.legacy_sending_batch (
  sending_batch_id int PRIMARY KEY REFERENCES public.visit_msg_sending_batch(id) ON DELETE CASCADE,
  account_id       int  NOT NULL REFERENCES public.account(id),
  code             text NOT NULL,
  comment          text NOT NULL,
  source_files     text[],
  loaded_by        text,
  loaded_at        timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.legacy_invite_map (
  account_id   int  NOT NULL,
  legacy_sguid text NOT NULL,
  visit_msg_id uuid NOT NULL REFERENCES public.visit_msg(id) ON DELETE CASCADE,
  PRIMARY KEY (account_id, legacy_sguid)
);
CREATE TABLE IF NOT EXISTS public.legacy_source_row (
  account_id       int  NOT NULL REFERENCES public.account(id),
  source_file      text NOT NULL,
  row_no           int  NOT NULL,
  row_kind         text NOT NULL,
  raw              jsonb NOT NULL,
  patient_id       int  REFERENCES public.patient(id)       ON DELETE SET NULL,
  patient_visit_id int  REFERENCES public.patient_visit(id) ON DELETE SET NULL,
  visit_msg_id     uuid REFERENCES public.visit_msg(id)     ON DELETE SET NULL,
  sending_batch_id int  REFERENCES public.visit_msg_sending_batch(id) ON DELETE SET NULL,
  loaded_at        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (account_id, source_file, row_no)
);

-- Link trigger fallback (identical to what SIE installed): uuid sguid as before; other sguids -> legacy_invite_map
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

DROP TABLE IF EXISTS public.stg_arcadia_full;
CREATE TABLE public.stg_arcadia_full (
  row_no                         text,
  row_kind                       text,
  raw_id                         text,
  raw_sent_at                    text,
  raw_location                   text,
  raw_first_name                 text,
  raw_last_name                  text,
  raw_source_id                  text,
  raw_phone                      text,
  raw_lead_source                text,
  raw_year_of_birth              text,
  raw_gender_code                text,
  raw_country_code               text,
  raw_language_code              text,
  raw_visit_date                 text,
  raw_procedure                  text,
  raw_comment                    text,
  raw_doctor                     text,
  raw_status                     text,
  legacy_sguid                   text,
  link_sguid                     text,
  sguid_reused                   text,
  phone_clean                    text,
  est_visit_date                 text,
  est_sent_at                    text,
  est_status                     text,
  has_response                   text,
  procedure_out                  text,
  derived_year_of_birth          text,
  sort_ts                        text
);

COMMIT;

-- Check: expect legacy_sending_batch | legacy_invite_map | legacy_source_row | stg_arcadia_full | 0
SELECT to_regclass('public.legacy_sending_batch') AS t1,
       to_regclass('public.legacy_invite_map')    AS t2,
       to_regclass('public.legacy_source_row')    AS t3,
       to_regclass('public.stg_arcadia_full')                  AS staging,
       (SELECT count(*) FROM public.stg_arcadia_full)          AS staging_rows;

-- After the GUI import, run this on its own. Expect 13595 / 6497 / 5255 / 1843 / 0
-- SELECT count(*) AS total, count(*) FILTER (WHERE row_kind = 'platform') AS platform,
--        count(*) FILTER (WHERE row_kind = 'legacy_invite') AS legacy_invite, count(*) FILTER (WHERE row_kind = 'legacy_visit') AS legacy_visit,
--        count(*) FILTER (WHERE row_kind = 'legacy_raw') AS legacy_raw
-- FROM public.stg_arcadia_full;
