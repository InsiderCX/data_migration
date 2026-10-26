-- =====================================================================================================
-- SIE legacy migration - REPORT QUERIES for Ops: how Clinicdash will show the data per week / month / quarter / year.
-- Read-only. Exact Clinicdash definitions (icx-database metrics: General dashboard, Message performance, NPS Trends):
--   * NPS: scored responses (0-10, any status), dated by survey start ("dateStarted"), rounded half-up to 1 decimal
--   * Message performance: initial invites only, dated by SEND time, response rate = responses / DELIVERED
--   * Week = ISO week starting Monday; time zone Europe/Zagreb
-- Every query starts with the same parameter block (p): change bucket / dates there. Run each query on its own and
-- export it as CSV under the name in its header.
-- `source` column: legacy = imported (SIE_LEGACY_V4), platform = normal platform data.
--   Legacy NPS / responses are REAL. Legacy sent / delivered / response rate are ESTIMATES.
-- =====================================================================================================


-- -----------------------------------------------------------------------------------------------------
-- R1_message_performance.csv  -  Message performance page, per bucket (by SEND date)
-- -----------------------------------------------------------------------------------------------------
WITH p AS (
  SELECT s."accountId"        AS account_id,
         'month'::text        AS bucket,      -- << 'week' (ISO, Monday) | 'month' | 'quarter' | 'year'
         'Europe/Zagreb'::text AS tz,
         DATE '2023-05-01'    AS start_day,   -- << first day (inclusive)
         DATE '2026-10-31'    AS end_day      -- << last day (inclusive)
  FROM survey s WHERE s."alchemerId"::text = '90558103'
),
b AS (SELECT p.*, (p.start_day::timestamp AT TIME ZONE p.tz) AS t0,
                  ((p.end_day::timestamp + interval '1 day' - interval '1 millisecond') AT TIME ZONE p.tz) AS t1 FROM p),
lb AS (SELECT sending_batch_id FROM legacy_sending_batch WHERE code = 'SIE_LEGACY_V4')
SELECT date_trunc(b.bucket, vm.sent_at AT TIME ZONE b.tz)::date                              AS period_start,
       CASE WHEN vm.sending_batch_id IN (SELECT sending_batch_id FROM lb)
            THEN 'legacy (sent/delivered estimated)' ELSE 'platform' END                       AS source,
       count(*)                                                                             AS messages_sent,
       count(*) FILTER (WHERE vm.status = 'DELIVERED')                                      AS delivered,
       count(*) FILTER (WHERE r."NPS_SCORE" BETWEEN 0 AND 10)                               AS responses,
       count(*) FILTER (WHERE r."NPS_SCORE" BETWEEN 0 AND 10 AND r.status = 'Complete')     AS completed,
       CASE WHEN count(*) = 0 THEN 0 ELSE floor(1000.0 * count(*) FILTER (WHERE vm.status = 'DELIVERED') / count(*) + 0.5) / 10 END AS delivery_rate,
       CASE WHEN count(*) FILTER (WHERE vm.status = 'DELIVERED') = 0 THEN 0
            ELSE floor(1000.0 * count(*) FILTER (WHERE r."NPS_SCORE" BETWEEN 0 AND 10)
                       / count(*) FILTER (WHERE vm.status = 'DELIVERED') + 0.5) / 10 END     AS response_rate,
       CASE WHEN count(*) FILTER (WHERE r."NPS_SCORE" BETWEEN 0 AND 10) = 0 THEN 0
            ELSE floor(1000.0 * count(*) FILTER (WHERE r."NPS_SCORE" BETWEEN 0 AND 10 AND r.status = 'Complete')
                       / count(*) FILTER (WHERE r."NPS_SCORE" BETWEEN 0 AND 10) + 0.5) / 10 END AS completion_rate
FROM b
JOIN visit_msg vm ON vm.account_id = b.account_id AND vm.id = vm.invite_id AND vm.sent_at IS NOT NULL
                 AND vm.sent_at >= b.t0 AND vm.sent_at <= b.t1
LEFT JOIN survey_response r ON r.visit_msg_id = vm.id
GROUP BY 1, 2
ORDER BY 1, 2;


