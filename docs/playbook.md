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

## 2. Decide what is real and what must be estimated

Typical for legacy data: responses (real), patients (real), doctor and comments (real); **missing**: visit dates, send dates, which visits got an invite, delivery status. Estimate only what dashboards need, and agree with Ana / ops that the estimates are acceptable and will be labelled. If the clinic or the old SMS provider can supply real send counts, prefer those.

SIE methods (reuse if the data looks the same; re-validate if not):
- **Send date:** legacy ids are sequential in time; fit isotonic regression id → (response start − send→response median) on the responded rows. Check the Spearman correlation is high (SIE: 0.994).
- **Invite selection:** replay platform rules per phone (first visit invited, then not within `quarantine_days`, age ≥ `msg_age_limit`); responded rows always invited. Validate the replay on platform-era visits (SIE: recovered 93% of real invites, ~10% over).
- **Visit date** = send − visit→send median. **Delivery status** = platform delivery rate, deterministic by hash.
- **Year of birth** = year(visit) − age. Check what "age" means against existing patients (SIE: age at visit, not today).
- **Procedure** derived from comments only if the Account's breakdowns need it; validate the rule on platform visits.

## 3. Build the Account folder

Copy `accounts/sie/` to `accounts/<account>/` and change:
- the Alchemer survey id, Account name check, time zone, load code (`<ACCOUNT>_LEGACY_V1`), source file name
- builder constants (send hour, medians, delivery rate, id schemes, quarantine, age limit)
- the hard-coded expected counts in `02_load.sql` (row kinds, responses to link, params) and the expectations in `03`, `06`, `07`, `08`
- `06_compare_bi_responses.sql`: regenerate its inlined BI responses from the Account's BI export
- the account card and `PRODUCTION.md`

Build the load file with `scripts/1_*` and `scripts/2_*`, record its SHA-256, and keep it in `data/` (git-ignored).

## 4. Test locally

`bash accounts/<account>/tests/run_mock_test.sh <clinic file>`. Adapt `tests/make_mock.py` to the Account's ids and counts. All checks must pass. The test covers the real constraints: identity ids, `fk_last_processed_visit_id`, ticket and reminder-log foreign keys, the link trigger.

## 5. Staging (person runs, pastes results)

1. Confirm the connection is the right **region**, and that staging contains the Account and its Survey (`SELECT … FROM survey WHERE "alchemerId" = …`). If staging is too old or lacks the Account, ask for a prod snapshot.
2. `00_cleanup_all.sql` only if earlier attempts ran there.
3. `01_before_import.sql` → GUI import of the load file into the existing `stg_<account>_full` → count check → `02_load.sql` → `03_validation.sql` → `04_export_original_csv.sql` (must equal the original file).
4. `06_compare_bi_responses.sql`, then `07_report_by_period.sql` and `08_ops_lists.sql` for ops.
5. Test `99_rollback.sql` once and reload.

Differences between staging and BI must all be explained by the staging copy's age (responses that reached prod later). Anything else is a bug.

## 6. Ops validation

Hand ops the material in `ops-validation.md`: the visual report, the workbook, the BI comparison, and the "real vs estimated" list, plus the caveats specific to the Account (gaps in the estimate, legacy volumes that aren't comparable). Get written confirmation.

## 7. Production

Follow `accounts/<account>/PRODUCTION.md`: go/no-go list (ops, CTO, dev check on `legacy_import` batches, backup, file hashes), then 01 → import → 02 → 03 → 04 → 06 → 07/08, Clinicdash check, drop staging tables, delete local PII. On prod every comparison with BI must match exactly.

## 8. Aftercare

- Tell the clinic and the CSM which figures are estimates.
- Retire the old BI pages for the Account once ops agree.
- Update the status table in the root `README.md` and the account card (dates, counts, hashes).
- Restrict `legacy_source_row` access like `patient`.
