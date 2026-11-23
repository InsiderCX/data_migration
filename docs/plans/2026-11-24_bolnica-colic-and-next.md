# Plan: legacy import for Bolnica Colić and the next two Accounts

Linear: [DEV-375](https://linear.app/insidercx/issue/DEV-375/legacy-imports-bolnica-colic-and-the-next-two-accounts) (parent) · Bolnica Colić: [DEV-376](https://linear.app/insidercx/issue/DEV-376/bolnica-colic-build-and-mock-test-the-legacy-import) build → [DEV-377](https://linear.app/insidercx/issue/DEV-377/bolnica-colic-load-to-eu-staging-and-prepare-the-ops-package) staging → [DEV-378](https://linear.app/insidercx/issue/DEV-378/bolnica-colic-upload-the-legacy-data-to-production) production · Owner: Ana · Written 23 Nov 2026, starts 24 Nov 2026

Follows `docs/playbook.md`. Commits `refs DEV-376` (or the sub-issue being worked on). Branch: `feat/DEV-376-legacy-import-bolnica-colic`.

## Where we start (23 Nov 2026)

- The six Accounts of DEV-185 are on EU prod (23 Nov 2026), ops signed off in COPS-338 (Karlo, 23 Nov). Run sheet: `docs/production-run-2026-11-23.md`; run logs: `accounts/*/runs/2026-11-23_production.md`.
- Karlo confirmed in Slack (DM, 23 Nov) that the next Accounts can start. Ana chose to start with **Bolnica Colić**; Karlo sends **two more Accounts on 24 Nov 2026**. When they arrive, add them to DEV-375 with their own three sub-issues (build, staging, production) and a section in this plan.
- Ops tasks (COPS) are created by Ana when each Account is ready for ops. Claude prepares the text, does not create them.
- Open from DEV-185: delete local PII of the six Accounts now that COPS-338 is done (`accounts/{opticalexpress,kvaternik,arcadia,videntis,mazalin,apolonija}/data/` and `out/`, `~/Downloads/export_prod_*`, `~/Downloads/apoonij_pt2.csv`, the Kvaternik/Mazalin clinic files in `~/Downloads`). Ask Ana before deleting. Tell the CSMs that legacy message figures are estimates (Ana).

## Bolnica Colić: what we know (EU prod replica, 23 Nov 2026, real numbers)

| | |
|---|---|
| Account name | Bolnica Colić (EU; not found in UK) |
| Account / Location / Survey id (EU prod) | 68 / 259 / 47 |
| Alchemer survey | 90511513 |
| Location time zone | `Europe/Belgrade` (the six others use `Europe/Zagreb`; same offset, but check the scripts use the Location's own zone) |
| Survey Responses | 900, of which **746 without a Visit Msg** |
| First platform invite | **11 Nov 2026** |
| Files (Slack DM from Karlo, 11 Nov 2026) | `Pacijenti_DrColic.csv` (180.7 KB), `Survey_responses_DrColic.csv` (417.3 KB) |

Karlo's note: the patient file still has the **old table structure**; convert it to the current format (the one of the six done Accounts, e.g. `Pacijenti_Joined_Mazalin.csv`).

## Risks to settle early

1. **Thin platform history.** The Account has been on the platform only since 11 Nov 2026 (~2 weeks). The playbook fits estimates (send date, delivery rate, response rate, visit→send) to the Account's own platform data. That is not enough here. Propose the benchmark source (e.g. similar EU Accounts, or the 2 weeks plus a sanity check) and get Ana's approval before building. Say which numbers are real and which are estimated.
2. **Old file structure.** Map every old column to the current one, list what is missing, and keep the conversion as a script in `accounts/bolnicacolic/scripts/` so it can be rerun.
3. **Few platform rows.** Most of the file will be legacy. Check how many rows already exist on the platform (file `id` = `visit_msg.id`, or `source_id` + date).
4. **Staging age.** Staging is a 28 Sep 2026 prod copy, so the Account may have no Visit Msgs there, or not exist. Check first (DEV-377 step 1); ask for a fresh copy if needed.
5. **Lessons from 23 Nov** (write them into `docs/pitfalls.md` if not there yet): Beekeeper "Automatically Trim Whitespace" must be off; Beekeeper splits two-byte characters at 64 KB chunk edges (check the load file for chunk edges inside a character before the import); Beekeeper exports are capped at 50,000 rows.

## Steps (a human gate after each: overview, then wait for Ana)

| # | Do | Linear | Done when |
|---|---|---|---|
| 0 | Ana saves Karlo's two files into `accounts/bolnicacolic/data/`; Claude checks rows, columns, encoding (aggregates only) | DEV-376 | Files read, nothing printed in bulk |
| 1 | Discovery on the prod replica (playbook §1); account card `accounts/bolnicacolic/README.md` | DEV-376 | Card has every §1 fact |
| 2 | Conversion of the old file structure to the current one; rows already on the platform vs legacy; link check `sguid = id` for the 746 unlinked | DEV-376 | Ana approves the mapping |
| 3 | Estimates: benchmark proposal, then `scripts/1_build_load_file.py` `CONFIG` block (code below `CONFIG` identical to the other Accounts) | DEV-376 | Ana approves the estimates |
| 4 | `sql_config.json`, render `01 02 03 04 99`, mock test | DEV-376 | `ALL CHECKS PASSED`, hash in the card; other Accounts still rebuild byte-identical if the builder changed |
| 5 | EU staging run (Ana, or Claude through `tools/run_staging.sh` only if Ana allows it again for this Account) | DEV-377 | `03` passes, `04` identical, `99` tested once |
| 6 | Alchemer and Zoho comparison per month; ops package; COPS text for Ana | DEV-377 | Every difference explained |
| 7 | After ops sign-off: freeze scripts, preflight, production session like 23 Nov | DEV-378 | Run log merged |

## How we work

- Claude reads the prod replicas only and never writes to a database. Ana runs every write in Beekeeper. Permission to write to staging (DEV-232) does not carry over: ask again.
- No patient data in git or in the conversation: aggregates and ids only.
- Git: one branch per sub-issue, Conventional Commits with `refs DEV-xxx`, PR template, merge commits only, no AI attribution lines.