-- -----------------------------------------------------------------------------------------------------
-- R2_nps_trends.csv  -  NPS Trends page + General dashboard KPIs, per bucket (by SURVEY START date)
-- -----------------------------------------------------------------------------------------------------
WITH p AS (
  SELECT s."accountId"        AS account_id,
         'month'::text        AS bucket,      -- << 'week' (ISO, Monday) | 'month' | 'quarter' | 'year'
         'Europe/Zagreb'::text AS tz,
         DATE '2023-05-01'    AS start_day,   -- << first day (inclusive)
         DATE '2026-10-31'    AS end_day      -- << last day (inclusive)
  FROM survey s WHERE s."alchemerId"::text = '90558103'
),
b AS (SELECT p.*, (p.start_day::timestamp AT TIME ZONE p.tz) AS t0,
                  ((p.end_day::timestamp + interval '1 day' - interval '1 millisecond') AT TIME ZONE p.tz) AS t1 FROM p),
lb AS (SELECT sending_batch_id FROM legacy_sending_batch WHERE code = 'SIE_LEGACY_V4')
SELECT date_trunc(b.bucket, sr."dateStarted" AT TIME ZONE b.tz)::date                     AS period_start,
       CASE WHEN vm.sending_batch_id IN (SELECT sending_batch_id FROM lb) THEN 'legacy' ELSE 'platform' END AS source,
       count(*)                                                                          AS responses,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9)                                AS promoters,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") BETWEEN 7 AND 8)                     AS passives,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6)                                AS detractors,
       floor(1000.0 * count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9) / count(*) + 0.5) / 10            AS promoters_pct,
       floor(1000.0 * count(*) FILTER (WHERE round(sr."NPS_SCORE") BETWEEN 7 AND 8) / count(*) + 0.5) / 10 AS passives_pct,
       floor(1000.0 * count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6) / count(*) + 0.5) / 10            AS detractors_pct,
       floor(1000.0 * (count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9)
                     - count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6)) / count(*) + 0.5) / 10          AS nps
FROM b
JOIN visit_msg vm       ON vm.account_id = b.account_id
JOIN survey_response sr ON sr.visit_msg_id = vm.id
WHERE sr."NPS_SCORE" BETWEEN 0 AND 10 AND sr."dateStarted" IS NOT NULL
  AND sr."dateStarted" >= b.t0 AND sr."dateStarted" <= b.t1
GROUP BY 1, 2
ORDER BY 1, 2;


-- -----------------------------------------------------------------------------------------------------
-- R3_nps_trends_total.csv  -  same as R2 but legacy + platform combined (what the dashboard line shows)
-- -----------------------------------------------------------------------------------------------------
WITH p AS (
  SELECT s."accountId"        AS account_id,
         'month'::text        AS bucket,      -- << 'week' (ISO, Monday) | 'month' | 'quarter' | 'year'
         'Europe/Zagreb'::text AS tz,
         DATE '2023-05-01'    AS start_day,   -- << first day (inclusive)
         DATE '2026-10-31'    AS end_day      -- << last day (inclusive)
  FROM survey s WHERE s."alchemerId"::text = '90558103'
),
b AS (SELECT p.*, (p.start_day::timestamp AT TIME ZONE p.tz) AS t0,
                  ((p.end_day::timestamp + interval '1 day' - interval '1 millisecond') AT TIME ZONE p.tz) AS t1 FROM p),
lb AS (SELECT sending_batch_id FROM legacy_sending_batch WHERE code = 'SIE_LEGACY_V4')
SELECT date_trunc(b.bucket, sr."dateStarted" AT TIME ZONE b.tz)::date                     AS period_start,
       count(*)                                                                          AS responses,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9)                                AS promoters,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6)                                AS detractors,
       floor(1000.0 * (count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9)
                     - count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6)) / count(*) + 0.5) / 10 AS nps,
       bool_or(vm.sending_batch_id IN (SELECT sending_batch_id FROM lb))                 AS contains_legacy
FROM b
JOIN visit_msg vm       ON vm.account_id = b.account_id
JOIN survey_response sr ON sr.visit_msg_id = vm.id
WHERE sr."NPS_SCORE" BETWEEN 0 AND 10 AND sr."dateStarted" IS NOT NULL
  AND sr."dateStarted" >= b.t0 AND sr."dateStarted" <= b.t1
GROUP BY 1
ORDER BY 1;


