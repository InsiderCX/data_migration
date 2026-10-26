-- Re-create Pacijenti_JOINED_Stomatologija_i_estetika.csv exactly (same 14,254 rows, order, columns and values).
-- Export the result as CSV (comma, header on, UTF-8). Contains Patient PII - handle like the original file.
SELECT raw->>'id'                  AS "id",
       raw->>'first_name'          AS first_name,
       raw->>'last_name'           AS last_name,
       raw->>'source_id'           AS source_id,
       raw->>'phone'               AS phone,
       raw->>'lead_source'         AS lead_source,
       raw->>'year_of_birth'       AS year_of_birth,
       raw->>'gender_code'         AS gender_code,
       raw->>'country_code'        AS country_code,
       raw->>'language_code'       AS language_code,
       raw->>'visit_date'          AS visit_date,
       raw->>'procedure'           AS "procedure",
       raw->>'comment'             AS "comment",
       raw->>'doctor'              AS doctor,
       raw->>'status'              AS status,
       raw->>'accommodation'       AS accommodation,
       raw->>'organized_transport' AS organized_transport,
       raw->>'age'                 AS age
FROM legacy_source_row
WHERE source_file = 'Pacijenti_JOINED_Stomatologija_i_estetika.csv'
  AND account_id = (SELECT "accountId" FROM survey WHERE "alchemerId"::text = '90558103')
ORDER BY row_no;

-- Same rows, plus where each one lives in the live data now:
-- SELECT row_no, row_kind, raw->>'id' AS id, raw->>'source_id' AS source_id,
--        patient_id, patient_visit_id, visit_msg_id, sending_batch_id
-- FROM legacy_source_row WHERE source_file = 'Pacijenti_JOINED_Stomatologija_i_estetika.csv' ORDER BY row_no;
