-- Stomatološka poliklinika Apolonija legacy import (APOLONIJA_LEGACY_V1). Rendered by tools/render_legacy_sql.py from sql_config.json - do not edit by hand.
-- Part 3: validation (read-only). Run each query on its own.

-- 1) Summary: expect 67895 source rows, 30899 legacy visits, 10516 invites, 1517 linked,
--    0 existing Patients changed, 0 legacy rows without Patient, 0 Deleted responses linked
WITH r AS (SELECT * FROM legacy_source_row WHERE source_file = 'Pacijenti_JOINED_Apolonija.csv'
             AND account_id = (SELECT "accountId" FROM survey WHERE "alchemerId"::text = '90492576')),
     b AS (SELECT * FROM legacy_sending_batch WHERE code = 'APOLONIJA_LEGACY_V1')
SELECT (SELECT count(*) FROM r)                                                          AS source_rows,
       (SELECT count(*) FROM r WHERE row_kind IN ('legacy_invite','legacy_visit') AND patient_visit_id IS NOT NULL) AS legacy_visits,
       (SELECT count(*) FROM visit_msg WHERE sending_batch_id IN (SELECT sending_batch_id FROM b)) AS legacy_invites,
       (SELECT count(*) FROM survey_response sr JOIN visit_msg vm ON vm.id = sr.visit_msg_id
          WHERE vm.sending_batch_id IN (SELECT sending_batch_id FROM b))                 AS linked_responses,
       (SELECT count(*) FROM survey_response sr JOIN visit_msg vm ON vm.id = sr.visit_msg_id
          WHERE vm.sending_batch_id IN (SELECT sending_batch_id FROM b) AND sr.status = 'Deleted') AS deleted_linked,
       (SELECT count(*) FROM r WHERE row_kind = 'platform' AND visit_msg_id IS NOT NULL) AS platform_rows_linked,
       (SELECT count(*) FROM patient p WHERE p.account_id = (SELECT min(account_id) FROM b)
          AND p.created < (SELECT min(loaded_at) FROM b) AND p.updated >= (SELECT min(loaded_at) FROM b)) AS existing_patients_changed,
       (SELECT count(*) FROM patient p WHERE p.account_id = (SELECT min(account_id) FROM b)
          AND p.created = (SELECT min(loaded_at) FROM b))                                AS new_patients,
       (SELECT count(*) FROM r WHERE row_kind IN ('legacy_invite','legacy_visit') AND patient_id IS NULL) AS legacy_rows_without_patient,
       (SELECT count(*) FROM survey_response sr JOIN survey s ON s.id = sr."surveyId"
          WHERE s."alchemerId"::text = '90492576' AND sr.visit_msg_id IS NULL)              AS still_unlinked;

-- 2) Message performance, legacy quarters (sent/delivered ESTIMATED, responses real)
SELECT date_trunc('quarter', vm.sent_at AT TIME ZONE 'Europe/Zagreb')::date AS quarter,
       count(*) AS sent,
       count(*) FILTER (WHERE vm.status = 'DELIVERED') AS delivered,
       count(r.id) AS responses,
       floor(1000.0 * count(r.id) / NULLIF(count(*) FILTER (WHERE vm.status = 'DELIVERED'), 0) + 0.5) / 10 AS response_rate
FROM visit_msg vm
LEFT JOIN survey_response r ON r.visit_msg_id = vm.id
WHERE vm.sending_batch_id IN (SELECT sending_batch_id FROM legacy_sending_batch WHERE code = 'APOLONIJA_LEGACY_V1') AND vm.id = vm.invite_id
GROUP BY 1 ORDER BY 1;

-- 3) Legacy NPS (real): responses / promoters / detractors / NPS
SELECT count(*) AS responses,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9) AS promoters,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6) AS detractors,
       floor(1000.0 * (count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9)
                     - count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6)) / NULLIF(count(*), 0) + 0.5) / 10 AS nps
FROM survey_response sr
JOIN visit_msg vm ON vm.id = sr.visit_msg_id
WHERE vm.sending_batch_id IN (SELECT sending_batch_id FROM legacy_sending_batch WHERE code = 'APOLONIJA_LEGACY_V1') AND sr."NPS_SCORE" BETWEEN 0 AND 10;

-- When satisfied: DROP TABLE public.stg_apolonija_full;   -- contains PII
