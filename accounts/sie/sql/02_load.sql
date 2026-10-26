-- SIE legacy full migration v4, Part 2: load. Code SIE_LEGACY_V4.
-- Requires: 01_before_import.sql done, and data/sie_full_v4.csv imported into public.stg_sie_full (all columns TEXT).
-- Does: new Patients (existing untouched); 11,573 legacy Patient Visits (+ params, never surveyed);
--       1 mock sending batch with 2,692 legacy invites; links the 480 legacy responses;
--       stores all 14,254 source rows untouched in legacy_source_row, linked to Patient / visit / invite.
-- Platform rows (2,681) are NOT created - they already exist; they are only linked.
-- Run the WHOLE file. On any error: run ROLLBACK; and send the message.

BEGIN;

-- 0) Resolve this environment ------------------------------------------------------------------------------
CREATE TEMP TABLE cfg ON COMMIT DROP AS
SELECT s."accountId" AS account_id, s.id AS survey_id,
       (SELECT min(l.id) FROM public.location l WHERE l.account_id = s."accountId") AS location_id,
       (SELECT count(*)  FROM public.location l WHERE l.account_id = s."accountId") AS n_locations,
       (SELECT coalesce(min(l.quarantine_days), 90) FROM public.location l WHERE l.account_id = s."accountId") AS quarantine_days,
       (SELECT coalesce(a.sms_sender, 'SiE') FROM public.account a WHERE a.id = s."accountId") AS sms_from,
       now() AS loaded_at,
       'Pacijenti_JOINED_Stomatologija_i_estetika.csv'::text AS source_file
FROM public.survey s WHERE s."alchemerId"::text = '90558103';

DO $$ DECLARE c record; n int; BEGIN
  SELECT count(*) INTO n FROM cfg;
  IF n <> 1 THEN RAISE EXCEPTION 'Survey 90558103 found % times - wrong environment or data not present', n; END IF;
  SELECT * INTO c FROM cfg;
  IF c.n_locations <> 1 THEN RAISE EXCEPTION 'Account % has % Locations, expected 1', c.account_id, c.n_locations; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.account WHERE id = c.account_id AND name ILIKE 'Stomatologija i estetika%') THEN RAISE EXCEPTION 'Account % is not Stomatologija i estetika', c.account_id; END IF;
  IF to_regclass('public.legacy_source_row') IS NULL THEN RAISE EXCEPTION 'Run 01_before_import.sql first'; END IF;
  IF EXISTS (SELECT 1 FROM public.legacy_source_row WHERE account_id = c.account_id AND source_file = c.source_file) THEN RAISE EXCEPTION 'Source file already loaded'; END IF;
  IF to_regclass('public.stg_sie_full') IS NULL THEN RAISE EXCEPTION 'Import sie_full_v4.csv into public.stg_sie_full first'; END IF;
  RAISE NOTICE 'Using account_id=%, location_id=%, survey_id=%', c.account_id, c.location_id, c.survey_id;
END $$;

