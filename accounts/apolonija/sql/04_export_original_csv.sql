-- Stomatološka poliklinika Apolonija legacy import (APOLONIJA_LEGACY_V1). Rendered by tools/render_legacy_sql.py from sql_config.json - do not edit by hand.
-- Re-create Pacijenti_JOINED_Apolonija.csv (same 67895 rows, order, columns and values).
-- Export the result as CSV (comma, header on, UTF-8). Contains Patient PII - handle like the original file.
-- Compare by value with the clinic file: some values are quoted in the original where no quotes are needed, and the
-- export tool decides its own quoting, so a byte compare can differ while every value is identical.
SELECT raw->>'id' AS "id",
       raw->>'first_name' AS "first_name",
       raw->>'last_name' AS "last_name",
       raw->>'source_id' AS "source_id",
       raw->>'phone' AS "phone",
       raw->>'lead_source' AS "lead_source",
       raw->>'year_of_birth' AS "year_of_birth",
       raw->>'gender_code' AS "gender_code",
       raw->>'country_code' AS "country_code",
       raw->>'language_code' AS "language_code",
       raw->>'visit_date' AS "visit_date",
       raw->>'procedure' AS "procedure",
       raw->>'comment' AS "comment",
       raw->>'doctor' AS "doctor",
       raw->>'status' AS "status",
       raw->>'roditelj' AS "roditelj",
       raw->>'ortodoncija' AS "ortodoncija",
       raw->>'hzzo' AS "hzzo",
       raw->>'next_reservation_timestamp' AS "next_reservation_timestamp",
       raw->>'parent_ortho_comment' AS "parent_ortho_comment",
       raw->>'parent_phone' AS "parent_phone",
       raw->>'age' AS "age",
       raw->>'Spol2' AS "Spol2"
FROM legacy_source_row
WHERE source_file = 'Pacijenti_JOINED_Apolonija.csv'
  AND account_id = (SELECT "accountId" FROM survey WHERE "alchemerId"::text = '90492576')
ORDER BY row_no;
