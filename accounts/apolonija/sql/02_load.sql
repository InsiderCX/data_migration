-- Stomatološka poliklinika Apolonija legacy import (APOLONIJA_LEGACY_V1). Rendered by tools/render_legacy_sql.py from sql_config.json - do not edit by hand.
-- Part 2: the load. Requires 01_before_import.sql, and apolonija_full_v1.csv imported into public.stg_apolonija_full (all columns TEXT).
-- Creates: Patients that don't exist yet (existing Patients are never changed); 30899 legacy Patient Visits
-- (never surveyed); 1 mock sending batch with 10516 legacy invites; links 1517 legacy Survey Responses;
-- stores all 67895 source rows untouched in legacy_source_row. Platform rows (11420) are only linked, never created.
-- Run the WHOLE file. Check the GUI's commit mode first. On any error: run ROLLBACK; and send the message.

BEGIN;

-- 0) Resolve this environment -------------------------------------------------------------------------------------
CREATE TEMP TABLE cfg ON COMMIT DROP AS
SELECT s."accountId" AS account_id, s.id AS survey_id,
       (SELECT min(l.id) FROM public.location l WHERE l.account_id = s."accountId") AS location_id,
       (SELECT count(*)  FROM public.location l WHERE l.account_id = s."accountId") AS n_locations,
       (SELECT coalesce(min(l.quarantine_days), 90) FROM public.location l WHERE l.account_id = s."accountId") AS quarantine_days,
       (SELECT a.sms_sender FROM public.account a WHERE a.id = s."accountId") AS sms_from,
       now() AS loaded_at,
       'Pacijenti_JOINED_Apolonija.csv'::text AS source_file
FROM public.survey s WHERE s."alchemerId"::text = '90492576';

DO $$ DECLARE c record; n int; BEGIN
  SELECT count(*) INTO n FROM cfg;
  IF n <> 1 THEN RAISE EXCEPTION 'Survey 90492576 found % times - wrong database (EU vs UK?) or data not present', n; END IF;
  SELECT * INTO c FROM cfg;
  IF c.n_locations <> 1 THEN RAISE EXCEPTION 'Account % has % Locations, expected 1', c.account_id, c.n_locations; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.account WHERE id = c.account_id AND name = 'Stomatološka poliklinika Apolonija') THEN
    RAISE EXCEPTION 'Account % is not Stomatološka poliklinika Apolonija', c.account_id; END IF;
  IF c.sms_from IS NULL THEN RAISE EXCEPTION 'Account % has no sms_sender', c.account_id; END IF;
  IF to_regclass('public.legacy_source_row') IS NULL OR to_regclass('public.legacy_invite_map') IS NULL THEN
    RAISE EXCEPTION 'Run 01_before_import.sql first'; END IF;
  IF EXISTS (SELECT 1 FROM public.legacy_source_row WHERE account_id = c.account_id AND source_file = c.source_file) THEN
    RAISE EXCEPTION 'Source file already loaded'; END IF;
  IF EXISTS (SELECT 1 FROM public.legacy_sending_batch WHERE code = 'APOLONIJA_LEGACY_V1') THEN RAISE EXCEPTION 'APOLONIJA_LEGACY_V1 already loaded'; END IF;
  IF to_regclass('public.stg_apolonija_full') IS NULL THEN RAISE EXCEPTION 'Import apolonija_full_v1.csv into public.stg_apolonija_full first'; END IF;
  RAISE NOTICE 'Using account_id=%, location_id=%, survey_id=%', c.account_id, c.location_id, c.survey_id;
END $$;

