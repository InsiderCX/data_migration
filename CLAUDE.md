# CLAUDE.md: legacy imports

Read `README.md`, then `docs/playbook.md`, before doing anything. For an existing Account, also read its `accounts/<account>/README.md` and `PRODUCTION.md`.

## What you can and cannot touch

- **Databases.** Use the Zamera MCP connector (`InsiderCX_Zamera_Central`): `icx-prod-eu__execute_sql`, `icx-prod-uk__execute_sql`. These are **read-only replicas of production**. Staging is **not** reachable from here. Use the `icx-database` skill for schema, domain terms and metric definitions.
- **Never write to any database**, and never ask for write credentials. You prepare SQL. Ana (or another person with write access) runs it in a GUI SQL client on staging, then production, and pastes results back.
- **EU vs UK.** An Account lives in exactly one region. Resolve it by name in both regions first. Every script resolves ids from the Account's Alchemer survey id, never from hard-coded database ids.
- **Patient data.** `accounts/*/data/` and `accounts/*/out/` hold PII and are git-ignored. Never commit a CSV, XLSX or JSON with patient rows. Never print names, phones, `source_id`, `year_of_birth`, `surveyData` or comments in bulk. Use aggregates; when a row list is needed, use ids (Alchemer response id, legacy invite id, `visit_msg.id`).
- **Prod replica queries.** Always filter by Account and date; large result sets come back as files, so parse them with Python rather than reading them into the conversation.

## How SQL in this repo must be written (the person runs it in a GUI)

- No psql meta-commands (`\set`, `\copy`, `\i`). Plain SQL only.
- One file = one purpose. Loads are a single `BEGIN … COMMIT` with `DO $$ … RAISE EXCEPTION` checks **before** and **after** writing. A failed check must leave nothing behind.
- Guards first: resolve the Account through `survey."alchemerId"`, check the Account name, refuse if the load code already exists, refuse if staging is missing or was type-converted by the GUI.
- Staging tables are created by our own SQL with **all columns `text`** and no key (GUIs auto-type phones as integers and add primary keys).
- Validation queries: one result set per query, every column aliased (GUIs show only the last result and collapse duplicate column names).
- Explicit ids on identity columns need `OVERRIDING SYSTEM VALUE`. Delete `visit_msg_sending_batch` rows **before** the `patient_visit` rows they reference.
- Dashboard numbers use Clinicdash definitions exactly: NPS rows dated by `"dateStarted"`, Message performance by `sent_at`, response rate over delivered, half-up rounding `floor(1000.0*n/d + 0.5)/10`.

## Before you hand anything over

1. Run the Account's mock test: `bash accounts/<account>/tests/run_mock_test.sh <original clinic csv>`. Everything must pass: load, validation, export identical to the original, ops exports run, rollback and cleanup back to baseline.
2. If you changed a builder script, rebuild the load file and compare its SHA-256 with the one in the Account card. A change in hash must be intentional and recorded.
3. Re-check on the prod replica any schema fact you rely on (`docs/database-facts.md`). Schema drift is the main risk.
4. Say plainly what you tested and what only a person can test (staging, Clinicdash, production).

## Writing style for docs and messages

Plain English, short sentences, InsiderCX terms from the `icx-database` glossary (Account, Location, Survey Response, Visit Msg, Survey Invite). Say which numbers are real and which are estimated, every time.
