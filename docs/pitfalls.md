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
| Replica showed nothing right after `02_load.sql` (SIE prod, 28 Oct 2026) | The run hadn't finished or wasn't committed yet in the GUI | Before running `02`, check the GUI's commit mode. Wait for the result row, then confirm on the replica before the next step |
| Load file hash differed from the recorded one (SIE prod) | The final newline was lost on upload / download | If a hash differs, compare the values (pandas) before rejecting the file. Record what differed in the run log |
| `01` would refuse every new Account once one Account is loaded (found 3 Nov 2026, Videntis / Arcadia / Apolonija) | SIE's `01` refused on *any* `legacy_import` sending batch, and SIE's batch is on prod | Generated `01` checks only this Account and this load code; it creates the shared tables / trigger only if missing |
| Dates read with the wrong day and month (would have hit all three Nov 2026 Accounts) | SIE's exports were month-first; these exports are day-first | Check the format on every new export: a first field > 12 means day-first. Compare a few `Time Started` with `"dateStarted"` |
| Year of birth would have been 1–3 years off (Videntis) | Its `age` is age **in 2026**, not age at the visit as in SIE | Check `age` against existing Patients' real year of birth per Account before deriving anything |
| Hundreds of estimated invites on one day | Isotonic regression gives steps: every id between two answered ids gets the same date; weak id groups pool into one block | Interpolate between isotonic block midpoints; id groups with Spearman < 0.95 use the anchors' send-time quantiles by rank. Check invites per day against the platform |
| Invites estimated for rows without a phone | The replay treated an empty phone as a phone | No phone → invite only when a real response proves it |
| Most legacy rows have no `source_id` (Videntis 81%) | SIE keyed Patients on `source_id` | Phone matches exactly one existing Patient → attach; else one new Patient per phone; else one per row (decision 14 in the DEV-162 plan) |
| Responses missing from the analyst's survey export (Apolonija: 45 with a leading space or `apo…` id, 5 more) | The export is older or filtered; some sguids have a leading space | Take the unlinked responses from the prod replica, not from the export; match on the trimmed sguid, link on the sguid exactly as stored |
| The same legacy id used for two Patients (Arcadia, 289 ids) | Two id schemes collided | Never link or map a reused id; list its responses for ops |
| "Access Denied" from Zoho through Zamera after a few calls (3 Nov 2026) | Zamera's Zoho token blocked or over its API limit | Don't rely on Zoho for a step; ask whoever runs Zamera to check the token |
| Load stopped on `violates foreign key constraint "fk_country_code"` (Mazalin staging, 6 Nov 2026) | `patient.country_code` references `public.country` (3-letter codes, some platform-specific: Kosovo `XXK`, Serbia `SER`). The mock had no country table | Layout-2 builds map every country value explicitly (`country_map`; an unmapped value stops the build); the SQL keeps only codes in `public.country`; the mock has prod's country table and key |
| Country written as a name in the clinic file (Optical: `SLOVENIJA`, `HRVATSKA`, …) | Export from another system | `left(upper(x), 3)` would have stored wrong codes like `SLO`: map names explicitly |
| A row with shifted columns (`#VALUE!` as year of birth, a date in `language_code`; Kvaternik) | Spreadsheet export error | Cast-safe derived values only: year of birth 4 digits, 1900–2026, else empty; list the row for ops |
| Legacy rows with uuid ids and real visit dates (Mazalin, Kvaternik) | Their first weeks were sent before Visit Msgs were stored | Don't decide "platform" from `visit_date` or `sent_at` (6 Kvaternik platform rows have no `sent_at`): use the Account's Visit Msg ids on prod (`platform_rule: db_ids`) |
| "Not linked" would not stay not linked | The link trigger runs on every UPDATE: an Alchemer sync links any response whose uuid sguid now has a Visit Msg, or whose sguid is in `legacy_invite_map` | Append-only loads (`link_responses: false`) use generated Visit Msg ids and write no map rows; the mock simulates a sync and checks 0 links |
| Clinic file statuses contradict real responses (36 answered invites "not delivered") | Old SMS provider statuses | A response proves delivery: set DELIVERED, mark `status_source=corrected` in `visit_msg.meta`, list for ops |
| Alchemer `get_response` returns the whole response (answers, IP address, location) | It is the only way to open one response by id | Open single responses only when a count can't settle it; keep status, dates, score, sguid; prefer `count_responses` with date bisection |
| Zoho id lists are long and the token blocks after ~4 calls | 20 rows per query; burst limit | Legacy months: `GROUP_CONCAT` ids per month. Newer months: compare a checksum per month (count, sum, min, max of ids), fetch ids only where it differs |
| Zoho misses responses that our DB has (no sguid, test, invite missing) | Zoho joins responses to its patient table | Exclude responses without an invite on both sides before comparing; list them separately |
| `99_rollback.sql` takes 7–17 min on bigger Accounts | Foreign-key checks on each deleted Patient Visit | Known (DEV-162 open item); correct, just slow. Plan the time |