-- 1) Stage + type --------------------------------------------------------------------------------------------------
CREATE TEMP TABLE stg ON COMMIT DROP AS
SELECT row_no::int AS row_no,
       btrim(row_kind::text) AS row_kind,
       -- original columns, untouched (NULL from the import tool = empty in the file)
       coalesce(raw_id::text, '') AS raw_id,
       coalesce(raw_first_name::text, '') AS raw_first_name,
       coalesce(raw_last_name::text, '') AS raw_last_name,
       coalesce(raw_source_id::text, '') AS raw_source_id,
       coalesce(raw_phone::text, '') AS raw_phone,
       coalesce(raw_lead_source::text, '') AS raw_lead_source,
       coalesce(raw_year_of_birth::text, '') AS raw_year_of_birth,
       coalesce(raw_gender_code::text, '') AS raw_gender_code,
       coalesce(raw_country_code::text, '') AS raw_country_code,
       coalesce(raw_language_code::text, '') AS raw_language_code,
       coalesce(raw_visit_date::text, '') AS raw_visit_date,
       coalesce(raw_procedure::text, '') AS raw_procedure,
       coalesce(raw_comment::text, '') AS raw_comment,
       coalesce(raw_doctor::text, '') AS raw_doctor,
       coalesce(raw_status::text, '') AS raw_status,
       coalesce(raw_roditelj::text, '') AS raw_roditelj,
       coalesce(raw_ortodoncija::text, '') AS raw_ortodoncija,
       coalesce(raw_hzzo::text, '') AS raw_hzzo,
       coalesce(raw_next_reservation_timestamp::text, '') AS raw_next_reservation_timestamp,
       coalesce(raw_parent_ortho_comment::text, '') AS raw_parent_ortho_comment,
       coalesce(raw_parent_phone::text, '') AS raw_parent_phone,
       coalesce(raw_age::text, '') AS raw_age,
       coalesce(raw_spol2::text, '') AS raw_spol2,
       -- computed by scripts/1_build_load_file.py
       NULLIF(btrim(legacy_sguid::text), '')                AS legacy_sguid,
       NULLIF(link_sguid::text, '')                         AS link_sguid,      -- exactly as Alchemer stores it (may start with a space)
       (btrim(coalesce(sguid_reused::text, '')) = 'true')   AS sguid_reused,
       NULLIF(btrim(phone_clean::text), '')                 AS phone_clean,
       NULLIF(btrim(est_visit_date::text), '')::timestamptz AS est_visit_date,
       NULLIF(btrim(est_sent_at::text), '')::timestamptz    AS est_sent_at,
       NULLIF(btrim(est_status::text), '')                  AS est_status,
       (btrim(coalesce(has_response::text, '')) = 'true')   AS has_response,
       NULLIF(btrim(procedure_out::text), '')               AS procedure_out,
       CASE WHEN NULLIF(btrim(derived_year_of_birth::text), '')::numeric BETWEEN 1900 AND 2026
            THEN NULLIF(btrim(derived_year_of_birth::text), '')::numeric::int END AS derived_year_of_birth,
       NULLIF(btrim(sort_ts::text), '')::timestamp          AS sort_ts
FROM public.stg_apolonija_full;

ALTER TABLE stg ADD COLUMN patient_id int, ADD COLUMN pv_id int, ADD COLUMN visit_msg_id uuid,
                ADD COLUMN sid text, ADD COLUMN is_legacy boolean;
UPDATE stg SET sid = NULLIF(btrim(raw_source_id), ''), is_legacy = row_kind IN ('legacy_invite', 'legacy_visit');

