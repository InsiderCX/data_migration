# Plan: legacy import for Videntis, Arcadia and Apolonija

Linear: [DEV-162](https://linear.app/insidercx/issue/DEV-162/upload-the-legacy-data) · Branch: `feat/DEV-162-legacy-import-videntis-arcadia-apolonija` · Owner: Ana · Agreed 3 Nov 2026

Follows `docs/playbook.md`, with SIE (`accounts/sie/`) as the template.

## Status (3 Nov 2026)

| Step | Status |
|---|---|
| 1 Discovery | done; account cards written; checklist `out/DEV-162_checks.xlsx` (git-ignored) |
| 2 Load files | done; hashes in the account cards |
| 3 SQL + mock tests | load path (01, 02, 03, 04, 99) done, mock test passes for all three; ops SQL (05–08) still to write |
| 4 Staging | runbooks ready (`accounts/<account>/STAGING.md`); not run |
| 5–7 | not started |

## How we work

- **A person checks every step.** After each step Claude stops and gives an overview: what was done, what it showed (real vs estimated numbers), and what is open. The next step starts only after Ana confirms the step is done.
- Claude only reads the prod replica. Ana runs every write on staging and production.

## The Accounts (EU prod replica, 3 Nov 2026, real numbers)

| | Videntis | Arcadia | Apolonija |
|---|---|---|---|
| Account name | Videntis Dental Centar | Arcadia | Stomatološka poliklinika Apolonija |
| Account / Survey id (EU prod) | 38 / 19 | 45 / 27 | 39 / 20 |
| Alchemer survey | 90508475 | 90534273 | 90492576 |
| Location settings | Europe/Zagreb, quarantine 90, age limit 0 | Europe/Zagreb, quarantine 90, age limit 18 | Europe/Zagreb, quarantine 90, age limit 25 |
| First linked response | 21 Oct 2024 | 24 Apr 2025 | 21 Oct 2024 |
| Unlinked responses in DB | 619 | 1,092 | 1,566 |
| Clinic file rows | 16,416 | 13,595 | 67,895 |
| Legacy (numeric) sguids in survey file | 502, all in clinic file | 1,165 (1,072 distinct), all in clinic file | 1,471, all in clinic file |

None of the three exist on UK. Every script still resolves ids from the Alchemer survey id.

Inputs are in `accounts/<account>/data/` (git-ignored, PII). SHA-256:

| File | SHA-256 |
|---|---|
| `Pacijenti_JOINED_Videntis.csv` | `6ce5844e54d3f3daa3e9d8e8657b1de74ec798106eb810003646d8e8f921f4e0` |
| `Survey_responses_Videntis.csv` | `7632c12509ccc3a9cd6d1cada864ad20a21f564b85c143bfe54401e2719af964` |
| `Pacijenti_Joined_Arcadia.csv` | `2beffde7f71484f20278273dbc845ef607b5f2dc7bcc4e82abe008db4356c109` |
| `Survey_responses_Arcadia.csv` | `8066d05cae0541c70fe1f7da26f92d51b65cf0426f400d9355f8f19a55d1d0b7` |
| `Pacijenti_JOINED_Apolonija.csv` | `c04325052d5cbb4363bac8918715d2965788c0393699c2e108bbaf375ed860c2` |
| `Survey_responses_Apolonija.csv` | `abb6b20be148037440b088f6a4fd3a3a6365ca9ef71968f32d6a7a3c906105e3` |

## Decisions

1. All three Accounts run in parallel. Every input and benchmark comes from the **prod replica**, never staging.
2. Staging is used as it is (no fresh snapshot). Differences in the BI comparison caused by staging's age are expected and are logged as such.
3. Apolonija's 25,547 rows without an id stay in the load file as raw rows (for the export back) until ops say what they are.
4. Apolonija's legacy rows have no age: `year_of_birth` stays empty, and the invite replay skips the age rule. The effect on the response rate is measured and labelled as estimated.
5. Arcadia's repeated legacy ids are analysed first. A person decides how to link them.
6. Responses in a survey file but missing from the DB are listed by Alchemer response id. We never insert into `survey_response`.
7. SIE's estimation methods are reused with each Account's own constants. An Account passes only if ids vs response time Spearman ≥ 0.95 and the replay recovers ≥ 85% of real platform-era invites. An Account that fails comes back to Ana before anything is built.
8. One Linear issue (DEV-162), one branch, commits `refs DEV-162`.
9. One production session for all three Accounts, each with its own load transaction and rollback.
10. A dev reviews the PR before production. It merges right before the production session. Accepted risk: if the review changes SQL that already ran on staging, that Account's staging run is repeated (about half a day).
11. (3 Nov 2026, after discovery) Link the 47 responses whose sguid matches a clinic id once trimmed or as text: Apolonija 45, Videntis 2 (checks C07, C08).
12. Deleted responses are not linked, as for SIE (C09).
13. For now, Arcadia's 93 responses on reused ids and Videntis' 70 responses with missing invites stay unlinked and listed. They can be added later if the clinic answers (C03, C04).
14. (3 Nov 2026, step 3) Legacy rows without a `source_id`: attach to the existing Patient when their phone matches exactly one Patient of the Account (that Patient is not changed); otherwise one new Patient per phone with an empty `source_id`; rows with neither get one new Patient each, with an empty phone. Rows with a `source_id` work as in SIE.
15. (3 Nov 2026, step 2) Legacy rows without a phone are invites only when a real response proves the invite.

## Steps

Each step ends with an overview and Ana's confirmation.

| # | Step | Who | Estimate |
|---|---|---|---|
| 1 | Discovery on the prod replica for all three: benchmarks, unlinked responses by sguid shape, match quality, schema facts. Analyse the open items. Write the three account cards | Claude | ~1 day |
| 2 | Copy `accounts/sie/` three times, set constants, adapt the builders, build the load files, record hashes | Claude | ~1.5 days |
| 3 | Mock tests pass for all three | Claude | ~0.5 day |
| 4 | Staging runs: check staging has the Account and Survey, then 01 → import → 02 → 03 → 04 → 06 → 07/08, test 99 rollback | Ana runs, Claude checks | ~1 day of Ana's time |
| 5 | Ops validation per Account (`docs/ops-validation.md`), written sign-off | Ops | depends on ops |
| 6 | Open the PR, dev review, fixes (rerun staging where SQL changed) | Claude + dev | 1–2 days |
| 7 | Production session for all three, Clinicdash check, drop staging tables, delete local PII, run logs, README status | Ana runs, Claude checks | ~0.5 day |

Total: about 5–6 working days of build and run time, plus the time ops and the dev review take. All estimates.

## Open items

Details for each item are in the account cards (`accounts/<account>/README.md`).

| # | Account | Question | Who | Status |
|---|---|---|---|---|
| 1 | Apolonija (P1) | What are the 25,547 rows without an id? They hold only name, phone and sometimes a comment, and each phone also appears on a row with an id | Ops | asked by Ana |
| 2 | Arcadia (A1) | 289 legacy ids are **reused** for a second Patient (all in 10113–10467, two id schemes collided). 93 of them have **one** response each (the survey export shows it twice because of the join). The files can't tell which Patient answered | Ana decides | analysed 3 Nov 2026 |
| 3 | All | Gap between unlinked responses in the DB and legacy sguids in the files | Claude | **explained 3 Nov 2026**: empty, test and text sguids, plus responses whose invite is missing from the clinic file (Videntis 70, Apolonija 13, Arcadia 3). Linkable: Videntis 502, Arcadia 979 (+93), Apolonija 1,476 |
| 4 | Videntis (V1) | 70 legacy responses point to invites missing from the clinic file. Ask the clinic for those rows, or leave them unlinked | Ana / ops | open |
| 5 | All (V2, A2, P2) | Early id groups are weakly ordered in time (Spearman 0.04–0.71), so send dates for their non-responded rows can't be fitted from id order. Overall Spearman passes (0.992–0.998) | Decide in step 2 | open |
