# Ops validation package

What ops receive for each Account, how it's produced, and what "OK" looks like. Produce it on staging first, then again on production after the load.

| Deliverable | Made from | What ops check |
|---|---|---|
| **BI comparison** | `sql/06_compare_bi_responses.sql` (BI export inlined) | Every BI response is in the database and shown; values equal. On staging, differences only for responses newer than the staging copy |
| **Visual report** (Claude dashboard artifact "<Account> legacy migration review") | `sql/07_report_by_period.sql` R1, R2, R5, R6, R7 exported as CSV, loaded as the report's datasets | Months match BI; legacy period shaded; estimated figures hatched; caveats readable |
| **Workbook** (`<account>_invites_and_responses.xlsx`) | `sql/08_ops_lists.sql` → `scripts/3_build_ops_workbook.py` → `recalc.py` | Every invite sent and every response, with a monthly summary in formulas; estimated cells yellow |
| **Real vs estimated list** | Account card / report | Agreement that estimates may be shown |
| Optional field-level exports | `sql/05_ops_exports.sql` | Spot checks of single rows |

## Rules for anything handed to ops

- No patient names, phones, `source_id` or comments. Rows are matched by Alchemer response id or legacy invite id (sguid). If ops need names for spot checks, produce a separate restricted file and say so.
- Every legacy figure says whether it's real, derived or estimated.
- Use Clinicdash definitions and rounding, and say which page a number corresponds to (NPS Trends vs Message performance date responses differently).
- State the data cut-off (staging copy date, BI export date, prod replica date).

## SIE results (reference)

Staging, 26 Oct 2026:
- 38 of 41 months match BI. The 3 that differ (Jul, Sep, Oct 2026) come from 17 responses newer than the staging copy.
- Legacy: 2,692 invites (estimated), 2,592 delivered, 480 responses, 18.5% response rate (estimated), NPS 86.5 (real, equal to BI).

Caveats given to ops:
- Read Dec 2023 – Feb 2024 together.
- Legacy visit volume isn't comparable.
- 27 responses can't be linked (test links, no sguid, ids missing from the clinic file).