-- -----------------------------------------------------------------------------------------------------
-- R4_score_distribution.csv  -  General dashboard "NPS score distribution" (count per score 0-10), per bucket
-- -----------------------------------------------------------------------------------------------------
WITH p AS (
  SELECT s."accountId"        AS account_id,
         'month'::text        AS bucket,      -- << 'week' (ISO, Monday) | 'month' | 'quarter' | 'year'
         'Europe/Zagreb'::text AS tz,
         DATE '2023-05-01'    AS start_day,   -- << first day (inclusive)
         DATE '2026-10-31'    AS end_day      -- << last day (inclusive)
  FROM survey s WHERE s."alchemerId"::text = '90558103'
),
b AS (SELECT p.*, (p.start_day::timestamp AT TIME ZONE p.tz) AS t0,
                  ((p.end_day::timestamp + interval '1 day' - interval '1 millisecond') AT TIME ZONE p.tz) AS t1 FROM p),
lb AS (SELECT sending_batch_id FROM legacy_sending_batch WHERE code = 'SIE_LEGACY_V4')
SELECT date_trunc(b.bucket, sr."dateStarted" AT TIME ZONE b.tz)::date AS period_start,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") = 0) AS s0, count(*) FILTER (WHERE round(sr."NPS_SCORE") = 1) AS s1, count(*) FILTER (WHERE round(sr."NPS_SCORE") = 2) AS s2, count(*) FILTER (WHERE round(sr."NPS_SCORE") = 3) AS s3, count(*) FILTER (WHERE round(sr."NPS_SCORE") = 4) AS s4, count(*) FILTER (WHERE round(sr."NPS_SCORE") = 5) AS s5, count(*) FILTER (WHERE round(sr."NPS_SCORE") = 6) AS s6, count(*) FILTER (WHERE round(sr."NPS_SCORE") = 7) AS s7, count(*) FILTER (WHERE round(sr."NPS_SCORE") = 8) AS s8, count(*) FILTER (WHERE round(sr."NPS_SCORE") = 9) AS s9, count(*) FILTER (WHERE round(sr."NPS_SCORE") = 10) AS s10,
       count(*) AS responses
FROM b
JOIN visit_msg vm       ON vm.account_id = b.account_id
JOIN survey_response sr ON sr.visit_msg_id = vm.id
WHERE sr."NPS_SCORE" BETWEEN 0 AND 10 AND sr."dateStarted" >= b.t0 AND sr."dateStarted" <= b.t1
GROUP BY 1
ORDER BY 1;


-- -----------------------------------------------------------------------------------------------------
-- R5_breakdown.csv  -  NPS Trends "Breakdown" tab for the whole date range: gender, age band, procedure, doctor
--                      (procedure for legacy visits is DERIVED from the visit comment)
-- -----------------------------------------------------------------------------------------------------
WITH p AS (
  SELECT s."accountId"        AS account_id,
         'month'::text        AS bucket,      -- << 'week' (ISO, Monday) | 'month' | 'quarter' | 'year'
         'Europe/Zagreb'::text AS tz,
         DATE '2023-05-01'    AS start_day,   -- << first day (inclusive)
         DATE '2026-10-31'    AS end_day      -- << last day (inclusive)
  FROM survey s WHERE s."alchemerId"::text = '90558103'
),
b AS (SELECT p.*, (p.start_day::timestamp AT TIME ZONE p.tz) AS t0,
                  ((p.end_day::timestamp + interval '1 day' - interval '1 millisecond') AT TIME ZONE p.tz) AS t1 FROM p),
