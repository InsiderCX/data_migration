# Pitfalls (and how the scripts now prevent them)

| What happened | Cause | Prevention now |
|---|---|---|
| "Account 36 mismatch", then "Survey not found" | Connected to **UK** staging | Check region first; scripts resolve ids from the Alchemer survey id and stop with a clear message |
| `value "385…" (a phone number) is out of range for type integer` | GUI auto-typed `phone` as integer | `01` creates the staging table with all-text columns |
| `duplicate key … _pkey` on import | GUI added a primary key on a repeating column | Same; plus a unique `row_no` in the file |
| `relation … already exists` on import | GUI only imports into new tables in some modes | Import into the table `01` created; otherwise drop it and let the GUI create it with every column TEXT |
| `syntax error at or near "\"` | `\set`, `\copy` are psql-only | No meta-commands in any script |
| Only one result visible | GUI shows only the last statement's result | Validation queries are run one at a time |
| JSON with a single `count` column | Duplicate column names collapsed | Every column aliased |
| Import into a table named like a real one (`import_batch`) | Free-form names in the GUI | Fixed staging names; `01` refuses on leftovers |
| `violates foreign key constraint "fk_last_processed_visit_id"` | Visits deleted before the batch pointing at them | Batches deleted first; FK list in `database-facts.md` |
| Identity insert refused | `GENERATED ALWAYS` ids | `OVERRIDING SYSTEM VALUE` |
| Ages 2–3 years off | Clinic `age` was age at visit, read as age today | `year(visit) − age`, verified against existing Patients |
| January looks empty, February too high | No responses that month → estimate has no anchor | Flag such gaps; tell ops to read neighbouring months together |
| Legacy visits ~3× platform volume | Clinic file has several rows per visit | Don't compare legacy visit counts; invites use platform rules |
| Status column in clinic file looked usable | Filled on exactly ~25% of rows (export artifact) | Check fill patterns before trusting a column |
| `NaN` treated as a value in Python | pandas NaN is truthy | Normalise missing values to `''` before logic |
| Silent change of raw values | GUI converting dates or numbers | `02` refuses if `raw_visit_date` / `raw_phone` look converted |
| Same file with a new name | `Joined.csv` = `Sie_surveys.csv` | Compare hashes of every input |
