-- Ops lists: every initial survey invite sent and every survey response of the account, read-only.
-- Run each query on its own and export as CSV (comma, header, UTF-8) under the file name in its header,
-- then build the Excel with:  python3 scripts/3_build_ops_workbook.py invites.csv responses.csv out.xlsx
-- No patient names, phones or comments. Legacy rows: send date, visit date and (without a response) status are ESTIMATED.

-- -----------------------------------------------------------------------------------------------------
-- invites.csv  -  every initial invite that was sent (legacy + platform), with its response if any
-- -----------------------------------------------------------------------------------------------------
WITH acc AS (SELECT "accountId" AS account_id, id AS survey_id FROM survey WHERE "alchemerId"::text = '90558103'),
lb AS (SELECT sending_batch_id FROM legacy_sending_batch WHERE code = 'SIE_LEGACY_V4'),
lm AS (SELECT visit_msg_id, legacy_sguid FROM legacy_invite_map WHERE account_id = (SELECT account_id FROM acc))
SELECT vm.id::text                                                         AS invite_id,
       coalesce(lm.legacy_sguid, '')                                       AS legacy_invite_id,
       CASE WHEN vm.sending_batch_id IN (SELECT sending_batch_id FROM lb) THEN 'legacy' ELSE 'platform' END AS source,
       to_char(vm.sent_at AT TIME ZONE 'Europe/Zagreb', 'YYYY-MM-DD HH24:MI:SS') AS sent_local,
       CASE WHEN vm.sending_batch_id IN (SELECT sending_batch_id FROM lb) THEN 'estimated' ELSE 'actual' END AS sent_date_is,
       vm.status,
       CASE WHEN vm.sending_batch_id NOT IN (SELECT sending_batch_id FROM lb) THEN 'actual'
            WHEN sr.id IS NOT NULL THEN 'actual (patient responded)' ELSE 'estimated' END AS status_is,
       to_char(pv.visit_date AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI')     AS visit_local,      -- stored as local wall-clock
       CASE WHEN vm.sending_batch_id IN (SELECT sending_batch_id FROM lb) THEN 'estimated' ELSE 'actual' END AS visit_date_is,
       coalesce(pv.doctor, '')                                             AS doctor,
       coalesce(pv.procedure, '')                                          AS procedure,
       CASE WHEN vm.sending_batch_id IN (SELECT sending_batch_id FROM lb) THEN 'derived from comment' ELSE 'actual' END AS procedure_is,
       CASE WHEN sr.id IS NOT NULL THEN 'yes' ELSE 'no' END                AS responded,
       coalesce(sr."alchemerResponseId", '')                               AS alchemer_response_id,
       CASE WHEN sr."NPS_SCORE" BETWEEN 0 AND 10 THEN round(sr."NPS_SCORE")::int END AS score,
       coalesce(sr.status, '')                                             AS response_status,
       coalesce(to_char(sr."dateStarted" AT TIME ZONE 'Europe/Zagreb', 'YYYY-MM-DD HH24:MI:SS'), '') AS survey_started_local,
       to_char(vm.sent_at AT TIME ZONE 'Europe/Zagreb', 'YYYY-MM')         AS send_month
FROM acc
JOIN visit_msg vm      ON vm.account_id = acc.account_id AND vm.id = vm.invite_id AND vm.sent_at IS NOT NULL
JOIN patient_visit pv  ON pv.id = vm.patient_visit_id
LEFT JOIN lm           ON lm.visit_msg_id = vm.id
LEFT JOIN survey_response sr ON sr.visit_msg_id = vm.id
ORDER BY vm.sent_at, vm.id;


-- -----------------------------------------------------------------------------------------------------
-- responses.csv  -  every response of the account's survey(s), incl. the ones dashboards cannot show
-- -----------------------------------------------------------------------------------------------------
WITH acc AS (SELECT "accountId" AS account_id FROM survey WHERE "alchemerId"::text = '90558103'),
lb AS (SELECT sending_batch_id FROM legacy_sending_batch WHERE code = 'SIE_LEGACY_V4')
SELECT sr."alchemerResponseId"                                             AS alchemer_response_id,
       coalesce(sr.sguid, '')                                              AS sguid,
       CASE WHEN vm.id IS NULL THEN 'not linkable'
            WHEN vm.sending_batch_id IN (SELECT sending_batch_id FROM lb) THEN 'legacy' ELSE 'platform' END AS kind,
       coalesce(sr.status, '')                                             AS status,
       CASE WHEN sr."NPS_SCORE" BETWEEN 0 AND 10 THEN round(sr."NPS_SCORE")::int END AS score,
       coalesce(to_char(sr."dateStarted"   AT TIME ZONE 'Europe/Zagreb', 'YYYY-MM-DD HH24:MI:SS'), '') AS started_local,
       coalesce(to_char(sr."dateSubmitted" AT TIME ZONE 'Europe/Zagreb', 'YYYY-MM-DD HH24:MI:SS'), '') AS submitted_local,
       coalesce(sr.language, '')                                           AS language,
       CASE WHEN vm.id IS NOT NULL AND sr."NPS_SCORE" BETWEEN 0 AND 10 THEN 'yes' ELSE 'no' END AS shown,
       CASE WHEN vm.id IS NOT NULL AND sr."NPS_SCORE" BETWEEN 0 AND 10 THEN ''
            WHEN vm.id IS NOT NULL THEN 'no score'
            WHEN sr.sguid IS NULL OR sr.sguid = '' THEN 'no sguid in survey link'
            WHEN sr.sguid !~ '^[0-9]+$' THEN 'test link'
            WHEN length(sr.sguid) > 8 THEN 'test-like long id'
            ELSE 'legacy id not in clinic file' END                        AS reason,
       coalesce(vm.id::text, '')                                           AS invite_id_after_import,
       ''                                                                  AS in_bi,            -- filled by the workbook script from the BI export
       coalesce(to_char(sr."dateStarted" AT TIME ZONE 'Europe/Zagreb', 'YYYY-MM'), '') AS start_month,
       coalesce(sr.comment_sentiment, '')                                  AS comment_sentiment
FROM survey_response sr
JOIN survey s ON s.id = sr."surveyId" AND s."accountId" = (SELECT account_id FROM acc)
LEFT JOIN visit_msg vm ON vm.id = sr.visit_msg_id
ORDER BY sr."alchemerResponseId"::int;
