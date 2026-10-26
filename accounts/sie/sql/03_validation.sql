-- SIE legacy full migration v4, Part 3: validation (read-only). Run each query on its own.

-- 1) Summary: expect 14254 source rows, 11573 legacy visits, 2692 invites, 480 linked, 0 existing patients changed,
--    27 unlinked, 2121 legacy patients present / 0 missing
WITH r AS (SELECT * FROM legacy_source_row WHERE source_file = 'Pacijenti_JOINED_Stomatologija_i_estetika.csv'),
     b AS (SELECT * FROM legacy_sending_batch WHERE code = 'SIE_LEGACY_V4')
SELECT (SELECT count(*) FROM r)                                                         AS source_rows,
       (SELECT count(*) FROM r WHERE row_kind <> 'platform' AND patient_visit_id IS NOT NULL) AS legacy_visits,
       (SELECT count(*) FROM visit_msg WHERE sending_batch_id IN (SELECT sending_batch_id FROM b)) AS legacy_invites,
       (SELECT count(*) FROM survey_response sr JOIN visit_msg vm ON vm.id = sr.visit_msg_id
          WHERE vm.sending_batch_id IN (SELECT sending_batch_id FROM b))                AS linked_responses,
       (SELECT count(*) FROM r WHERE row_kind = 'platform' AND visit_msg_id IS NOT NULL) AS platform_rows_linked,
       (SELECT count(*) FROM patient p WHERE p.account_id = (SELECT min(account_id) FROM b)
          AND p.created < (SELECT min(loaded_at) FROM b) AND p.updated >= (SELECT min(loaded_at) FROM b)) AS existing_patients_changed,
       (SELECT count(*) FROM survey_response sr JOIN survey s ON s.id = sr."surveyId"
          WHERE s."alchemerId"::text = '90558103' AND sr.visit_msg_id IS NULL)          AS unlinked,
       (SELECT count(DISTINCT raw->>'source_id') FROM r WHERE row_kind <> 'platform' AND patient_id IS NOT NULL) AS legacy_patients_present,
       (SELECT count(DISTINCT raw->>'source_id') FROM r WHERE row_kind <> 'platform' AND patient_id IS NULL)     AS legacy_patients_missing;

-- 2) Message performance, legacy quarters (same as validated before)
--    2023Q2 543/520/113 21.7 | 2023Q3 456/446/86 19.3 | 2023Q4 477/455/57 12.5 | 2024Q1 414/400/78 19.5
--    2024Q2 367/347/69 19.9  | 2024Q3 361/352/68 19.3 | 2024Q4 74/72/9 12.5
SELECT date_trunc('quarter', vm.sent_at AT TIME ZONE 'Europe/Zagreb')::date AS quarter,
       count(*) AS sent,
       count(*) FILTER (WHERE vm.status = 'DELIVERED') AS delivered,
       count(*) FILTER (WHERE r."NPS_SCORE" BETWEEN 0 AND 10) AS responses,
       floor(1000.0 * count(*) FILTER (WHERE r."NPS_SCORE" BETWEEN 0 AND 10)
             / NULLIF(count(*) FILTER (WHERE vm.status = 'DELIVERED'), 0) + 0.5) / 10 AS response_rate
FROM visit_msg vm
JOIN legacy_sending_batch l ON l.sending_batch_id = vm.sending_batch_id AND l.code = 'SIE_LEGACY_V4'
LEFT JOIN survey_response r ON r.visit_msg_id = vm.id
WHERE vm.id = vm.invite_id
GROUP BY 1 ORDER BY 1;

-- 3) Legacy NPS: expect 480 / 436 / 21 / 86.5
SELECT count(*) AS responses,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9) AS promoters,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6) AS detractors,
       floor(1000.0 * (count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9)
                     - count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6)) / count(*) + 0.5) / 10 AS nps
FROM survey_response sr
JOIN visit_msg vm ON vm.id = sr.visit_msg_id
JOIN legacy_sending_batch l ON l.sending_batch_id = vm.sending_batch_id AND l.code = 'SIE_LEGACY_V4'
WHERE sr."NPS_SCORE" BETWEEN 0 AND 10;

-- When satisfied: DROP TABLE public.stg_sie_full;   -- contains PII
