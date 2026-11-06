# Playbook: importing an Account's legacy history

From "the clinic has old data in another system" to "Clinicdash shows it and ops signed off". SIE (`accounts/sie/`) is the worked example for every step. Expect about 2–4 working days per Account, most of it waiting for staging runs and ops.

## 0. Prerequisites

- Inputs from ops or the clinic:
  - **the clinic's patient / visit file** for the legacy period
  - **the Alchemer export** of the Account's survey(s): Response ID, Time Started, Status, `URL Variable: sguid`, score question
- Read access to the prod replicas (Zamera) for Claude Code. Write access to staging and production for the person running scripts.
- A copy of the current BI view (if any) to compare against at the end.

## 1. Discovery (read-only, prod replica)

1. Resolve the Account in **EU and UK** by name; note region, `account.id`, Locations (`timezone`, `quarantine_days`, `msg_age_limit`), Surveys (`alchemerId`), `msg_sending_method`, `sms_sender`, Visit Msg Templates per language.
2. Count Survey Responses with `visit_msg_id IS NULL`, by year and by `sguid` shape (uuid / numeric / test / empty). Numeric sguids are almost always legacy invite ids.
3. Profile the clinic file: rows, columns, which rows already exist on the platform (match on `source_id` + visit date, and file `id` = `visit_msg.id`), which rows are legacy (no date, numeric id).
4. Match unlinked responses to legacy rows on `sguid = id`. Check the match quality (language agrees, one-to-one). List what can't be matched and why (test links, ids missing from the file).
5. Read the platform benchmarks for this Account from its platform-era data: delivery rate, response rate, visit→send and send→response medians, typical send hour, reminder use.
6. Verify the schema facts in `database-facts.md` still hold.

Write all of this into `accounts/<account>/README.md` (the account card) before building anything.

## 2. Prepare the data: what is real and what must be estimated

The load file holds everything from the clinic's file that **doesn't exist in the database yet**. Rows already on the platform are only linked, never created again. Where the clinic's file is missing values that dashboards need (dates, which visits got an invite, delivery), fill them with **estimates fitted to the Account's real platform data**. That way the legacy period's response rate, delivery rate and timing look like what the platform actually produces. Every estimated value is marked as estimated.

Typical for legacy data: responses (real), patients (real), doctor and comments (real); **missing**: visit dates, send dates, which visits got an invite, delivery status. Estimate only what dashboards need, and agree with Ana / ops that the estimates are acceptable and will be labelled. If the clinic or the old SMS provider can supply real send counts, prefer those.

SIE methods (reuse if the data looks the same; re-validate if not):
- **Send date:** legacy ids are sequential in time; fit isotonic regression id → (response start − send→response median) on the responded rows. Check the Spearman correlation is high (SIE: 0.994).
- **Invite selection:** replay platform rules per phone (first visit invited, then not within `quarantine_days`, age ≥ `msg_age_limit`); responded rows always invited. Validate the replay on platform-era visits (SIE: recovered 93% of real invites, ~10% over).
- **Send date, refined in DEV-162:** interpolate between isotonic block midpoints (not steps), and give id groups with Spearman < 0.95 the anchors' send-time quantiles by id rank; weekend dates move to Monday. Check estimated invites per day against the platform's daily volume; days with many real responses can be real batch days.
- **Rows without a phone** are invites only when a real response proves it.
- **Patients without `source_id`:** attach to the one existing Patient with that phone, else one new Patient per phone, else one per row.
- **Visit date** = send − visit→send median. **Delivery status** = platform delivery rate, deterministic by hash.
- **Year of birth** = year(visit) − age. Check what "age" means against existing patients **for every Account** (SIE: age at visit; Videntis: age in 2026).
- **Procedure** derived from comments only if the Account's breakdowns need it; validate the rule on platform visits.

## 3. Build the Account folder

Since DEV-162 (Videntis, Arcadia, Apolonija, Nov 2026) new Accounts use a shared builder and generated SQL instead of copying SIE's hand-written files. Use `accounts/videntis/` as the example.

1. Export the Account's unlinked Survey Responses from the prod replica into `data/db_unlinked_responses_<date>.csv` (`alchemer_response_id, sguid, started_utc, status, is_test`; sguid exactly as stored). The analyst's survey export can miss responses.
2. Copy `scripts/1_build_load_file.py` from another new-style Account and change only its `CONFIG` block (send time, platform medians, quarantine, age rule, delivery rate, year-of-birth rule, raw-only ids). The code below `CONFIG` must stay identical in every Account: diff it.
3. Build the load file: `python3 -I scripts/1_build_load_file.py data/<clinic csv> data/db_unlinked_responses_<date>.csv data/<account>_full_v1.csv`. Record its SHA-256 in the account card.
4. Write `sql_config.json` (load code, Alchemer survey id, exact Account name, source and survey file names, platform start, a fixed uuid namespace, what is estimated). Then `python3 -I tools/render_legacy_sql.py accounts/<account> --update-expect` copies the counts from the load file and renders `sql/01, 02, 03, 04, 99`. Never edit the rendered SQL by hand: change the template or the config and render again.
5. Write the account card, `STAGING.md` and, before production, `PRODUCTION.md`. Start an empty `runs/` folder.