-- 2) Prep checks ---------------------------------------------------------------------------------------------------
DO $$ DECLARE n int; BEGIN
  SELECT count(*) INTO n FROM stg;                                  IF n <> 67895 THEN RAISE EXCEPTION 'rows %, expected 67895', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'platform';      IF n <> 11420 THEN RAISE EXCEPTION 'platform rows %, expected 11420', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_invite'; IF n <> 10516 THEN RAISE EXCEPTION 'legacy_invite rows %, expected 10516', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_visit';  IF n <> 20383 THEN RAISE EXCEPTION 'legacy_visit rows %, expected 20383', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_raw';    IF n <> 25576 THEN RAISE EXCEPTION 'legacy_raw rows %, expected 25576', n; END IF;
  SELECT count(*) INTO n FROM (SELECT row_no FROM stg GROUP BY 1 HAVING count(*) > 1) d; IF n > 0 THEN RAISE EXCEPTION 'duplicate row_no %', n; END IF;
  -- raw columns must arrive as text exactly as in the file (an auto-typed date or number column would change them)
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'platform' AND raw_visit_date !~ '^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$';
    IF n > 0 THEN RAISE EXCEPTION 'raw_visit_date was converted by the import tool (% rows) - re-import with ALL columns as TEXT', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE raw_phone ~ '^\d+\.\d+$|e\+';
    IF n > 0 THEN RAISE EXCEPTION 'raw_phone was converted to a number (% rows) - re-import with ALL columns as TEXT', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE is_legacy AND (est_visit_date IS NULL OR legacy_sguid IS NULL);
    IF n > 0 THEN RAISE EXCEPTION 'incomplete legacy rows %', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE is_legacy AND phone_clean IS NULL; IF n <> 1524 THEN RAISE EXCEPTION 'legacy rows without phone %, expected 1524', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_invite' AND (est_sent_at IS NULL OR est_status NOT IN ('DELIVERED','UNDELIVERABLE'));
    IF n > 0 THEN RAISE EXCEPTION 'incomplete invite rows %', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_invite' AND NOT has_response
     AND est_sent_at >= ('2024-10-21 00:00'::timestamp AT TIME ZONE 'Europe/Zagreb');
    IF n > 0 THEN RAISE EXCEPTION 'estimated legacy sends in the platform period %', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE has_response AND (row_kind <> 'legacy_invite' OR link_sguid IS NULL OR sguid_reused);
    IF n > 0 THEN RAISE EXCEPTION 'responded rows that cannot be linked %', n; END IF;
  SELECT count(*) INTO n FROM stg s JOIN public.survey_response sr
     ON sr."surveyId" = (SELECT survey_id FROM cfg) AND sr.sguid = s.link_sguid AND sr.visit_msg_id IS NULL
     WHERE s.has_response;
    IF n <> 1517 THEN RAISE EXCEPTION 'unlinked legacy responses found %, expected 1517 (staging older than prod?)', n; END IF;
END $$;

UPDATE stg SET visit_msg_id = uuid_generate_v5('c41f9e2b-7d58-4a36-b0e1-5a8c2d6f9e03'::uuid, 'apolonija-legacy-' || row_no) WHERE row_kind = 'legacy_invite';

DO $$ DECLARE n int; BEGIN
  SELECT count(*) INTO n FROM stg s JOIN public.visit_msg vm ON vm.id = s.visit_msg_id; IF n > 0 THEN RAISE EXCEPTION 'legacy visit_msg ids already exist %', n; END IF;
END $$;

-- 3) Patients (decision 14). Existing Patients are never changed. -------------------------------------------------
-- Phones that belong to exactly one Patient of this Account BEFORE the load
CREATE TEMP TABLE ph_one ON COMMIT DROP AS
SELECT regexp_replace(p.phone, '\D', '', 'g') AS phone_clean, min(p.id) AS patient_id
FROM public.patient p WHERE p.account_id = (SELECT account_id FROM cfg) AND regexp_replace(p.phone, '\D', '', 'g') <> ''
GROUP BY 1 HAVING count(*) = 1;

-- 3a) rows with a source_id: the existing Patient with that source_id
UPDATE stg s SET patient_id = p.id FROM public.patient p, cfg c
WHERE s.is_legacy AND s.sid IS NOT NULL AND p.account_id = c.account_id AND p.source_id = s.sid;
-- 3b) rows without a source_id: the one existing Patient with that phone
UPDATE stg s SET patient_id = m.patient_id FROM ph_one m
WHERE s.is_legacy AND s.sid IS NULL AND s.phone_clean = m.phone_clean;

-- 3c) new Patients: one per source_id, else one per phone, else one per row; data from the latest legacy row
CREATE TEMP TABLE np ON COMMIT DROP AS
SELECT DISTINCT ON (k) k, nextval(pg_get_serial_sequence('public.patient', 'id'))::int AS id, row_no
FROM (SELECT coalesce('sid:' || sid, 'ph:' || phone_clean, 'row:' || row_no) AS k, row_no, sort_ts
      FROM stg WHERE is_legacy AND patient_id IS NULL) x
ORDER BY k, sort_ts DESC NULLS LAST, row_no DESC;

