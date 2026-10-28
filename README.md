# Legacy imports

Bringing an Account's **pre-platform history** (survey invites sent outside InsiderCX, and the responses they got) into the InsiderCX database, so Clinicdash shows it like any other period, ops can validate it, and the clinic's original file can be exported back unchanged.

The first Account done this way is **Stomatologija i estetika** (`accounts/sie/`). The method is written down so the next Account follows the same path.

## Layout

```
README.md                 this file
CLAUDE.md                 rules for Claude Code in this repo (read first)
docs/
  playbook.md             step by step: from "the clinic sent us an old file" to production
  design.md               the data model (v4): what is created, how it is marked, how it links
  database-facts.md       schema facts the scripts depend on (re-verify before every new Account)
  pitfalls.md             what went wrong before and how the scripts now prevent it
  ops-validation.md       what ops get (exports, workbook, visual report) and how to read it
  initial-prompt.md       the prompt that bootstrapped this repo in Claude Code
accounts/
  <account>/              one folder per Account, self-contained
    README.md             account card: ids, inputs + hashes, assumptions, results, status
    PRODUCTION.md         go/no-go + production steps for this Account
    sql/                  00 cleanup, 01 before import, 02 load, 03 validation, 04 export original,
                          05 ops field exports, 06 BI comparison, 07 report by period, 08 ops lists, 99 rollback
    scripts/              build the load file (1, 2) and the ops workbook (3)
    tests/                local PostgreSQL mock with the real constraints
    runs/                 one log per staging / production run: what was run, results, open items
    data/                 inputs and load file - CONTAINS PATIENT DATA, never committed
    out/                  exports and workbooks - never committed
```

## Status

| Account | Region | Load code | Staging | Ops | Production |
|---|---|---|---|---|---|
| Stomatologija i estetika (`sie`) | EU | `SIE_LEGACY_V4` | validated 23–26 Oct 2026 | confirmed | **loaded 28 Oct 2026** (batch 13128); follow-ups open, see `accounts/sie/runs/2026-10-28_production.md` |

## Ground rules (short version; full list in `CLAUDE.md`)

- Claude Code **reads** databases through the Zamera connector (read-only prod replicas). It never writes to stg or prod. A person with write access runs the scripts in a SQL client.
- Every load is one transaction, checks itself, and has a rollback. Nothing existing is updated except filling empty response links.
- Patient data never enters git: `data/` and `out/` are ignored. Exports for ops carry no names, phones or comments.
- Estimated values are always labelled as estimated, in the database (`legacy_sending_batch.comment`), in exports and in reports.