Ops SQL (05–08) for new-style Accounts: see the DEV-162 plan for status.

Since DEV-232 (Kvaternik, Mazalin, Optical Express, Nov 2026) the builder and renderer have opt-in options for files that differ from the DEV-162 ones; left out, they keep the DEV-162 behaviour, and Videntis, Arcadia and Apolonija rebuild byte-identical. `layout: 2` with `platform_rule: db_ids` (platform rows = the Account's Visit Msg ids on prod), `status_rule: file` (real SMS status, `status_source` in `visit_msg.meta`), `send_rule: waves` (bulk sends seen in the responses), `invite_rule: all`, `reused_rule: raw_only`, `location_map`, `country_map`, `language_map`, and `link_responses: false` in `sql_config.json` (append only: no response is linked and no map row written). Use `accounts/mazalin/` as the example for these.

SIE (`accounts/sie/`) keeps its hand-written v4 files; they are what ran on prod.

## 4. Test locally

`bash accounts/<account>/tests/run_mock_test.sh <clinic file>`. All checks must pass and the last line must read `ALL CHECKS PASSED`. The mock (`tools/legacy_mock/`) mirrors prod: the real constraints (identity ids, `fk_last_processed_visit_id`, ticket and reminder-log foreign keys), the link trigger **with** SIE's fallback, SIE's legacy tables and batch already present, Patients findable only by phone (one and two per phone), a Deleted response and reused ids. It runs 01 → import → 02 → checks → 03 → 04 (values identical) → 99 (back to baseline) → reload → 01 must refuse.

## 5. Staging (person runs, pastes results)

1. Confirm the connection is the right **region**, and that staging contains the Account and its Survey (`SELECT … FROM survey WHERE "alchemerId" = …`). If staging is too old or lacks the Account, ask for a prod snapshot.
2. `00_cleanup_all.sql` only if earlier attempts ran there.
3. `01_before_import.sql` → GUI import of the load file into the existing `stg_<account>_full` → count check → `02_load.sql` → `03_validation.sql` → `04_export_original_csv.sql` (must equal the original file).
4. `06_compare_bi_responses.sql`, then `07_report_by_period.sql` and `08_ops_lists.sql` for ops.
5. Test `99_rollback.sql` once and reload.

Differences between staging and BI must all be explained by the staging copy's age (responses that reached prod later). Anything else is a bug.

## 6. Ops validation

Compare before handing over (DEV-232 method): **Alchemer is the source of truth** (`count_responses` per status and period against staging and prod); **Zoho by response id** for the legacy months (`GROUP_CONCAT` per month) and by an id checksum per month for the newer months; responses without an invite are excluded on both sides and listed. Every month gets an explanation. Then hand ops the material in `ops-validation.md`: the visual report, the workbook, the BI comparison, and the "real vs estimated" list, plus the caveats specific to the Account (gaps in the estimate, legacy volumes that aren't comparable). Get written confirmation.

## 7. Production

Follow `accounts/<account>/PRODUCTION.md`: go/no-go list (ops, CTO, dev check on `legacy_import` batches, backup, file hashes), then 01 → import → 02 → 03 → 04 → 06 → 07/08, Clinicdash check, drop staging tables, delete local PII. On prod every comparison with BI must match exactly.

The short version (SIE, 28 Oct 2026, is the worked example in `accounts/sie/runs/`):

| # | Who | Do | Check |
|---|---|---|---|
| — | Claude | Pre-flight on the prod replica: right Account, unlinked responses, no leftovers, original trigger, baseline counts | Matches the account card |
| 1 | Person | `SELECT current_database(), …` | Right database and Account (EU vs UK) |
| 2 | Person | `01_before_import.sql` | 3 tables + staging table, 0 rows |
| 3 | Person | GUI import of the load file into the existing staging table | — |
| 4 | Person | Count check | Row kinds as in the account card |
| 5 | Person | Check the GUI's **commit mode**, then `02_load.sql`. Wait for the result row | Counts as in the account card |
| 6 | Claude | Confirm the load on the replica, then run `03` and `06` read-only | All checks pass; BI matches every month |
| 7 | Person | `04_export_original_csv.sql` and compare with the clinic file | Identical (may be skipped by decision if proven on staging; write that down) |
| 8 | Person | Clinicdash on prod | Legacy period visible; platform period unchanged |
| 9 | Person | `DROP TABLE` the staging table; delete local PII | Claude confirms on the replica that the table is gone |

Hashes: if a file's hash differs from the recorded one, compare the values before rejecting it. A lost final newline is enough to change the hash.

**Write a run log** in `accounts/<account>/runs/<date>_<environment>.md`: pre-flight, each step with its result, ids created (load code, mock sending batch id, `loaded_at`), what was skipped and why, open items, lessons. Copy the SIE log's layout.

## 8. Aftercare

- Tell the clinic and the CSM which figures are estimates.
- Retire the old BI pages for the Account once ops agree.
- Update the status table in the root `README.md` and the account card (dates, counts, hashes), and link the run log.
- Move new lessons from the run log into `pitfalls.md` and this playbook.
- Restrict `legacy_source_row` access like `patient`.