-- 1) Stage + type ---------------------------------------------------------------------------------------------
CREATE TEMP TABLE stg ON COMMIT DROP AS
SELECT row_no::int                                              AS row_no,
       btrim(row_kind::text)                                    AS row_kind,
       -- original columns, untouched (NULL from the import tool = empty in the file)
       coalesce(raw_id::text, '')            AS r_id,            coalesce(raw_first_name::text, '')   AS r_first_name,
       coalesce(raw_last_name::text, '')     AS r_last_name,     coalesce(raw_source_id::text, '')    AS r_source_id,
       coalesce(raw_phone::text, '')         AS r_phone,         coalesce(raw_lead_source::text, '')  AS r_lead_source,
       coalesce(raw_year_of_birth::text, '') AS r_year_of_birth, coalesce(raw_gender_code::text, '')  AS r_gender_code,
       coalesce(raw_country_code::text, '')  AS r_country_code,  coalesce(raw_language_code::text, '') AS r_language_code,
       coalesce(raw_visit_date::text, '')    AS r_visit_date,    coalesce(raw_procedure::text, '')    AS r_procedure,
       coalesce(raw_comment::text, '')       AS r_comment,       coalesce(raw_doctor::text, '')       AS r_doctor,
       coalesce(raw_status::text, '')        AS r_status,        coalesce(raw_accommodation::text, '') AS r_accommodation,
       coalesce(raw_organized_transport::text, '') AS r_organized_transport, coalesce(raw_age::text, '') AS r_age,
       -- computed
       NULLIF(btrim(legacy_sguid::text), '')                    AS legacy_sguid,
       NULLIF(btrim(phone_clean::text), '')                     AS phone_clean,
       NULLIF(btrim(est_visit_date::text), '')::timestamptz     AS est_visit_date,
       NULLIF(btrim(est_sent_at::text), '')::timestamptz        AS est_sent_at,
       NULLIF(btrim(est_status::text), '')                      AS est_status,
       (btrim(coalesce(has_response::text, '')) = 'true')       AS has_response,
       NULLIF(btrim(procedure_mock::text), '')                  AS procedure_mock,
       CASE WHEN NULLIF(btrim(derived_year_of_birth::text), '')::numeric BETWEEN 1900 AND 2026
            THEN NULLIF(btrim(derived_year_of_birth::text), '')::numeric::int END AS derived_year_of_birth,
       NULLIF(btrim(sort_ts::text), '')::timestamp              AS sort_ts
FROM public.stg_sie_full;

ALTER TABLE stg ADD COLUMN patient_id int, ADD COLUMN pv_id int, ADD COLUMN visit_msg_id uuid;

-- 2) Prep checks ------------------------------------------------------------------------------------------------
DO $$ DECLARE n int; BEGIN
  SELECT count(*) INTO n FROM stg;                                    IF n <> 14254 THEN RAISE EXCEPTION 'rows %, expected 14254', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'platform';        IF n <> 2681  THEN RAISE EXCEPTION 'platform rows %, expected 2681', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_invite';   IF n <> 2692  THEN RAISE EXCEPTION 'legacy_invite rows %, expected 2692', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_visit';    IF n <> 8881  THEN RAISE EXCEPTION 'legacy_visit rows %, expected 8881', n; END IF;
  SELECT count(*) INTO n FROM (SELECT row_no FROM stg GROUP BY 1 HAVING count(*) > 1) d; IF n > 0 THEN RAISE EXCEPTION 'duplicate row_no %', n; END IF;
  -- raw columns must arrive as text exactly as in the file (an auto-typed date/number column would change them)
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'platform' AND r_visit_date !~ '^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$';
    IF n > 0 THEN RAISE EXCEPTION 'raw_visit_date was converted by the import tool (% rows) - re-import with ALL columns as TEXT', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE r_phone ~ '^\d+\.\d+$|e\+' AND r_phone <> '9,99999E+99';
    IF n > 0 THEN RAISE EXCEPTION 'raw_phone was converted to a number (% rows) - re-import with ALL columns as TEXT', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind <> 'platform' AND (phone_clean IS NULL OR est_visit_date IS NULL OR legacy_sguid IS NULL);
    IF n > 0 THEN RAISE EXCEPTION 'incomplete legacy rows %', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_invite' AND (est_sent_at IS NULL OR est_status NOT IN ('DELIVERED','UNDELIVERABLE'));
    IF n > 0 THEN RAISE EXCEPTION 'incomplete invite rows %', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_invite' AND est_sent_at >= ('2024-10-16 00:00'::timestamp AT TIME ZONE 'Europe/Zagreb');
    IF n > 0 THEN RAISE EXCEPTION 'legacy sends overlap platform period %', n; END IF;
  SELECT count(*) INTO n FROM stg s JOIN public.survey_response sr
     ON sr."surveyId" = (SELECT survey_id FROM cfg) AND sr.sguid = s.legacy_sguid AND sr.visit_msg_id IS NULL
     WHERE s.row_kind = 'legacy_invite' AND s.has_response; IF n <> 480 THEN RAISE EXCEPTION 'unlinked legacy responses found %, expected 480', n; END IF;
END $$;

UPDATE stg SET visit_msg_id = uuid_generate_v5('6f1c6c2e-5d1b-4b8a-9a77-1e2c5a0b5e11'::uuid, 'sie-legacy-' || legacy_sguid)
WHERE row_kind = 'legacy_invite';