INSERT INTO public.patient (id, account_id, source_id, first_name, last_name, phone, gender_code, language_code,
                            country_code, year_of_birth, lead_source)
OVERRIDING SYSTEM VALUE
SELECT np.id, c.account_id, s.sid,
       NULLIF(btrim(s.raw_first_name), ''), NULLIF(btrim(s.raw_last_name), ''), coalesce(s.phone_clean, ''),
       CASE WHEN upper(btrim(s.raw_gender_code)) IN ('F','M') THEN upper(btrim(s.raw_gender_code)) END,
       CASE WHEN upper(btrim(s.raw_language_code)) ~ '^[A-Z]{2}$' THEN upper(btrim(s.raw_language_code)) END,
       CASE upper(btrim(s.raw_country_code)) WHEN '' THEN NULL WHEN 'ROM' THEN 'ROU' ELSE left(upper(btrim(s.raw_country_code)), 3) END,
       s.derived_year_of_birth, NULLIF(btrim(s.raw_lead_source), '')
FROM np JOIN stg s ON s.row_no = np.row_no CROSS JOIN cfg c;

UPDATE stg s SET patient_id = np.id FROM np
WHERE s.is_legacy AND s.patient_id IS NULL AND np.k = coalesce('sid:' || s.sid, 'ph:' || s.phone_clean, 'row:' || s.row_no);

-- 4) One mock sending batch for all legacy invites -------------------------------------------------------------------
CREATE TEMP TABLE sb ON COMMIT DROP AS
SELECT nextval(pg_get_serial_sequence('public.visit_msg_sending_batch', 'id'))::int AS batch_id;

INSERT INTO public.visit_msg_sending_batch (id, account_id, created_at, trigger, sent_at, processed_visits, processed_patients,
                                            created_messages, quarantine_blocked, ignored_visits, type, msg_sending_method)
OVERRIDING SYSTEM VALUE
SELECT sb.batch_id, c.account_id,
       (SELECT min(est_sent_at) FROM stg WHERE row_kind = 'legacy_invite') - interval '54 seconds', 'legacy_import',
       (SELECT min(est_sent_at) FROM stg WHERE row_kind = 'legacy_invite'),
       (SELECT count(*) FROM stg WHERE is_legacy),
       (SELECT count(DISTINCT patient_id) FROM stg WHERE is_legacy),
       (SELECT count(*) FROM stg WHERE row_kind = 'legacy_invite'),
       (SELECT count(*) FROM stg WHERE row_kind = 'legacy_visit'),
       '[]'::json, 'SURVEY_INVITE', 'INFOBIP_SMS_MAIN'
FROM sb CROSS JOIN cfg c;

INSERT INTO public.legacy_sending_batch (sending_batch_id, account_id, code, comment, source_files, loaded_by, loaded_at)
SELECT sb.batch_id, c.account_id, 'APOLONIJA_LEGACY_V1',
       'LEGACY DATA - Stomatološka poliklinika Apolonija, Nov 2022 - 20 Oct 2024: one mock sending batch holding all pre-platform survey invites. ESTIMATED: invite selection (90-day quarantine replay, no age rule; responded always included), send time (17:00 Zagreb), visit date (send - 63 h), delivery status (96.1% platform rate). Year of birth left empty. REAL: Survey Responses, Patient data, doctor, procedure, visit comment. Original rows in legacy_source_row.',
       ARRAY[c.source_file, 'Survey_responses_Apolonija.csv', 'apolonija_full_v1.csv'], 'ana@insidercx.com', c.loaded_at
FROM sb CROSS JOIN cfg c;

-- 5) Legacy Patient Visits + "never survey" param ------------------------------------------------------------------
UPDATE stg SET pv_id = nextval(pg_get_serial_sequence('public.patient_visit', 'id')) WHERE is_legacy;

INSERT INTO public.patient_visit (id, account_id, location_id, patient_id, visit_date, doctor, procedure, comment)
OVERRIDING SYSTEM VALUE
SELECT s.pv_id, c.account_id, c.location_id, s.patient_id, s.est_visit_date,
       NULLIF(btrim(s.raw_doctor), ''), s.procedure_out, NULLIF(btrim(s.raw_comment), '')
