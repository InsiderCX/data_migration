-- =====================================================================================================
-- SIE legacy import (SIE_LEGACY_V4) - exports for Ops validation
-- Account: Stomatologija i estetika. Run each query on its own and export the result as CSV with the
-- file name given in its header. No Patient names or phones are included.
--
-- Column prefixes:
--   actual_   real data (clinic export or Alchemer)          derived_  calculated from real data
--   est_      estimated (no source data exists)             mock_     technical filler so dashboards work
-- Legacy invites = Visit Msgs in the mock sending batch listed in legacy_sending_batch (code SIE_LEGACY_V4).
-- Every source row (incl. 8,881 legacy visits without invite) = legacy_source_row.
-- =====================================================================================================


-- ---------------------------------------------------------------------------------------------------
-- 00_summary.csv  -  one row with all key counts
-- expect: 1 mock batch, 2692 invites (480 actual / 2212 estimated), 2592 delivered, 480 responses,
--         11573 legacy visits, 14254 source rows, 27 unlinked responses
-- ---------------------------------------------------------------------------------------------------
WITH l AS (SELECT sending_batch_id, account_id, loaded_at FROM legacy_sending_batch WHERE code = 'SIE_LEGACY_V4'),
     m AS (SELECT vm.*, sr.id AS response_id FROM visit_msg vm
           LEFT JOIN survey_response sr ON sr.visit_msg_id = vm.id
           WHERE vm.sending_batch_id IN (SELECT sending_batch_id FROM l))
SELECT (SELECT count(*) FROM l)                                            AS mock_sending_batches,
       (SELECT min(loaded_at) FROM l)                                      AS loaded_at,
       count(*)                                                            AS invites_total,
       count(response_id)                                                  AS invites_actual_with_response,
       count(*) - count(response_id)                                       AS invites_estimated,
       count(*) FILTER (WHERE status = 'DELIVERED')                        AS delivered,
       count(*) FILTER (WHERE status <> 'DELIVERED')                       AS undelivered_est,
       count(response_id)                                                  AS responses_actual,
       (SELECT count(*) FROM patient p WHERE p.account_id = (SELECT min(account_id) FROM l)
          AND p.created = (SELECT min(loaded_at) FROM l))                  AS patients_created_by_load,
       (SELECT count(*) FROM survey_response sr JOIN survey s ON s.id = sr."surveyId"
          WHERE s."alchemerId"::text = '90558103' AND sr.visit_msg_id IS NULL) AS responses_still_unlinked,
       (SELECT count(*) FROM legacy_source_row WHERE source_file = 'Pacijenti_JOINED_Stomatologija_i_estetika.csv' AND row_kind <> 'platform') AS legacy_visits_total,
       (SELECT count(*) FROM legacy_source_row WHERE source_file = 'Pacijenti_JOINED_Stomatologija_i_estetika.csv') AS source_rows
FROM m;


-- ---------------------------------------------------------------------------------------------------
-- 01_monthly_messages_full_history.csv  -  as in Message performance (by send month), legacy vs platform
-- legacy sent/delivered = estimated, responses = actual
-- ---------------------------------------------------------------------------------------------------
SELECT to_char(date_trunc('month', vm.sent_at AT TIME ZONE 'Europe/Zagreb'), 'YYYY-MM') AS month,
       CASE WHEN l.sending_batch_id IS NOT NULL THEN 'legacy (sent/delivered estimated)' ELSE 'platform (actual)' END AS source,
       count(*)                                                     AS invites_sent,
       count(*) FILTER (WHERE vm.status = 'DELIVERED')              AS delivered,
       count(r.id) FILTER (WHERE r."NPS_SCORE" BETWEEN 0 AND 10)    AS responses,
       floor(1000.0 * count(r.id) FILTER (WHERE r."NPS_SCORE" BETWEEN 0 AND 10)
             / NULLIF(count(*) FILTER (WHERE vm.status = 'DELIVERED'), 0) + 0.5) / 10 AS response_rate_pct
FROM visit_msg vm
LEFT JOIN legacy_sending_batch l ON l.sending_batch_id = vm.sending_batch_id AND l.code = 'SIE_LEGACY_V4'
LEFT JOIN survey_response r ON r.visit_msg_id = vm.id
WHERE vm.account_id = (SELECT "accountId" FROM survey WHERE "alchemerId"::text = '90558103')
  AND vm.id = vm.invite_id AND vm.sent_at IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 2;