DO $$ DECLARE n int; BEGIN
  SELECT count(*) INTO n FROM stg s JOIN public.visit_msg vm ON vm.id = s.visit_msg_id; IF n > 0 THEN RAISE EXCEPTION 'legacy visit_msg ids already exist %', n; END IF;
END $$;

-- 3) Patients: new only, from legacy rows (latest legacy visit wins); existing Patients untouched ------------------
INSERT INTO public.patient (account_id, source_id, first_name, last_name, phone, gender_code, language_code,
                            country_code, year_of_birth, lead_source)
SELECT DISTINCT ON (s.r_source_id) c.account_id, s.r_source_id,
       NULLIF(btrim(s.r_first_name), ''), NULLIF(btrim(s.r_last_name), ''), s.phone_clean,
       CASE WHEN upper(btrim(s.r_gender_code)) IN ('F','M') THEN upper(btrim(s.r_gender_code)) END,
       upper(NULLIF(btrim(s.r_language_code), '')),
       CASE upper(btrim(s.r_country_code)) WHEN 'ROM' THEN 'ROU' ELSE upper(NULLIF(btrim(s.r_country_code), '')) END,
       s.derived_year_of_birth, NULLIF(btrim(s.r_lead_source), '')
FROM stg s CROSS JOIN cfg c
WHERE s.row_kind <> 'platform'
ORDER BY s.r_source_id, s.sort_ts DESC NULLS LAST, s.row_no DESC
ON CONFLICT (account_id, source_id) DO NOTHING;

UPDATE stg s SET patient_id = p.id FROM public.patient p, cfg c
WHERE p.account_id = c.account_id AND p.source_id = s.r_source_id;

-- 4) One mock sending batch for all legacy invites ----------------------------------------------------------------
CREATE TEMP TABLE sb ON COMMIT DROP AS
SELECT nextval(pg_get_serial_sequence('public.visit_msg_sending_batch', 'id'))::int AS batch_id;

INSERT INTO public.visit_msg_sending_batch (id, account_id, created_at, trigger, sent_at, processed_visits, processed_patients,
                                            created_messages, quarantine_blocked, ignored_visits, type, msg_sending_method)
OVERRIDING SYSTEM VALUE
SELECT sb.batch_id, c.account_id,
       (SELECT min(est_sent_at) FROM stg WHERE row_kind = 'legacy_invite') - interval '54 seconds', 'legacy_import',
       (SELECT min(est_sent_at) FROM stg WHERE row_kind = 'legacy_invite'),
       (SELECT count(*) FROM stg WHERE row_kind <> 'platform'),
       (SELECT count(DISTINCT patient_id) FROM stg WHERE row_kind <> 'platform'),
       (SELECT count(*) FROM stg WHERE row_kind = 'legacy_invite'),
       (SELECT count(*) FROM stg WHERE row_kind = 'legacy_visit'),
       '[]'::json, 'SURVEY_INVITE', 'INFOBIP_SMS_MAIN'
FROM sb CROSS JOIN cfg c;

INSERT INTO public.legacy_sending_batch (sending_batch_id, account_id, code, comment, source_files, loaded_by, loaded_at)
SELECT sb.batch_id, c.account_id, 'SIE_LEGACY_V4',
       'LEGACY DATA - Stomatologija i estetika, May 2023 - 15 Oct 2024: one mock sending batch holding all pre-platform survey invites. '
       || 'ESTIMATED: invite selection (90-day quarantine + age>=18 replay; responded always included), send time, '
       || 'visit date (send - 27 h), delivery status (95.2% platform rate), procedure (from visit comment). '
       || 'REAL: Survey Responses, Patient data, doctor, visit comment. Original rows in legacy_source_row.',
       ARRAY[c.source_file, 'Sie_surveys.csv', 'sie_full_v4.csv'], 'ana@insidercx.com', c.loaded_at
FROM sb CROSS JOIN cfg c;

-- 5) Legacy Patient Visits (all 11,573) + params ------------------------------------------------------------------
UPDATE stg SET pv_id = nextval(pg_get_serial_sequence('public.patient_visit', 'id')) WHERE row_kind <> 'platform';

