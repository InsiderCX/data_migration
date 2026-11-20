# Plan: legacy import for Videntis, Arcadia and Apolonija

Linear: [DEV-162](https://linear.app/insidercx/issue/DEV-162/upload-the-legacy-data) (upload) · [DEV-184](https://linear.app/insidercx/issue/DEV-184/validate-the-legacy-data-uploaded-to-dev) (validate on staging; done only when ops have validated the data) · Branch: `feat/DEV-162-legacy-import-videntis-arcadia-apolonija` · Owner: Ana · Agreed 3 Nov 2026

Follows `docs/playbook.md`, with SIE (`accounts/sie/`) as the template.

## Status (3 Nov 2026)

| Step | Status |
|---|---|
| 1 Discovery | done; account cards written; checklist `out/DEV-162_checks.xlsx` (git-ignored) |
| 2 Load files | done; hashes in the account cards |
| 3 SQL + mock tests | load path (01, 02, 03, 04, 99) done, mock test passes for all three; ops SQL (05–08) still to write |
| 4 Staging | **loaded 3 Nov 2026** for all three (run logs in `accounts/<account>/runs/`); rollback tested; loads left on staging for ops. **Compared with Zoho (old BI): every difference explained** (run logs, section "Comparison with Zoho Analytics") |
| 5 Ops validation (DEV-184) | **sent to ops 4 Nov 2026** as Linear [COPS-224](https://linear.app/insidercx/issue/COPS-224) (Karlo), with two workbooks. Waiting for answers. DEV-184 is done only when ops have validated the data |
| 5–7 | not started |

## Where we stopped (19 Nov 2026)

DEV-312 done (Ana's manual check). The DEV-312 table now has two reason columns: Zoho vs Clinicdash after load, and Clinicdash staging vs after load. COPS-333 explains to ops why staging is lower.

- **Staging is a prod copy from 28 Sep 2026.** It has prod's Survey Responses with `created_at < 2026-09-29 00:00 UTC`, plus our loads; Alchemer has not synced to staging since. That cut-off plus the loads reproduces all 12 of Ana's Clinicdash staging numbers exactly (all time and Sep 2026, six Accounts; real). So staging is lower for late Sep 2026 onwards (e.g. Mazalin all time 5,187 on staging vs 5,616 after load). Legacy months match. Checked on the prod replica: staging is not reachable by `psql` from the laptop (private host, timeout).
- **Zoho read on 19 Nov vs Clinicdash after load on 17 Nov.** Zoho has picked up newer November answers since, so the differences moved. Clinicdash after load on 19 Nov (prod + load, projected): Videntis 996, Arcadia 2,405 (-93 vs Zoho), Apolonija 2,666 (+183), Kvaternik 1,754 (+2), Mazalin 5,635 (+2), Optical Express 1,286 (+1). The extra +1/+2 are answers newer than Zoho's refresh (Kvaternik also 146).
- **Open: Videntis Zoho chart.** Ana's reading (all time 993 / 75.83, Sep 2026 31 / 51.61) equals Zoho's `JOINED_FINAL` table (995 scored; Sep 33 with 7 detractors) minus exactly 2 Sep 2026 detractors. The chart's filter can't be read with the Zamera token (error 8540). Ask Ana which chart she read.
- **Open: Apolonija Sep 2026.** Ana reads 46 / 78.26 in Zoho; it was 47 on 17 Nov (1 promoter fewer). Not checked: Zoho returned "Access Denied" after a burst.

**Production chain in Linear** (each blocked by the one before): COPS-333 ops sign off staging → DEV-185 load to production (description written 19 Nov) → DEV-319 Ana validates production against Zoho → COPS-338 ops validate production ("Legacy data OK on production" per Account).

## Where we stopped (17 Nov 2026)

Branch `fix/DEV-184-exclude-alchemer-deleted-responses` (from `main`; the DEV-184 branch was merged as PR #5 on 6 Nov 2026). Loads on staging are still the 3 Nov ones (Videntis 13087, Arcadia 13089, Apolonija 13091).

**Karlo's answers in COPS-224 (16 Nov 2026):**

| Item | Answer | Action |
|---|---|---|
| A1 Arcadia 93 reused ids | Wants a quick sync. Rule given: keep the detractor, else the one with a comment, discard the other. COPS-234 flowchart: no phone → discard, else keep only 1 copy | His rule picks between two responses, but each id has 1 response and 2 clinic rows; `status` and `sent_at` are empty on all 578 rows. **Ana decided (17 Nov):** keep one row per id, don't load the other (it stays in the clinic file). Kept: only row with a phone (20 answered, 56 unanswered); answered with two phones: row closest in time (73, estimated); else the first row (140). Linked 1,072 (was 979). Built, mock test, staging rerun pending. Tell Karlo at the sync |
| A2 Apolonija 44 sguid space/text | Confirm | none |
| A3 Apolonija 127, 300 | Should not count; no response Deleted in Alchemer should be shown anywhere | **Done in the load file (17 Nov):** both re-checked as Deleted in Alchemer; builder option `alchemer_deleted`; Apolonija links 1,515 (was 1,517). Staging rerun pending. "Anywhere" = dev ticket for all Accounts (resync deletions) |
| A4 late answers 647, 1964, 1261 | Confirm | none |
| A5 Videntis 3 unscored | Confirm | none |
| A6 estimated sends and delivery | Confirm | none |
| B1 Apolonija 136 Zoho join drop | Include them in Clinicdash | none: Clinicdash already shows them |
| B2 Apolonija 2073 second answer | No | none (default) |
| B3 Arcadia 2267 stored twice | Ok | dev ticket (below) |
| C1 sign-off | Box ticked, no written "Legacy data OK for production" per Account | **Open:** ask Karlo for the written line per Account |

Projected after the changes (real responses, projected totals): Apolonija Clinicdash after load 2,652 (was 2,654); legacy NPS still 83.6 (127 and 300 were both promoters). Arcadia adds 1,072 legacy responses (was 979), so the gap to Zoho closes by the 93 reused-id responses.

**Zoho vs Clinicdash before production (17 Nov 2026).** Six Accounts, three checkpoints each (all-time total, one legacy month, Sep 2026): 13 match exactly, 5 differ with a named reason, 0 unexplained. Workbook `out/preprod/Zoho_vs_Clinicdash_2026-11-17.xlsx` (git-ignored), built by `tools/preprod/build_zoho_clinicdash_check.py`. Zoho = the Account's Joined table (real); Clinicdash after the load = prod today (real) + the responses the load links (projected).
- Apolonija +181: 44 survey link ids with a space or text (Zoho misses them), 136 dropped by Zoho's JOINED in Mar-Aug 2026, 1 newer than Zoho's refresh.
- Kvaternik +3: response 146 is Deleted and Clinicdash counts Deleted responses (exists on prod today; the only one in the six Accounts; dev ticket), 2 newer than Zoho's refresh. Mazalin +6: newer than Zoho's refresh.
- Arcadia: Zoho's table lists the 93 reused-id responses twice. If its charts count rows, Zoho shows up to 94 more than Clinicdash; Ana checks Aug 2023 by hand (116 = rows, 73 = responses).
- Checked by hand 17 Nov 2026 (Ana): Zoho matches the workbook for all six Accounts; Clinicdash staging General dashboard Arcadia Aug 2023 = 73 / NPS 91.8 as projected. Zoho Pages embedded in Clinicdash show Zoho's numbers (116), not ours. Decisions: Zoho is not changed; legacy months get no Comment Sentiment (not run on legacy comments).
- Clinicdash (InsiderCX code): months in the Clinicdash User's time zone; NPS Trends joins Visit Msg and Patient Visit by the Visit Msg's Account. Checked on staging: every linked legacy response has both, in the right Account.

**Open, in order:**
1. ~~Staging reruns~~ **done 17 Nov 2026**: Arcadia batch 13101 (1,072 linked), Apolonija batch 13103 (1,515 linked); both validated, exports identical, run files `accounts/<account>/runs/2026-11-17_staging.md`.
2. Ana validates by hand: Linear **DEV-312** (workbook attached). Then ops sign off in **COPS-333** (blocked by DEV-312, unassigned until Ana assigns it to Karlo): "Legacy data OK for production" per Account. PR #6 is open for review.
3. DEV-232 (later, own branch): apply Karlo's COPS-234 answers of 9 Nov (link where there is visit data, Optical repeated ids per his marked file, discard the 32 Optical responses without an invite). Needs his marked file.
4. Items 4–7 of the 4 Nov list below are unchanged (faster `99_rollback.sql` and `PRODUCTION.md`; dev ticket for Arcadia 2267 and Alchemer deletions, now covering Karlo's "not shown anywhere"; C04–C06 with the clinic; drop staging tables after sign-off).

## Where we stopped (4 Nov 2026, end of day)

Branch `feat/DEV-184-validate-legacy-data-staging` (pushed, no PR yet). DEV-162 work is merged (PRs #2, #3). Staging password rotated 4 Nov 2026; connection verified read-only. Loads still on staging: Videntis 13087, Arcadia 13089, Apolonija 13091.

**Done 4 Nov 2026 (read-only research):**
- Every linked legacy response checked on staging: one response per invite, none Deleted / test / wrong Account / started before its (estimated) send. 3 started after the platform began (Videntis 647, Arcadia 1964, Apolonija 1261): **Ana decided to keep them linked.**
- Zoho, Clinicdash and Alchemer compared **by Alchemer response id**, for the legacy and the platform era. Every difference is labelled; every month reconciles.
- Two workbooks for ops (git-ignored, patient data in the reused-ids sheet), built by `tools/dev184/`:
  - `out/DEV-184_legacy_differences_2026-11-04.xlsx`: differences caused by the load, Arcadia reused ids (both candidate rows side by side), prod totals per month after the load (projected), Alchemer vs DB totals.
  - `out/DEV-184_platform_era_differences_2026-11-04.xlsx`: gaps that already exist today, unrelated to the load.
- Sent to ops as Linear **COPS-224** (Karlo): checklist A1–A6 (legacy), B1–B3 (platform era), C1 (sign-off).

**Findings (real numbers, 4 Nov 2026):**

| Account | Zoho all time | Clinicdash today | Added by load | Clinicdash after load | Gap explained by |
|---|---|---|---|---|---|
| Videntis | 985 | 481 | 501 | 982 | −3 legacy responses without score |
| Arcadia | 2,346 | 1,275 | 979 | 2,254 | −93 reused ids, −1 no score, +2 not yet in Zoho |
| Apolonija | 2,469 | 1,137 | 1,517 | 2,654 | +44 sguid space/text, +2 deleted in Alchemer, +136 Zoho join drop, +3 not yet in Zoho |

- **Apolonija 127 and 300 are Deleted in Alchemer** (since 8 Nov 2024) but Complete in the DB; the load links them. Clinicdash counts Deleted responses when linked, so a resync alone won't hide them.
- **Zoho's Apolonija `JOINED` drops 136 responses (Mar–Aug 2026)**; its raw table `Apolonija_export_FINAL` has them. Clinicdash is right.
- **Arcadia 2267 is stored twice** (good API copy + broken webhook copy dated 1970, DB id 309489). The only duplicate in the 3 surveys.
- Alchemer's API cannot filter by response id; single responses were opened with `get_response` (Ana's permission), nothing kept but status, dates, score, sguid.
- Zoho via Zamera: 20 rows per query (pack ids with `GROUP_CONCAT` per month) and "Access Denied" / error 6045 after a burst; wait 10–30 min.

**Open, in order:**
1. **Karlo (COPS-224):** A1 pick the Patient for 93 Arcadia responses; A2–A6 and B1–B3 confirmations; C1 written sign-off per Account (closes DEV-184).
2. **Ana decides:** exclude Apolonija 127 and 300 from the load (recommended), or wait for a dev resync. Excluding = config change, re-render, mock test, Apolonija staging rerun.
3. **After Karlo's A1 answers:** link the decided reused-id responses (config change, re-render, mock test, Arcadia staging rerun).
4. **Claude, before production (DEV-162):** make `99_rollback.sql` faster (Apolonija took 35 min on staging), re-test on staging; write each Account's `PRODUCTION.md`.
5. **Dev ticket (not opened yet):** delete the broken Arcadia 2267 copy and find why the webhook stored it; resync deletions from Alchemer.
6. **Ana / clinic:** C04 (Videntis' responses whose invite is missing), C05 / C06 (Apolonija's rows without id and `#N/A` ids).
7. After ops sign-off: drop the staging tables with patient data (`stg_videntis_full`, `stg_arcadia_full`, `stg_apolonija_full`, and SIE's old `stg_sie_full`).

**Where things are:**
- Local, git-ignored: patient files and load files in `accounts/<account>/data/`; the checklist and exports in `out/`; comparison data in `out/dev162/`.
- Rebuild the checklist: `.venv/bin/python -I tools/dev162/build_checks_workbook.py "$PWD" out/dev162/unlinked.tsv out/DEV-162_checks.xlsx`.
- Rebuild the ops workbooks (inputs in `out/dev184/`, from staging, prod replica, Zoho and Alchemer on 4 Nov 2026): `.venv/bin/python -I tools/dev184/build_differences_workbook.py "$PWD" out/dev184 out/DEV-184_legacy_differences_2026-11-04.xlsx` and `.venv/bin/python -I tools/dev184/build_platform_differences_workbook.py out/dev184 out/DEV-184_platform_era_differences_2026-11-04.xlsx`.
- Staging runs: `bash tools/run_staging.sh <account> <clinic csv>` (refuses anything but `insider-eu-stg`). Production is never run by Claude without Ana's explicit permission.
- Zoho through Zamera blocks the token after a burst of calls ("Access Denied"); wait and retry, keep calls few.

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