-- ---------------------------------------------------------------------------------------------------
-- 02_monthly_nps_full_history.csv  -  as in NPS Trends (by survey start month); all values actual
-- ---------------------------------------------------------------------------------------------------
SELECT to_char(date_trunc('month', sr."dateStarted" AT TIME ZONE 'Europe/Zagreb'), 'YYYY-MM') AS month,
       CASE WHEN l.sending_batch_id IS NOT NULL THEN 'legacy' ELSE 'platform' END AS source,
       count(*)                                                       AS responses,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9)             AS promoters,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") BETWEEN 7 AND 8)  AS passives,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6)             AS detractors,
       floor(1000.0 * (count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9)
                     - count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6)) / count(*) + 0.5) / 10 AS nps
FROM survey_response sr
JOIN visit_msg vm ON vm.id = sr.visit_msg_id
LEFT JOIN legacy_sending_batch l ON l.sending_batch_id = vm.sending_batch_id AND l.code = 'SIE_LEGACY_V4'
WHERE vm.account_id = (SELECT "accountId" FROM survey WHERE "alchemerId"::text = '90558103')
  AND sr."NPS_SCORE" BETWEEN 0 AND 10
GROUP BY 1, 2
ORDER BY 1, 2;


-- ---------------------------------------------------------------------------------------------------
-- 03_legacy_responses.csv  -  the 480 real legacy Survey Responses (tick off against the Alchemer export)
-- ---------------------------------------------------------------------------------------------------
SELECT sr."alchemerResponseId"                                         AS actual_alchemer_response_id,
       sr.sguid                                                        AS actual_legacy_sguid,
       (sr."dateStarted" AT TIME ZONE 'Europe/Zagreb')::timestamp(0)   AS actual_survey_started_local,
       (sr."dateSubmitted" AT TIME ZONE 'Europe/Zagreb')::timestamp(0) AS actual_survey_submitted_local,
       sr."NPS_SCORE"                                                  AS actual_score,
       sr.status                                                       AS actual_response_status,
       sr.language                                                     AS actual_response_language,
       p.source_id                                                     AS actual_patient_source_id,
       pv.doctor                                                       AS actual_doctor,
       pv.procedure                                                    AS derived_procedure_from_comment,
       pv.visit_date::date                                             AS est_visit_date,
       (vm.sent_at AT TIME ZONE 'Europe/Zagreb')::timestamp(0)         AS est_sent_local,
       vm.status                                                       AS derived_delivery_status
FROM survey_response sr
JOIN visit_msg vm             ON vm.id = sr.visit_msg_id
JOIN legacy_sending_batch l   ON l.sending_batch_id = vm.sending_batch_id AND l.code = 'SIE_LEGACY_V4'
JOIN patient_visit pv         ON pv.id = vm.patient_visit_id
JOIN patient p                ON p.id = pv.patient_id
ORDER BY sr."dateStarted";


-- ---------------------------------------------------------------------------------------------------
-- 04_legacy_invites.csv  -  all 2692 imported invites, every field labelled
-- ---------------------------------------------------------------------------------------------------
SELECT m.legacy_sguid                                                  AS actual_legacy_sguid,
       p.source_id                                                     AS actual_patient_source_id,
       CASE WHEN p.created = l.loaded_at THEN 'new (created by import)' ELSE 'existing (unchanged)' END AS patient_record,
       pv.doctor                                                       AS actual_doctor,
       pv.comment                                                      AS actual_visit_comment,
       pv.procedure                                                    AS derived_procedure_from_comment,
       CASE WHEN sr.id IS NOT NULL THEN 'actual (patient responded)'
            ELSE 'estimated (quarantine/age replay)' END               AS invite_existence,
       pv.visit_date::date                                             AS est_visit_date,
       (vm.sent_at AT TIME ZONE 'Europe/Zagreb')::timestamp(0)         AS est_sent_local,
       CASE WHEN sr.id IS NOT NULL THEN vm.status END                  AS derived_delivery_status,
       CASE WHEN sr.id IS NULL     THEN vm.status END                  AS est_delivery_status,
       vm.sending_batch_id                                             AS mock_sending_batch_id,
       vm.template_id                                                  AS mock_template_id,
       vm.sms_status_name                                              AS mock_sms_status_name,
       sr."alchemerResponseId"                                         AS actual_alchemer_response_id,
       (sr."dateStarted" AT TIME ZONE 'Europe/Zagreb')::timestamp(0)   AS actual_survey_started_local,
       sr."NPS_SCORE"                                                  AS actual_score,
       sr.status                                                       AS actual_response_status
