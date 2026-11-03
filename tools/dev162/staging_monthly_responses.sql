-- Monthly legacy responses on staging (read-only), for the comparison with Zoho. psql -v al=<alchemer id> -v start=<platform start date> -f this file
SELECT to_char(sr."dateStarted" AT TIME ZONE 'Europe/Zagreb', 'YYYY-MM') AS ym,
       count(*) AS db_all,
       count(*) FILTER (WHERE l.code IS NOT NULL) AS linked,
       count(*) FILTER (WHERE l.code IS NOT NULL AND round(sr."NPS_SCORE") >= 9) AS linked_prom,
       count(*) FILTER (WHERE l.code IS NOT NULL AND round(sr."NPS_SCORE") <= 6) AS linked_detr,
       count(*) FILTER (WHERE l.code IS NOT NULL AND NOT (sr."NPS_SCORE" BETWEEN 0 AND 10)) AS linked_noscore,
       count(*) FILTER (WHERE sr.status <> 'Deleted' AND NOT coalesce(sr."isTestData", false)) AS db_not_deleted_not_test,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9 AND sr.status <> 'Deleted') AS all_prom,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6 AND sr.status <> 'Deleted') AS all_detr
FROM survey_response sr JOIN survey s ON s.id = sr."surveyId"
LEFT JOIN visit_msg vm ON vm.id = sr.visit_msg_id
LEFT JOIN legacy_sending_batch l ON l.sending_batch_id = vm.sending_batch_id
WHERE s."alchemerId" = :'al' AND sr."dateStarted" < (:'start'::timestamp AT TIME ZONE 'Europe/Zagreb')
GROUP BY 1 ORDER BY 1;
