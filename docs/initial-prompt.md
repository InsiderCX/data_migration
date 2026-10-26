# Initial prompt for Claude Code

Paste the block below into Claude Code, opened in the root of the (empty, cloned) repo after copying in the contents of `legacy-imports-kit/`. Put the PII files (load file, clinic file, Alchemer/BI export) into `accounts/sie/data/` yourself; they are git-ignored.

---

```text
You are setting up and maintaining the "legacy imports" repo for InsiderCX. It holds everything needed to import an
Account's pre-platform survey history into the InsiderCX database, validate it with ops, run it on production, and
repeat the process for other Accounts.

Start by reading, in this order: CLAUDE.md, README.md, docs/playbook.md, docs/design.md, docs/database-facts.md,
docs/pitfalls.md, docs/ops-validation.md, accounts/sie/README.md, accounts/sie/PRODUCTION.md. Follow CLAUDE.md strictly:
you may read databases only through the Zamera MCP connector (read-only prod replicas, EU and UK), you never write to any
database, and patient data never goes into git.

Context: the first Account, Stomatologija i estetika (EU, load code SIE_LEGACY_V4), is validated on EU staging and
confirmed by ops. Its scripts in accounts/sie/ are the reference implementation and must keep working exactly as they are.

Phase 1 - repo baseline (do now)
1. Check the repo layout matches README.md. Make sure .gitignore keeps accounts/*/data/ and accounts/*/out/ out of git,
   and that no file in the repo contains patient rows (names, phones, clinic source ids). Report anything suspicious
   instead of committing it.
2. Make the SIE mock test runnable on this machine: tests/run_mock_test.sh expects PostgreSQL 16 binaries and root.
   If they are not available, add a Docker-based path (postgres:16 image) without changing what the test checks.
   Run it: bash accounts/sie/tests/run_mock_test.sh accounts/sie/data/Pacijenti_JOINED_Stomatologija_i_estetika.csv
   Expected: load OK, validation counts as in accounts/sie/README.md §8, export identical to the original file,
   ops exports without errors, rollback and cleanup back to baseline, 01 refuses with leftovers.
   Also exercise sql/08_ops_lists.sql + scripts/3_build_ops_workbook.py on the mock (add it to the test).
3. Rebuild the load file from the inputs (README §5) and confirm its SHA-256 equals the one in PRODUCTION.md.
4. On the EU prod replica, re-verify every fact in docs/database-facts.md for Account 36 and survey 90558103
   (trigger definition, identity columns, foreign keys, unique index, extensions). Record the date verified.
5. Commit with a clear message. Show me the summary before pushing.

Phase 2 - make the next Account cheap (propose first, then do after I approve the plan)
Goal: a new Account = a new folder + a config file + its input files, with no hand-editing of SQL.
- Split what is shared (the 3 legacy tables + trigger fallback in 01, rollback/cleanup logic, mock schema, ops workbook
  script, report queries) from what is Account-specific (Alchemer survey id, Account name, time zone, load code,
  source file name, builder constants, expected counts, BI export).
- Introduce accounts/<account>/account.yaml (or .toml) with those values, and a small render step that produces the
  Account's sql/ from templates. Builders read their constants from the config.
- Add accounts/_template/ and a short "new Account" checklist to docs/playbook.md.
- Acceptance: re-rendering SIE from its config gives SQL that is functionally identical to today's (diff and explain
  every change), the rebuilt load file has the same SHA-256, and the SIE mock test passes unchanged.

Phase 3 - production for SIE (only when I say "go for production")
Prepare, don't execute: walk me through accounts/sie/PRODUCTION.md step by step, give me each SQL file to run in my SQL
client, and check every result I paste back against the expected values before telling me the next step. After the load,
rebuild the ops deliverables from the production exports (07 R1/R2/R5/R6/R7 and 08), update the status table in
README.md and the account card, and list what I still have to do manually (Clinicdash check, drop staging table,
delete local PII files, tell the CSM which figures are estimates).

Working style: plain English, short. Say what you tested and what only a person can test. Never claim a staging or
production result you did not see pasted back.
```

---

## Using it for a new Account later

After Phase 2 is done, start a new Claude Code session in the repo with:

```text
Read CLAUDE.md and docs/playbook.md. We are starting a legacy import for Account "<name>".
The inputs are in accounts/<slug>/data/: <clinic file>, <Alchemer export>, <BI export if any>.
Do playbook step 1 (discovery) on the prod replicas and write the account card. Stop and show me the findings,
the proposed estimates (step 2) and anything that differs from SIE before building.
```