FROM visit_msg vm
JOIN legacy_sending_batch l   ON l.sending_batch_id = vm.sending_batch_id AND l.code = 'SIE_LEGACY_V4'
JOIN legacy_invite_map m      ON m.visit_msg_id = vm.id
JOIN patient_visit pv         ON pv.id = vm.patient_visit_id
JOIN patient p                ON p.id = pv.patient_id
LEFT JOIN survey_response sr  ON sr.visit_msg_id = vm.id
ORDER BY vm.sent_at;


-- ---------------------------------------------------------------------------------------------------
-- 05_legacy_patients.csv  -  all 2121 legacy Patients (no names/phones), with their legacy visits and invites
-- ---------------------------------------------------------------------------------------------------
WITH l AS (SELECT min(account_id) AS account_id, min(loaded_at) AS loaded_at FROM legacy_sending_batch WHERE code = 'SIE_LEGACY_V4'),
     vis AS (SELECT patient_id, count(*) AS visits FROM legacy_source_row
             WHERE source_file = 'Pacijenti_JOINED_Stomatologija_i_estetika.csv' AND row_kind <> 'platform' GROUP BY 1),
     inv AS (SELECT pv.patient_id, count(*) AS invites, count(sr.id) AS responses
             FROM visit_msg vm
             JOIN legacy_sending_batch lb ON lb.sending_batch_id = vm.sending_batch_id AND lb.code = 'SIE_LEGACY_V4'
             JOIN patient_visit pv ON pv.id = vm.patient_visit_id
             LEFT JOIN survey_response sr ON sr.visit_msg_id = vm.id
             GROUP BY 1)
SELECT p.source_id                                                     AS actual_patient_source_id,
       CASE WHEN p.created = l.loaded_at THEN 'new (created by import)' ELSE 'existing (unchanged)' END AS patient_record,
       p.gender_code                                                   AS actual_gender,
       p.language_code                                                 AS actual_language,
       p.lead_source                                                   AS actual_lead_source,
       p.year_of_birth                                                 AS derived_year_of_birth,
       coalesce(vis.visits, 0)                                         AS legacy_visits,
       coalesce(inv.invites, 0)                                        AS legacy_invites,
       coalesce(inv.responses, 0)                                      AS legacy_responses
FROM patient p
CROSS JOIN l
LEFT JOIN vis ON vis.patient_id = p.id
LEFT JOIN inv ON inv.patient_id = p.id
WHERE p.account_id = l.account_id
  AND p.id IN (SELECT patient_id FROM legacy_source_row
               WHERE source_file = 'Pacijenti_JOINED_Stomatologija_i_estetika.csv' AND row_kind <> 'platform')
ORDER BY p.source_id;


-- ---------------------------------------------------------------------------------------------------
-- 06_legacy_by_doctor.csv
-- ---------------------------------------------------------------------------------------------------
SELECT pv.doctor                                                       AS actual_doctor,
       count(*)                                                        AS invites,
       count(*) FILTER (WHERE vm.status = 'DELIVERED')                 AS delivered,
       count(sr.id)                                                    AS responses,
       floor(1000.0 * count(sr.id) / NULLIF(count(*) FILTER (WHERE vm.status = 'DELIVERED'), 0) + 0.5) / 10 AS est_response_rate_pct,
       floor(1000.0 * (count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9)
                     - count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6)) / NULLIF(count(sr.id), 0) + 0.5) / 10 AS actual_nps
FROM visit_msg vm
JOIN legacy_sending_batch l  ON l.sending_batch_id = vm.sending_batch_id AND l.code = 'SIE_LEGACY_V4'
JOIN patient_visit pv        ON pv.id = vm.patient_visit_id
LEFT JOIN survey_response sr ON sr.visit_msg_id = vm.id AND sr."NPS_SCORE" BETWEEN 0 AND 10
GROUP BY 1
ORDER BY invites DESC;


-- ---------------------------------------------------------------------------------------------------
-- 07_unlinked_responses.csv  -  the 27 responses that cannot be linked, with reason
-- ---------------------------------------------------------------------------------------------------
SELECT sr."alchemerResponseId"                                         AS actual_alchemer_response_id,
       sr.sguid                                                        AS actual_sguid,
       (sr."dateStarted" AT TIME ZONE 'Europe/Zagreb')::timestamp(0)   AS actual_survey_started_local,
       sr."NPS_SCORE"                                                  AS actual_score,
       sr.status                                                       AS actual_response_status,
       CASE WHEN sr.sguid IS NULL           THEN 'no sguid in link'
            WHEN sr.sguid !~ '^[0-9]+$'     THEN 'test link'
            WHEN length(sr.sguid) > 8       THEN 'test-like long id'
            ELSE 'legacy id not in clinic data' END                    AS reason
