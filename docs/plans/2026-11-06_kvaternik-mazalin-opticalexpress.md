# Plan: legacy import for Kvaternik, Mazalin and Optical Express

Linear: [DEV-232](https://linear.app/insidercx/issue/DEV-232/upload-legacy-data-for-kvaternik-mazalin-and-opticalexpress-to-the-stg) · Branch: `feat/DEV-232-legacy-import-kvaternik-mazalin-opticalexpress` (stacked on `feat/DEV-184-validate-legacy-data-staging`, which holds `tools/run_staging.sh` and `tools/dev184/`) · Owner: Ana · Agreed 6 Nov 2026

Follows `docs/playbook.md`, with Videntis (`accounts/videntis/`) as the template for new-style Accounts. Commits `refs DEV-232`.

## Status (6 Nov 2026)

| Step | Status |
|---|---|
| 1 Discovery, plan, account cards | **done 6 Nov 2026** |
| 2 Builder changes, load files, rendered SQL, mock tests | **done 6 Nov 2026**. Shared builder and renderer extended with opt-in options; Videntis, Arcadia and Apolonija rebuild byte-identical load files and SQL; mock test passes for all six Accounts |
| 3 EU staging run per Account | **done 6 Nov 2026**, all three loaded and left for ops: Kvaternik batch 13097, Mazalin 13095, Optical Express 13099. Run logs in `accounts/<account>/runs/2026-11-06_staging.md`. Found and fixed on staging: country foreign key (decision 13) |
| 4 Ops package (differences workbook, COPS checklist) | **ready 6 Nov 2026**, waiting for Ana to create the COPS ticket. Workbook `out/DEV-232_ops_review_2026-11-06.xlsx` (git-ignored, ids only), built by `tools/dev232/build_ops_workbook.py`; ticket text `out/dev232/COPS_ticket_DEV-232.txt` |

## How we work

- A person checks every step. After each step Claude stops with an overview (what was done, real vs estimated numbers, what is open). The next step starts only when Ana confirms.
- Claude reads the prod replicas. **Ana allowed Claude to write to EU staging for DEV-232** through `tools/run_staging.sh` (refuses anything but `insider-eu-stg`). Production stays Ana's.

## The Accounts (EU prod replica, 6 Nov 2026, real numbers)

| | Kvaternik | Mazalin | Optical Express |
|---|---|---|---|
| Account name | Kvaternik | Poliklinika Mazalin | Optical Express |
| Account / Survey id (EU prod) | 21 / 11 | 24 / 13 | 44 / 25 |
| Alchemer survey | 90677816 | 90553181 | 90535032 |
| Locations | 27 Kvaternik Kostanjevec, 28 Kvaternik Subiceva | 31 | 79 |
| First platform invite | 5 Mar 2024 | 23 Apr 2024 | 4 Mar 2025 |
| Clinic file rows | 8,407 | 30,481 | 7,931 |
| Already on the platform (id = Visit Msg) | 7,680 | 28,028 | 3,850 |
| **Legacy rows** | **727** | **2,453** | **4,081** |
| Legacy id type | uuid | uuid | numeric (+1 text id) |
| Unlinked Survey Responses in DB | 137 | 471 | 683 |
| Of which match a legacy row (not Deleted) | 132 | 437 | 634 |

None of the three exist on UK. Every script resolves ids from the Alchemer survey id.

**Why Mazalin and Kvaternik have uuid legacy rows:** their first weeks (Feb–Apr 2024) were sent with uuid survey links before Visit Msgs were stored. The responses exist with those uuids as `sguid`, but no Visit Msg has that id.

Inputs are in `accounts/<account>/data/` (git-ignored, PII). SHA-256:

| File | SHA-256 |
|---|---|
| `Pacijenti_joined_Kvaternik.csv` | `f043591a1401afe6da68cdf118530b04e150ccfcf8576a70003e80530c6266e1` |
| `Surevy_responses_Kvaternik.csv` | `da60d3126f0c9c071e68207fcf0ee6faa3ce077280efad5e3ccec0550e30b1ee` |
| `Pacijenti_Joined_Mazalin.csv` | `73e39f554fbd6dc51ebff25e61593bedd32fc336e9f6a6b9dc08fa74b135b773` |
| `Surevy_responses_Mazalin.csv` | `4a0bf901ba9c85f0f03c498ae33adbc61a2905f37447e715085ed589a48c365b` |
| `Pacijenti_joined_OpticalExpress.csv` | `802a8e335b31f236ec8adbbde0567a34193fb065e4bb6aabdf1a5dc17be43c8a` |
| `Surevy_responses_OpticalExpress.csv` | `46e3a445a9305287764b90e3ebce31cb2077bd77e17bd8e1cc002ce0fb86dfc6` |

## Decisions (grilling with Ana, 6 Nov 2026)

1. **Append only.** Existing Patients, Patient Visits, Visit Msgs and Survey Responses are never changed. The load only adds legacy rows.
2. **No linking for now** (`link_responses: false` in `sql_config.json`). Existing responses keep `visit_msg_id` empty. Visit Msgs get generated ids (`uuid_generate_v5`) and **no** `legacy_invite_map` rows are written, so no Alchemer sync can link them by itself (the link trigger runs on every UPDATE). Responses are never inserted, so nothing exists twice. Ops decide on linking; the workbook shows each month "today" and "if linked". If ops say link: Mazalin and Kvaternik Visit Msgs take the original uuid as id (the trigger's own uuid path links them), Optical gets map rows; rebuild, rerun staging (about half a day).
3. **SMS statuses in the files are real.** Uppercased and mapped to the names these Accounts' platform rows use: `DELIVERED → DELIVERED_TO_HANDSET`, `UNDELIVERABLE` / `UNDELIVERED → UNDELIVERABLE_NOT_DELIVERED`, `EXPIRED → EXPIRED_EXPIRED`, `REJECTED → REJECTED_NETWORK`, `PENDING → PENDING_ACCEPTED`. `UNSENT` (6 rows, all Kvaternik platform rows, not loaded) needs no mapping.
4. **Answered rows with a non-delivered status become `DELIVERED`** (a response proves delivery): Mazalin 15, Optical 21. Marked "corrected" and listed for ops.
5. **Send dates are estimated** (no real ones exist):
   - Kvaternik: all legacy invites 21 Feb 2024 14:50 Zagreb (first real response 15:57 Zagreb). The file's visit date (21 Feb 2024 12:00 on every legacy row) is a placeholder; kept as it is and labelled.
   - Mazalin: visits up to 31 Jan 2024 → 12 Feb 2024 15:00 Zagreb (wave 1, 277 real responses); visits from 1 Feb 2024 → 27 Mar 2024, just before that day's first response (wave 2, 152 real responses). The 8 January visits answered after 27 Mar stay in wave 1.
   - Optical: DEV-162 method (isotonic id → send, fitted per id scheme; schemes under 0.95 get the anchors' send-time quantiles by id rank; weekends to Monday). **Fails the 0.95 Spearman gate (0.933)**; labelled as such.
   - Every estimated send is before the row's real response; the build refuses otherwise.
6. **Every Optical legacy row is an invite** (no invite replay): the rows carry SMS statuses. Empty status (1,356): answered rows `DELIVERED`, the other 1,102 estimated at Optical's platform delivery rate (88.2%), deterministic by hash.
7. **Optical's 56 repeated legacy ids (113 rows) are not loaded.** Different phones, no responses. Kept as raw rows only (export back stays identical); ops decide.
8. **Unmatched responses:** same as DEV-162 decisions 6, 11, 12. Deleted not linked; text sguids that equal a clinic id count as matches; the rest is listed by Alchemer response id. Optical's 32 numeric sguids missing from the clinic file go on the ops checklist.
9. **Patients:** same as DEV-162 decision 14. With `source_id`: the existing Patient (`ON CONFLICT`), never changed, else a new one. Without: the one Patient with that phone, else one new Patient per phone.
10. **Year of birth** from the file only when 1900–2026, else empty (raw kept). Optical's `0` = empty. No age rule: the files hold years, not ages.
11. **Kvaternik Location** comes from the row: `Kostanjevec` → 27, `Subiceva` → 28. Each Location's own SURVEY_INVITE template (40, 39).
13. (6 Nov 2026, found on staging) **Country** goes to the Patient only as a code that exists in `public.country` (foreign key `fk_country_code`). The builder maps each Account's values explicitly (Mazalin `IE → IRL`, `XK → XXK`, `RS → SER`, …; Optical's Croatian names `SLOVENIJA → SVN`, …). The mock now has the country table and the key.
12. **Response-rate check** (if linked, estimated): the build refuses if a legacy response rate is more than 5 points from the Account's platform rate. Expected: Kvaternik 19.0% (platform 21.4%), Mazalin 18.2% (19.0%), Optical ≈17.4% (17.5%).

## Steps

| # | Step | Who | Estimate |
|---|---|---|---|
| 1 | Discovery, plan, account cards | Claude | done |
| 2 | Builder: link switch, real statuses + mapping, wave / fixed send dates, per-row Location, held-back rows. Load files, `sql_config.json`, rendered SQL, mock tests pass for all three | Claude | ~1 day |
| 3 | EU staging per Account: 01 → import → 02 → 03 → 04 (identical) → 99 → reload. Stop after each Account | Claude runs, Ana checks | ~2 h |
| 4 | Ops package: differences workbook (prod replica vs Zoho vs Alchemer by response id; "today" vs "if linked"), checklist for a new COPS ticket | Claude | ~0.5 day + Zoho waits |

All estimates.

## Comparison: staging vs Zoho vs Alchemer (6 Nov 2026, real numbers)

- **Alchemer = source of truth.** Complete / Partial before the platform start: Kvaternik 112 / 20, Mazalin 309 / 130, Optical 539 / 133, identical on staging and prod. Before 1 Sep 2026 identical too, except Mazalin: staging lacks 7 responses of 9 Jul 2026 (reached prod after the staging copy) and 1 response (submitted 16-20 Dec 2024) is Complete in Alchemer but Partial in our DB (B1, platform era).
- **Zoho vs staging, legacy months, by response id:** all 30 months identical once the legacy responses are counted as linked. No Zoho response missing from staging. Responses only on staging: Deleted, test, no sguid, and Optical's 32 missing invites (A3).
- **Zoho vs staging, newer (platform) months, by id:** checksum per month (count, sum, min, max of the response ids with an invite; Zoho query in `out/dev232/zoho_checksums.csv`). Identical in every month: Kvaternik 30, Mazalin 27, Optical 19. Exceptions: Mazalin Jul 2026 (staging lacks 7 later-synced responses; prod identical) and Nov 2026 (Zoho not refreshed yet). Responses without an invite (B2) are excluded on both sides.
- Zoho sources: Poliklinika Kvaternik / `JOINED_FINAL`, Poliklinika Mazalin / `Joined`, Optical Express / `Joined_final`. Inputs in `out/dev232/` (git-ignored).
- Alchemer single responses opened (status only kept): Mazalin 1896, 1898, 1901, 1909, all Partial as in our DB. Stopped there: `get_response` returns full answers and IP addresses.

## Open items

| # | Account | Question | Who |
|---|---|---|---|
| O1 | All | Link the legacy responses? (decision 2) | Ops |
| O2 | Optical | 56 repeated ids, 113 rows, different phones: keep one, both or none? | Ops |
| O3 | Optical | 32 responses whose numeric sguid is missing from the clinic file: does the clinic have those rows? | Ops / clinic |
| O4 | Mazalin, Optical | 36 answered rows with a non-delivered status, corrected to `DELIVERED` | Ops confirm |
| O5 | Optical | Confirm no real send dates exist (old SMS providers) | Ops |
| O6 | Kvaternik | 1 legacy row has shifted columns (`year_of_birth` = `#VALUE!`, a date in `language_code`) | Ops / clinic |
| O7 | Optical | 1 legacy row is a test (text id, its only response Deleted); loaded as an invite as the file says | Ops confirm |
| O8 | Optical | 299 answered invites have the send moved to 2 min before the response (estimate later than the real answer) | Info |