INSERT INTO public.patient_visit (id, account_id, location_id, patient_id, visit_date, doctor, procedure, comment)
OVERRIDING SYSTEM VALUE
SELECT s.pv_id, c.account_id, c.location_id, s.patient_id, s.est_visit_date,
       NULLIF(btrim(s.r_doctor), ''), s.procedure_mock, NULLIF(btrim(s.r_comment), '')
FROM stg s CROSS JOIN cfg c WHERE s.row_kind <> 'platform';

INSERT INTO public.patient_visit_param (patient_visit_id, param, value, account_id)
SELECT s.pv_id, p.param, p.value, c.account_id
FROM stg s CROSS JOIN cfg c
CROSS JOIN LATERAL (VALUES ('accommodation',       coalesce(NULLIF(btrim(s.r_accommodation), ''), 'NE')),
                           ('organized_transport', coalesce(NULLIF(btrim(s.r_organized_transport), ''), 'NE')),
                           ('ignore_for_survey',   'true')) p(param, value)
WHERE s.row_kind <> 'platform';

UPDATE public.visit_msg_sending_batch SET last_processed_visit_id = (SELECT max(pv_id) FROM stg)
WHERE id = (SELECT batch_id FROM sb);

-- 6) Legacy Visit Msgs (2,692), filled like real SMS invites of this Account -----------------------------------------
INSERT INTO public.visit_msg (id, invite_id, account_id, location_id, patient_visit_id, sending_batch_id, template_id,
                              sms_from, destination, sms_text, status, sms_status_group, sms_status_name,
                              created_at, sent_at, status_updated_at, quarantine_expiration, meta)
SELECT s.visit_msg_id, s.visit_msg_id, c.account_id, c.location_id, s.pv_id, (SELECT batch_id FROM sb), t.id,
       c.sms_from, s.phone_clean, coalesce(t.sms_text, '[legacy invite]'),
       s.est_status, s.est_status,
       CASE s.est_status WHEN 'DELIVERED' THEN 'DELIVERED_TO_HANDSET' ELSE 'UNDELIVERABLE_NOT_DELIVERED' END,
       s.est_sent_at - interval '54 seconds', s.est_sent_at, s.est_sent_at + interval '27393 seconds',
       s.est_sent_at + make_interval(days => c.quarantine_days),
       hstore('send_algo', 'legacy_import')
FROM stg s CROSS JOIN cfg c
LEFT JOIN LATERAL (
  SELECT vt.id, vt.sms_text FROM public.visit_msg_template vt
  WHERE vt.account_id = c.account_id AND vt.type = 'SURVEY_INVITE'
    AND (vt.location_id = c.location_id OR vt.location_id IS NULL)
  ORDER BY (vt.language_code = upper(btrim(s.r_language_code))) DESC, (vt.language_code = 'HR') DESC, vt.id
  LIMIT 1) t ON true
WHERE s.row_kind = 'legacy_invite';

-- 7) Map + link the 480 responses ----------------------------------------------------------------------------------
INSERT INTO public.legacy_invite_map (account_id, legacy_sguid, visit_msg_id)
SELECT c.account_id, s.legacy_sguid, s.visit_msg_id FROM stg s CROSS JOIN cfg c WHERE s.row_kind = 'legacy_invite';

UPDATE public.survey_response sr SET sguid = sr.sguid
FROM stg s, cfg c
WHERE sr."surveyId" = c.survey_id AND sr.visit_msg_id IS NULL AND sr.sguid = s.legacy_sguid
  AND s.row_kind = 'legacy_invite' AND s.has_response;

-- 8) Platform rows: link to the existing invite / visit (nothing created) ------------------------------------------
UPDATE stg s SET visit_msg_id = vm.id, pv_id = vm.patient_visit_id
FROM public.visit_msg vm, cfg c
WHERE s.row_kind = 'platform' AND vm.account_id = c.account_id
  AND s.r_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' AND vm.id = s.r_id::uuid;

-- 9) Source rows, untouched ------------------------------------------------------------------------------------------
INSERT INTO public.legacy_source_row (account_id, source_file, row_no, row_kind, raw, patient_id, patient_visit_id,
                                      visit_msg_id, sending_batch_id, loaded_at)
