"""Build a read-only 00_preflight.sql per Account for the DEV-185 production run.

It repeats the id checks of 02_load.sql before anything is written, without the staging table:
the Visit Msg ids the load will create must not exist yet, legacy rows must not already be Visit Msgs,
the expected unlinked legacy Survey Responses must still be there, and the load must not be present.

Settings come from the frozen production/DEV-185/<n>_<account>/02_load.sql; ids from the load file.
Output: accounts/<account>/out/00_preflight.sql (git-ignored: it holds legacy link ids).

Usage: python3 -I tools/preprod/build_preflight.py
"""
import csv
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "production" / "DEV-185"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def one(pattern, text, what):
    m = re.search(pattern, text)
    if not m:
        sys.exit(f"{what} not found")
    return m.group(1)


def q(v):
    return "NULL" if v is None else "'" + v.replace("'", "''") + "'"


def build(folder):
    account = folder.name.split("_", 1)[1]
    load = (folder / "02_load.sql").read_text()
    cfg = {
        "alchemer_id": one(r"\"alchemerId\"::text = '(\d+)'", load, "alchemer id"),
        "name": one(r"name = '([^']+)'\) THEN", load, "Account name"),
        "n_locations": one(r"n_locations <> (\d+)", load, "Locations"),
        "code": one(r"code = '([A-Z0-9_]+)'", load, "load code"),
        "source_file": one(r"'([^']+)'::text AS source_file", load, "source file"),
        "expected_unlinked": one(r"IF n <> (\d+) THEN RAISE EXCEPTION 'unlinked legacy responses", load, "expected unlinked"),
    }
    ns, slug = re.search(r"uuid_generate_v5\('([0-9a-f-]+)'::uuid, '([a-z]+-legacy-)' \|\| row_no\)", load).groups()
    uuid_ids = "uuid_legacy_ids" in load
    # the trigger body 01_before_import.sql installs; prod must already have exactly this one
    before = (folder / "01_before_import.sql").read_text()
    body = re.search(r"FUNCTION public\.survey_response__set_visit_msg_id_from_sguid\(\).*?AS (\$\w*\$)(.*?)\1", before, re.S).group(2)
    trigger_md5 = hashlib.md5(body.encode()).hexdigest()

    rows = []
    with open(ROOT / "accounts" / account / "data" / f"{account}_full_v1.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["row_kind"] not in ("legacy_invite", "legacy_visit"):
                continue
            legacy = r["legacy_sguid"].strip() or None
            link = r["link_sguid"] or None                     # exactly as Alchemer stores it
            reused = r["sguid_reused"].strip() == "true"
            has_resp = r["has_response"].strip() == "true"
            raw_id = r["raw_id"].strip()
            vm_id = None
            if r["row_kind"] == "legacy_invite":
                vm_id = legacy if (uuid_ids and not reused and legacy and UUID_RE.match(legacy)) else ""   # "" = v5 below
            raw_uuid = raw_id if UUID_RE.match(raw_id) else None
            if vm_id is None and raw_uuid is None:
                continue
            rows.append(f"({r['row_no']},{q(vm_id)},{q(raw_uuid)},{q(link if has_resp else None)})")

    sql = f"""-- {cfg['name']} ({cfg['code']}): READ-ONLY preflight for the DEV-185 production run. Writes nothing.
-- Built by tools/preprod/build_preflight.py from production/DEV-185/{folder.name}/02_load.sql and {account}_full_v1.csv.
-- One result row. Expected: database insider-prod, account_ok true, every *_present / *_already_* = 0,
-- unlinked_legacy_responses = expected_unlinked, trigger_same_as_01 true.
WITH ids(row_no, vm_id, raw_uuid, link_sguid) AS (VALUES
{','.join(rows)}
), cfg AS (
  SELECT s.id AS survey_id, s."accountId" AS account_id FROM public.survey s WHERE s."alchemerId"::text = '{cfg['alchemer_id']}'
), new_ids AS (
  SELECT CASE WHEN vm_id = '' THEN uuid_generate_v5('{ns}'::uuid, '{slug}' || row_no) ELSE vm_id::uuid END AS id
  FROM ids WHERE vm_id IS NOT NULL
)
SELECT current_database()                                                                              AS database,
       (SELECT count(*) FROM cfg)                                                                       AS surveys_found,        -- 1
       (SELECT a.name = '{cfg['name'].replace("'", "''")}' FROM public.account a JOIN cfg ON a.id = cfg.account_id) AS account_ok,
       (SELECT count(*) FROM public.location l JOIN cfg ON l.account_id = cfg.account_id)              AS locations,            -- {cfg['n_locations']}
       (SELECT count(*) FROM public.legacy_sending_batch WHERE code = '{cfg['code']}')                  AS load_code_present,    -- 0
       (SELECT count(*) FROM public.legacy_source_row r JOIN cfg ON r.account_id = cfg.account_id
          WHERE r.source_file = '{cfg['source_file']}')                                                 AS source_rows_present,  -- 0
       (SELECT count(*) FROM new_ids)                                                                   AS new_visit_msg_ids,
       (SELECT count(*) FROM new_ids n JOIN public.visit_msg vm ON vm.id = n.id)                        AS new_ids_already_present, -- 0
       (SELECT count(*) FROM new_ids n JOIN public.visit_msg vm ON vm.invite_id = n.id)                 AS new_invite_ids_already_present, -- 0
       (SELECT count(*) FROM ids i JOIN public.visit_msg vm ON vm.id = i.raw_uuid::uuid
          JOIN cfg ON vm.account_id = cfg.account_id)                                                   AS legacy_rows_already_visit_msgs, -- 0
       (SELECT count(*) FROM ids i JOIN public.survey_response sr ON sr."surveyId" = (SELECT survey_id FROM cfg)
          AND sr.sguid = i.link_sguid AND sr.visit_msg_id IS NULL)                                      AS unlinked_legacy_responses,
       {cfg['expected_unlinked']}                                                                       AS expected_unlinked,
       (SELECT md5(p.prosrc) = '{trigger_md5}' FROM pg_proc p
          WHERE p.proname = 'survey_response__set_visit_msg_id_from_sguid')                             AS trigger_same_as_01;
"""
    out = ROOT / "accounts" / account / "out" / "00_preflight.sql"
    out.parent.mkdir(exist_ok=True)
    out.write_text(sql)
    print(f"{folder.name}: {len(rows)} id rows, expected unlinked {cfg['expected_unlinked']}, "
          f"uuid ids {uuid_ids}, {out.stat().st_size // 1024} KB -> {out.relative_to(ROOT)}")


for folder in sorted(PROD.glob("*_*")):
    build(folder)