FROM survey_response sr
JOIN survey s ON s.id = sr."surveyId"
WHERE s."alchemerId"::text = '90558103' AND sr.visit_msg_id IS NULL
ORDER BY sr."dateStarted";


-- ---------------------------------------------------------------------------------------------------
-- 08_mock_sending_batch.csv  -  the single legacy batch and its note
-- ---------------------------------------------------------------------------------------------------
SELECT b.id                                                            AS mock_sending_batch_id,
       (b.sent_at AT TIME ZONE 'Europe/Zagreb')::date                  AS est_first_send_day,
       b.processed_visits                                              AS legacy_visits,
       b.created_messages                                              AS invites,
       b.processed_patients                                            AS patients,
       b.trigger                                                       AS mock_trigger,
       l.comment                                                       AS legacy_note
FROM visit_msg_sending_batch b
JOIN legacy_sending_batch l ON l.sending_batch_id = b.id AND l.code = 'SIE_LEGACY_V4'
ORDER BY b.sent_at;


-- ---------------------------------------------------------------------------------------------------
-- 09_integrity_checks.csv  -  every value must be 0
-- ---------------------------------------------------------------------------------------------------
WITH l AS (SELECT sending_batch_id, account_id, loaded_at FROM legacy_sending_batch WHERE code = 'SIE_LEGACY_V4')
SELECT
  (SELECT count(*) FROM visit_msg WHERE sending_batch_id IN (SELECT sending_batch_id FROM l)
     AND sent_at >= ('2024-10-16'::timestamp AT TIME ZONE 'Europe/Zagreb'))                       AS legacy_after_platform_launch,
  (SELECT count(*) FROM survey_response sr JOIN visit_msg vm ON vm.id = sr.visit_msg_id
     WHERE vm.sending_batch_id IN (SELECT sending_batch_id FROM l) AND sr."dateStarted" < vm.sent_at) AS responses_before_send,
  (SELECT count(*) FROM visit_msg vm WHERE vm.sending_batch_id IN (SELECT sending_batch_id FROM l)
     AND NOT EXISTS (SELECT 1 FROM legacy_invite_map m WHERE m.visit_msg_id = vm.id))               AS legacy_msgs_without_map,
  (SELECT count(*) FROM patient_visit pv JOIN visit_msg vm ON vm.patient_visit_id = pv.id
     WHERE vm.sending_batch_id IN (SELECT sending_batch_id FROM l)
       AND NOT EXISTS (SELECT 1 FROM patient_visit_param x WHERE x.patient_visit_id = pv.id
                       AND x.param = 'ignore_for_survey' AND x.value = 'true'))                    AS legacy_visits_without_ignore_flag,
  (SELECT count(*) FROM patient p WHERE p.account_id = (SELECT min(account_id) FROM l)
     AND p.created < (SELECT min(loaded_at) FROM l) AND p.updated >= (SELECT min(loaded_at) FROM l)) AS existing_patients_changed,
  (SELECT count(*) FROM visit_msg vm WHERE vm.sending_batch_id IN (SELECT sending_batch_id FROM l)
     AND vm.created_at > (SELECT min(loaded_at) FROM l) + interval '1 minute')                     AS new_msgs_sent_into_legacy_batches;


-- ---------------------------------------------------------------------------------------------------
-- 10_legacy_visits_all.csv  -  all 11573 legacy visits (with and without invite), source row -> live data
-- ---------------------------------------------------------------------------------------------------
SELECT r.row_no                                                        AS source_row_no,
       r.row_kind,
       r.raw->>'id'                                                    AS actual_legacy_id,
       r.raw->>'source_id'                                             AS actual_patient_source_id,
       r.raw->>'doctor'                                                AS actual_doctor,
       r.raw->>'comment'                                               AS actual_visit_comment,
       pv.procedure                                                    AS derived_procedure_from_comment,
       pv.visit_date::date                                             AS est_visit_date,
       CASE WHEN r.visit_msg_id IS NOT NULL THEN (vm.sent_at AT TIME ZONE 'Europe/Zagreb')::timestamp(0) END AS est_sent_local,
       vm.status                                                       AS invite_status,
       sr."NPS_SCORE"                                                  AS actual_score,
       r.patient_id, r.patient_visit_id, r.visit_msg_id
FROM legacy_source_row r
JOIN patient_visit pv        ON pv.id = r.patient_visit_id
LEFT JOIN visit_msg vm       ON vm.id = r.visit_msg_id
LEFT JOIN survey_response sr ON sr.visit_msg_id = vm.id
WHERE r.source_file = 'Pacijenti_JOINED_Stomatologija_i_estetika.csv' AND r.row_kind <> 'platform'
ORDER BY pv.visit_date, r.row_no;
