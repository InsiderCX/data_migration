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

## The next two Accounts: Orto-Nova and Affidea (files from Karlo, 24 Nov 2026)

Linear: Orto-Nova [DEV-406](https://linear.app/insidercx/issue/DEV-406) build → [DEV-408](https://linear.app/insidercx/issue/DEV-408) staging → [DEV-410](https://linear.app/insidercx/issue/DEV-410) production; Affidea [DEV-407](https://linear.app/insidercx/issue/DEV-407) → [DEV-409](https://linear.app/insidercx/issue/DEV-409) → [DEV-411](https://linear.app/insidercx/issue/DEV-411). Ana's manual check of all three: [DEV-412](https://linear.app/insidercx/issue/DEV-412), then the ops validation goes to Karlo (COPS task by Ana).

| | Orto-Nova | Affidea |
|---|---|---|
| Account / Locations / Surveys (EU prod) | 49 / 1 / **three** (90492015 HR, 90509784 IT, 90509787 SLO) | 27 / 4 (Čavka, Kalajžić, Sv. Rok, Vita) / 90540487 |
| Legacy rows | 25,839, no date, phone or source id; id = invite type digit + counter | 36,437, real SMS status (`GROUP_NAME`), no dates |
| Linked responses | 1,995 | 7,628 (3,532 more point to invites missing from the file) |
| Details | [`accounts/ortonova/README.md`](../../accounts/ortonova/README.md) | [`accounts/affidea/README.md`](../../accounts/affidea/README.md) |

## Status (25 Nov 2026)

- Steps 0–4 done for all three Accounts: discovery, account cards, Colić conversion, load files, mock tests (ALL CHECKS PASSED). PR #11.
- Ana (25 Nov): build without waiting for Karlo; his questions and the assumptions the build makes are in DEV-377, DEV-408, DEV-409, to confirm during validation.
- Builder and SQL got opt-in options (one id sequence, every legacy row sent, age at the visit, `GROUP_NAME` status, send date from the own response, rate tolerance, more Surveys per Account). The six done Accounts rebuild byte-identical and still pass their mock tests.
- Step 5, EU staging: Claude runs `tools/run_staging.sh` with Ana's permission for staging only (25 Nov, over her VPN). Colić done (batch 13111). Orto-Nova and Affidea running.
- Found on staging: Orto-Nova's legacy scores on the staging copy differ from prod (about 620 score 5 on staging, mostly 10 on prod). Staging NPS for Orto-Nova is not meaningful; counts are.
- Found on staging: `99_rollback` is slow because `legacy_source_row` (visit_msg_id, patient_visit_id, patient_id) and `legacy_invite_map` (visit_msg_id) have no index. Colić 14 min; Orto-Nova and Affidea hours. Matters for production (rollback plan).

## Where we stopped (25 Nov 2026, ~15:45) — start here on 26 Nov

Branch `feat/DEV-375-legacy-import-next-three`, **PR #11** open (assigned to Ana). Everything below is committed there.

**Done**
- All three Accounts built and mock-tested (ALL CHECKS PASSED); the six done Accounts still rebuild byte-identical.
- Alchemer and Zoho comparison: no unexplained difference (`docs/validation/2026-11-25_alchemer_zoho_dev375.md`).
- **Bolnica Colić on EU staging: done.** Final batch **13111**, 720 linked, export identical, rollback tested (14 min). Run log `accounts/bolnicacolic/runs/2026-11-25_staging.md`.
- DEV-412 (Ana's manual check) created and filled; Karlo's questions and the build's assumptions are in DEV-377 / DEV-408 / DEV-409.

**Running when we stopped: Orto-Nova on EU staging**
- Steps 1–6 passed: batch **13112**, 25,839 invites, **1,995 linked**, 25,663 new Patients, 0 existing Patients changed, export identical (log copy: `accounts/ortonova/out/stg_run_2026-11-25_partial.log`, git-ignored).
- Step 7 (`99_rollback`) was still running at 15:45 (Visit Msgs deleted, Patient Visits in progress; estimate end ~17:15–17:30), then step 8 reloads.
- It ends safely either way: if Ana's VPN dropped, the rollback transaction is undone and Orto-Nova **stays loaded as batch 13112**. If it finished, Orto-Nova is loaded again under a new batch id.

**Tomorrow, in this order**
1. VPN on. Read-only check of Orto-Nova on staging: `SELECT sending_batch_id, loaded_at FROM legacy_sending_batch WHERE code = 'ORTONOVA_LEGACY_V1';` (expect exactly 1 row), plus `03` query 1 (expect 35,557 / 25,839 / 25,839 / 1,995 / 0 deleted / 0 changed / 0 without Patient). Note whether the rollback test completed.
2. Write `accounts/ortonova/runs/2026-11-25_staging.md` (results above; staging scores for Orto-Nova differ from prod, see below).
3. **Affidea staging run**: `bash tools/run_staging.sh affidea Pacijenti_JOINED_Affidea.csv`. Load and checks take minutes; the rollback test takes hours (no index, below). Ana decides: run the rollback test at a quiet time, or skip step 7 for Affidea (proven in the mock test). Check Affidea's staging scores against prod too.
4. Update DEV-412 with the Orto-Nova and Affidea staging numbers; commit run logs to PR #11. Then Ana does DEV-412; after it, the ops validation goes to Karlo (COPS task by Ana).

**Known issues found on 25 Nov**
- **Orto-Nova scores on staging are wrong** (about 620 legacy responses have score 5 on staging, mostly 10 on prod). Staging NPS ~15, prod/Zoho 84–90. Counts are right. Written in DEV-412.
- **Slow rollback:** `legacy_source_row` (`visit_msg_id`, `patient_visit_id`, `patient_id`) and `legacy_invite_map.visit_msg_id` have no index, so `99` scans them per deleted row (Colić 14 min, Orto-Nova ~2.5 h, Affidea est. 3.5–4 h). Matters for the production rollback plan. Possible dev ticket (indexes); Ana decides.
- **Staging schema change by the app:** from 14:14 the staging app user (`app_platform_stg`) kept trying `ALTER TABLE account ADD COLUMN manual_patient_tickets_enabled`, blocked by 17 sessions of two personal DB users. Not caused by our run. Ana: no ALTER TABLE should be done there; raise with the team.
- `tools/run_staging.sh` puts the staging password on the `psql` command line (visible in a process list). Fix with `~/.pgpass`; not changed yet.
- Lesson: a wait loop with `pgrep -f "<text>"` matches its own command line; wait on a PID instead.

**Later**
- `PRODUCTION.md` for each Account (DEV-378 / DEV-410 / DEV-411), including the rollback-time decision.
- Karlo's answers may change the builds (rebuild + staging rerun).