FROM stg s CROSS JOIN cfg c WHERE s.is_legacy;

INSERT INTO public.patient_visit_param (patient_visit_id, param, value, account_id)
SELECT s.pv_id, 'ignore_for_survey', 'true', c.account_id FROM stg s CROSS JOIN cfg c WHERE s.is_legacy;

UPDATE public.visit_msg_sending_batch SET last_processed_visit_id = (SELECT max(pv_id) FROM stg)
WHERE id = (SELECT batch_id FROM sb);

-- 6) Legacy Visit Msgs, filled like real SMS invites of this Account ---------------------------------------------------
INSERT INTO public.visit_msg (id, invite_id, account_id, location_id, patient_visit_id, sending_batch_id, template_id,
                              sms_from, destination, sms_text, status, sms_status_group, sms_status_name,
                              created_at, sent_at, status_updated_at, quarantine_expiration, meta)
SELECT s.visit_msg_id, s.visit_msg_id, c.account_id, c.location_id, s.pv_id, (SELECT batch_id FROM sb), t.id,
       c.sms_from, coalesce(s.phone_clean, ''), coalesce(t.sms_text, '[legacy invite]'),
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
  ORDER BY (vt.language_code = upper(btrim(s.raw_language_code))) DESC, (vt.language_code = 'HR') DESC, vt.id
  LIMIT 1) t ON true
WHERE s.row_kind = 'legacy_invite';

-- 7) Link table + link the responses ----------------------------------------------------------------------------------
-- Key = the sguid exactly as Alchemer stores it (link_sguid) for answered invites, else the legacy id.
-- Not mapped: reused ids (decision 13) and sguids whose response is Deleted (decision 12).
INSERT INTO public.legacy_invite_map (account_id, legacy_sguid, visit_msg_id)
SELECT c.account_id, coalesce(s.link_sguid, s.legacy_sguid), s.visit_msg_id
FROM stg s CROSS JOIN cfg c
WHERE s.row_kind = 'legacy_invite' AND NOT s.sguid_reused
  AND NOT EXISTS (SELECT 1 FROM public.survey_response sr WHERE sr."surveyId" = c.survey_id AND sr.status = 'Deleted'
                  AND btrim(sr.sguid) = s.legacy_sguid);

UPDATE public.survey_response sr SET sguid = sr.sguid             -- fires the trigger, which fills visit_msg_id
FROM stg s, cfg c
WHERE sr."surveyId" = c.survey_id AND sr.visit_msg_id IS NULL AND sr.sguid = s.link_sguid AND s.has_response;

-- 8) Platform rows: link to the existing invite / visit (nothing created) ----------------------------------------------
UPDATE stg s SET visit_msg_id = vm.id, pv_id = vm.patient_visit_id
FROM public.visit_msg vm, cfg c
WHERE s.row_kind = 'platform' AND vm.account_id = c.account_id
  AND btrim(s.raw_id) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' AND vm.id = btrim(s.raw_id)::uuid;
UPDATE stg s SET patient_id = pv.patient_id FROM public.patient_visit pv WHERE s.row_kind = 'platform' AND pv.id = s.pv_id;

-- 9) Source rows, untouched -----------------------------------------------------------------------------------------
INSERT INTO public.legacy_source_row (account_id, source_file, row_no, row_kind, raw, patient_id, patient_visit_id,
                                      visit_msg_id, sending_batch_id, loaded_at)