lb AS (SELECT sending_batch_id FROM legacy_sending_batch WHERE code = 'SIE_LEGACY_V4'),
base AS (
  SELECT sr."NPS_SCORE", sr."dateStarted", p2.gender_code, p2.year_of_birth, pv.procedure, pv.doctor,
         CASE WHEN vm.sending_batch_id IN (SELECT sending_batch_id FROM lb) THEN 'legacy' ELSE 'platform' END AS source
  FROM b
  JOIN visit_msg vm       ON vm.account_id = b.account_id
  JOIN survey_response sr ON sr.visit_msg_id = vm.id
  JOIN patient_visit pv   ON pv.id = vm.patient_visit_id
  JOIN patient p2         ON p2.id = pv.patient_id
  WHERE sr."NPS_SCORE" BETWEEN 0 AND 10 AND sr."dateStarted" >= b.t0 AND sr."dateStarted" <= b.t1
),
seg AS (
  SELECT 'gender' AS breakdown, coalesce(gender_code::text, 'unknown') AS segment, source, "NPS_SCORE" FROM base
  UNION ALL
  SELECT 'age band', CASE WHEN year_of_birth IS NULL THEN 'unknown'
           WHEN extract(year FROM "dateStarted") - year_of_birth <= 17 THEN '0-17'
           WHEN extract(year FROM "dateStarted") - year_of_birth <= 30 THEN '18-30'
           WHEN extract(year FROM "dateStarted") - year_of_birth <= 40 THEN '31-40'
           WHEN extract(year FROM "dateStarted") - year_of_birth <= 50 THEN '41-50'
           WHEN extract(year FROM "dateStarted") - year_of_birth <= 60 THEN '51-60'
           WHEN extract(year FROM "dateStarted") - year_of_birth <= 70 THEN '61-70'
           WHEN extract(year FROM "dateStarted") - year_of_birth <= 80 THEN '71-80' ELSE '81+' END, source, "NPS_SCORE" FROM base
  UNION ALL
  SELECT 'procedure', coalesce(nullif(procedure, ''), 'unknown'), source, "NPS_SCORE" FROM base
  UNION ALL
  SELECT 'doctor', doctor, source, "NPS_SCORE" FROM base WHERE nullif(doctor, '') IS NOT NULL
)
SELECT breakdown, segment, source,
       count(*) AS responses,
       count(*) FILTER (WHERE round("NPS_SCORE") >= 9) AS promoters,
       count(*) FILTER (WHERE round("NPS_SCORE") <= 6) AS detractors,
       floor(1000.0 * (count(*) FILTER (WHERE round("NPS_SCORE") >= 9)
                     - count(*) FILTER (WHERE round("NPS_SCORE") <= 6)) / count(*) + 0.5) / 10 AS nps
FROM seg
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;


-- -----------------------------------------------------------------------------------------------------
-- R6_visits_and_patients.csv  -  Patient Visits per bucket (not a Clinicdash KPI; shows the 11,573 legacy visits)
-- -----------------------------------------------------------------------------------------------------
WITH p AS (
  SELECT s."accountId"        AS account_id,
         'month'::text        AS bucket,      -- << 'week' (ISO, Monday) | 'month' | 'quarter' | 'year'
         'Europe/Zagreb'::text AS tz,
         DATE '2023-05-01'    AS start_day,   -- << first day (inclusive)
         DATE '2026-10-31'    AS end_day      -- << last day (inclusive)
  FROM survey s WHERE s."alchemerId"::text = '90558103'
),
b AS (SELECT p.*, (p.start_day::timestamp AT TIME ZONE p.tz) AS t0,
                  ((p.end_day::timestamp + interval '1 day' - interval '1 millisecond') AT TIME ZONE p.tz) AS t1 FROM p),
lb AS (SELECT sending_batch_id FROM legacy_sending_batch WHERE code = 'SIE_LEGACY_V4'),
lv AS (SELECT patient_visit_id FROM legacy_source_row
       WHERE source_file = 'Pacijenti_JOINED_Stomatologija_i_estetika.csv' AND row_kind <> 'platform')
SELECT date_trunc(b.bucket, pv.visit_date AT TIME ZONE 'UTC')::date AS period_start,   -- visit_date holds local wall-clock labelled UTC
       CASE WHEN pv.id IN (SELECT patient_visit_id FROM lv) THEN 'legacy (visit date estimated)' ELSE 'platform' END AS source,
       count(*)                                    AS visits,
       count(DISTINCT pv.patient_id)               AS patients,
       count(vm.id)                                AS visits_with_invite,
       count(*) FILTER (WHERE pv.procedure = 'Prvi pregled') AS prvi_pregled,
       count(*) FILTER (WHERE pv.procedure = 'Zahvat')       AS zahvat
FROM b
JOIN patient_visit pv ON pv.account_id = b.account_id
LEFT JOIN visit_msg vm ON vm.patient_visit_id = pv.id AND vm.id = vm.invite_id
WHERE pv.visit_date AT TIME ZONE 'UTC' >= b.start_day AND pv.visit_date AT TIME ZONE 'UTC' < b.end_day + 1
GROUP BY 1, 2
ORDER BY 1, 2;


