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

## DEV-232 package (Kvaternik, Mazalin, Optical Express; staging, 6 Nov 2026)

One workbook per project, ids only: `out/DEV-232_ops_review_2026-11-06.xlsx`, built by `tools/dev232/build_ops_workbook.py` (inputs in `out/dev232/`). Sheets: Read me, Checklist (A legacy / B existing gaps / C sign-off, as in COPS-224), Load summary, All months (Zoho vs staging vs prod, with the explanation and an id check per month), Legacy months, Responses (one row per response, labelled), Corrected statuses, Repeated ids, Missing invites, Other rows, Alchemer vs DB. Ticket text: `out/dev232/COPS_ticket_DEV-232.txt`.

Results (real numbers): Alchemer = staging for all three (legacy period and to 1 Sep 2026; one Mazalin status gap in Dec 2024). Zoho = staging by response id in all 30 legacy months once the legacy responses are counted, and in every newer month by id checksum (exceptions: staging copy age, Zoho not refreshed for Nov 2026). The load is append only, so on staging the legacy invites show 0 responses until ops decide to link them (A1).