SELECT c.account_id, c.source_file, s.row_no, s.row_kind,
       jsonb_build_object(
         'id', s.raw_id,
         'first_name', s.raw_first_name,
         'last_name', s.raw_last_name,
         'source_id', s.raw_source_id,
         'phone', s.raw_phone,
         'lead_source', s.raw_lead_source,
         'year_of_birth', s.raw_year_of_birth,
         'gender_code', s.raw_gender_code,
         'country_code', s.raw_country_code,
         'language_code', s.raw_language_code,
         'visit_date', s.raw_visit_date,
         'procedure', s.raw_procedure,
         'comment', s.raw_comment,
         'doctor', s.raw_doctor,
         'status', s.raw_status,
         'roditelj', s.raw_roditelj,
         'ortodoncija', s.raw_ortodoncija,
         'hzzo', s.raw_hzzo,
         'next_reservation_timestamp', s.raw_next_reservation_timestamp,
         'parent_ortho_comment', s.raw_parent_ortho_comment,
         'parent_phone', s.raw_parent_phone,
         'age', s.raw_age,
         'Spol2', s.raw_spol2),
       s.patient_id, s.pv_id, s.visit_msg_id,
       CASE WHEN s.row_kind = 'legacy_invite' THEN (SELECT batch_id FROM sb) END, c.loaded_at
FROM stg s CROSS JOIN cfg c;

-- 10) Post-load checks (abort everything on mismatch) -----------------------------------------------------------------
DO $$ DECLARE n int; c record; b int; BEGIN
  SELECT * INTO c FROM cfg; SELECT batch_id INTO b FROM sb;
  SELECT count(*) INTO n FROM public.visit_msg WHERE sending_batch_id = b;   IF n <> 10516 THEN RAISE EXCEPTION 'visit_msg %', n; END IF;
  SELECT count(*) INTO n FROM public.patient_visit WHERE id IN (SELECT pv_id FROM stg WHERE is_legacy);
    IF n <> 30899 THEN RAISE EXCEPTION 'patient_visit %', n; END IF;
  SELECT count(*) INTO n FROM public.patient_visit_param WHERE patient_visit_id IN (SELECT pv_id FROM stg WHERE is_legacy);
    IF n <> 30899 THEN RAISE EXCEPTION 'params %', n; END IF;
  SELECT count(*) INTO n FROM public.survey_response sr JOIN public.visit_msg vm ON vm.id = sr.visit_msg_id
    WHERE vm.sending_batch_id = b;                                           IF n <> 1517 THEN RAISE EXCEPTION 'linked responses %, expected 1517', n; END IF;
  SELECT count(*) INTO n FROM public.survey_response sr JOIN public.visit_msg vm ON vm.id = sr.visit_msg_id
    WHERE vm.sending_batch_id = b AND sr.status = 'Deleted';                 IF n > 0 THEN RAISE EXCEPTION 'Deleted responses linked %', n; END IF;
  SELECT count(*) INTO n FROM public.legacy_source_row WHERE account_id = c.account_id AND source_file = c.source_file;
    IF n <> 67895 THEN RAISE EXCEPTION 'source rows %', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE is_legacy AND patient_id IS NULL;    IF n > 0 THEN RAISE EXCEPTION 'legacy rows without patient %', n; END IF;
  SELECT count(*) INTO n FROM public.patient WHERE account_id = c.account_id AND created < c.loaded_at AND updated >= c.loaded_at;
    IF n > 0 THEN RAISE EXCEPTION 'existing patients modified %', n; END IF;
END $$;

-- Result
SELECT 'APOLONIJA_LEGACY_V1' AS code,
  (SELECT account_id FROM cfg) AS account_id, (SELECT location_id FROM cfg) AS location_id, (SELECT survey_id FROM cfg) AS survey_id,
  (SELECT batch_id FROM sb) AS mock_sending_batch_id,
  (SELECT count(*) FROM public.patient WHERE account_id = (SELECT account_id FROM cfg) AND created = (SELECT loaded_at FROM cfg)) AS new_patients,
  (SELECT count(*) FROM stg WHERE is_legacy) AS legacy_visits,
  (SELECT count(*) FROM stg WHERE row_kind = 'legacy_invite') AS legacy_invites,
  (SELECT count(*) FROM public.survey_response sr JOIN public.visit_msg vm ON vm.id = sr.visit_msg_id
     WHERE vm.sending_batch_id = (SELECT batch_id FROM sb)) AS linked_responses,
  (SELECT count(*) FROM stg WHERE row_kind = 'platform' AND visit_msg_id IS NOT NULL) AS platform_rows_linked,   -- 11420 on prod; fewer on an older stg copy
  (SELECT count(*) FROM stg) AS source_rows_stored;

COMMIT;