-- -----------------------------------------------------------------------------------------------------
-- R7_db_vs_bi_by_month.csv  -  monthly responses / NPS: database (as Clinicdash) vs current BI system
--   BI values = Joined.csv (Alchemer export, cut-off 21 Oct 2026 14:31). Month buckets only.
--   Expect identical rows on prod after the load; on an older stg copy the latest months can be lower.
-- -----------------------------------------------------------------------------------------------------
WITH bi(period_start, bi_responses, bi_promoters, bi_detractors) AS (VALUES
  (DATE '2023-05-01', 71, 63, 4),
  (DATE '2023-06-01', 39, 38, 1),
  (DATE '2023-07-01', 24, 22, 0),
  (DATE '2023-08-01', 30, 27, 1),
  (DATE '2023-09-01', 33, 31, 1),
  (DATE '2023-10-01', 19, 17, 1),
  (DATE '2023-11-01', 24, 20, 2),
  (DATE '2023-12-01', 15, 14, 0),
  (DATE '2024-02-01', 51, 44, 1),
  (DATE '2024-03-01', 26, 23, 3),
  (DATE '2024-04-01', 16, 15, 1),
  (DATE '2024-05-01', 28, 26, 0),
  (DATE '2024-06-01', 27, 26, 1),
  (DATE '2024-07-01', 25, 24, 1),
  (DATE '2024-08-01', 20, 19, 1),
  (DATE '2024-09-01', 23, 18, 3),
  (DATE '2024-10-01', 29, 28, 1),
  (DATE '2024-11-01', 18, 17, 0),
  (DATE '2024-12-01', 14, 9, 1),
  (DATE '2025-01-01', 7, 7, 0),
  (DATE '2025-02-01', 22, 21, 1),
  (DATE '2025-03-01', 13, 12, 1),
  (DATE '2025-04-01', 22, 20, 0),
  (DATE '2025-05-01', 9, 8, 0),
  (DATE '2025-06-01', 10, 10, 0),
  (DATE '2025-07-01', 25, 22, 1),
  (DATE '2025-08-01', 7, 6, 0),
  (DATE '2025-09-01', 13, 13, 0),
  (DATE '2025-10-01', 23, 22, 0),
  (DATE '2025-11-01', 13, 12, 1),
  (DATE '2025-12-01', 16, 16, 0),
  (DATE '2026-01-01', 11, 9, 2),
  (DATE '2026-02-01', 13, 12, 1),
  (DATE '2026-03-01', 20, 19, 0),
  (DATE '2026-04-01', 15, 14, 0),
  (DATE '2026-05-01', 16, 14, 1),
  (DATE '2026-06-01', 9, 9, 0),
  (DATE '2026-07-01', 13, 13, 0),
  (DATE '2026-08-01', 12, 12, 0),
  (DATE '2026-09-01', 27, 27, 0),
  (DATE '2026-10-01', 15, 14, 1)
),
acc AS (SELECT "accountId" AS account_id FROM survey WHERE "alchemerId"::text = '90558103'),
db AS (
  SELECT date_trunc('month', sr."dateStarted" AT TIME ZONE 'Europe/Zagreb')::date AS period_start,
         count(*) AS db_responses,
         count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9) AS db_promoters,
         count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6) AS db_detractors
  FROM acc
  JOIN visit_msg vm       ON vm.account_id = acc.account_id
  JOIN survey_response sr ON sr.visit_msg_id = vm.id
  WHERE sr."NPS_SCORE" BETWEEN 0 AND 10
    AND sr."dateStarted" < ('2026-10-21 14:31'::timestamp AT TIME ZONE 'Europe/Zagreb')
  GROUP BY 1
)
SELECT coalesce(bi.period_start, db.period_start) AS period_start,
       bi.bi_responses, db.db_responses,
       floor(1000.0 * (bi.bi_promoters - bi.bi_detractors) / NULLIF(bi.bi_responses, 0) + 0.5) / 10 AS bi_nps,
       floor(1000.0 * (db.db_promoters - db.db_detractors) / NULLIF(db.db_responses, 0) + 0.5) / 10 AS db_nps,
       CASE WHEN bi.bi_responses IS NOT DISTINCT FROM db.db_responses
             AND bi.bi_promoters IS NOT DISTINCT FROM db.db_promoters
             AND bi.bi_detractors IS NOT DISTINCT FROM db.db_detractors THEN 'match' ELSE 'DIFFERENT' END AS check_result
FROM bi FULL JOIN db ON db.period_start = bi.period_start
ORDER BY 1;