SELECT c.account_id, c.source_file, s.row_no, s.row_kind,
       jsonb_build_object('id', s.r_id, 'first_name', s.r_first_name, 'last_name', s.r_last_name,
         'source_id', s.r_source_id, 'phone', s.r_phone, 'lead_source', s.r_lead_source,
         'year_of_birth', s.r_year_of_birth, 'gender_code', s.r_gender_code, 'country_code', s.r_country_code,
         'language_code', s.r_language_code, 'visit_date', s.r_visit_date, 'procedure', s.r_procedure,
         'comment', s.r_comment, 'doctor', s.r_doctor, 'status', s.r_status,
         'accommodation', s.r_accommodation, 'organized_transport', s.r_organized_transport, 'age', s.r_age),
       s.patient_id, s.pv_id, s.visit_msg_id,
       CASE WHEN s.row_kind = 'legacy_invite' THEN (SELECT batch_id FROM sb) END, c.loaded_at
FROM stg s CROSS JOIN cfg c;

-- 10) Post-load checks (abort everything on mismatch) ---------------------------------------------------------------
DO $$ DECLARE n int; c record; b int; BEGIN
  SELECT * INTO c FROM cfg; SELECT batch_id INTO b FROM sb;
  SELECT count(*) INTO n FROM public.visit_msg WHERE sending_batch_id = b;                         IF n <> 2692  THEN RAISE EXCEPTION 'visit_msg %', n; END IF;
  SELECT count(*) INTO n FROM public.patient_visit WHERE id IN (SELECT pv_id FROM stg WHERE row_kind <> 'platform'); IF n <> 11573 THEN RAISE EXCEPTION 'patient_visit %', n; END IF;
  SELECT count(*) INTO n FROM public.patient_visit_param WHERE patient_visit_id IN (SELECT pv_id FROM stg WHERE row_kind <> 'platform');
    IF n <> 34719 THEN RAISE EXCEPTION 'params %', n; END IF;
  SELECT count(*) INTO n FROM public.survey_response sr JOIN public.visit_msg vm ON vm.id = sr.visit_msg_id
    WHERE vm.sending_batch_id = b;                                                                 IF n <> 480   THEN RAISE EXCEPTION 'linked responses %, expected 480', n; END IF;
  SELECT count(*) INTO n FROM public.legacy_source_row WHERE account_id = c.account_id AND source_file = c.source_file;
    IF n <> 14254 THEN RAISE EXCEPTION 'source rows %', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind <> 'platform' AND patient_id IS NULL;            IF n > 0 THEN RAISE EXCEPTION 'legacy rows without patient %', n; END IF;
  SELECT count(*) INTO n FROM public.patient WHERE account_id = c.account_id AND created < c.loaded_at AND updated >= c.loaded_at;
    IF n > 0 THEN RAISE EXCEPTION 'existing patients modified %', n; END IF;
END $$;

-- Result
SELECT 'SIE_LEGACY_V4' AS code,
  (SELECT account_id FROM cfg) AS account_id, (SELECT location_id FROM cfg) AS location_id, (SELECT survey_id FROM cfg) AS survey_id,
  (SELECT batch_id FROM sb) AS mock_sending_batch_id,
  (SELECT count(*) FROM public.patient WHERE account_id = (SELECT account_id FROM cfg) AND created = (SELECT loaded_at FROM cfg)) AS new_patients,
  (SELECT count(*) FROM stg WHERE row_kind <> 'platform') AS legacy_visits,
  (SELECT count(*) FROM stg WHERE row_kind = 'legacy_invite') AS legacy_invites,
  (SELECT count(*) FROM public.survey_response sr JOIN public.visit_msg vm ON vm.id = sr.visit_msg_id
     WHERE vm.sending_batch_id = (SELECT batch_id FROM sb)) AS linked_responses,
  (SELECT count(*) FROM stg WHERE row_kind = 'platform' AND visit_msg_id IS NOT NULL) AS platform_rows_linked,     -- 2681 on prod; fewer on an older stg copy
  (SELECT count(*) FROM stg) AS source_rows_stored;

COMMIT;
