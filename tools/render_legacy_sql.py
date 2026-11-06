"""
Render one Account's load-path SQL (01, 02, 03, 04, 99) from accounts/<account>/sql_config.json.

Usage:
  python3 -I tools/render_legacy_sql.py accounts/<account>                  # write accounts/<account>/sql/*.sql
  python3 -I tools/render_legacy_sql.py accounts/<account> --update-expect  # first copy the counts from the load file
                                                                            # (data/<load_file>) into the config

The rendered .sql files are what a person runs in the GUI. Every Account gets the same SQL; only the config differs.
Written for the Videntis / Arcadia / Apolonija imports (DEV-162). SIE's hand-written SQL in accounts/sie/ is unchanged.
DEV-232 config keys (left out = DEV-162 SQL, unchanged): "layout": 2 (real SMS statuses, status_source in meta,
language_out, Location per row by name), "link_responses": false (append only: no legacy_invite_map rows, responses
untouched), "n_locations".
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(sys.argv[1])
CFG_PATH = ROOT / "sql_config.json"
C = json.loads(CFG_PATH.read_text())

if "--update-expect" in sys.argv:
    import pandas as pd
    o = pd.read_csv(ROOT / "data" / C["load_file"], dtype=str, keep_default_na=False)
    k = o.row_kind.value_counts()
    legacy = o.row_kind.isin(["legacy_invite", "legacy_visit"])
    inv = o.row_kind == "legacy_invite"
    C["expect"] = {
        "rows": len(o),
        "platform": int(k.get("platform", 0)),
        "legacy_invite": int(k.get("legacy_invite", 0)),
        "legacy_visit": int(k.get("legacy_visit", 0)),
        "legacy_raw": int(k.get("legacy_raw", 0)),
        "linked": int((o.has_response == "true").sum()),
        "mapped_link": int((inv & (o.link_sguid != "")).sum()),
        "reused_invites": int((inv & (o.sguid_reused == "true")).sum()),
        "legacy_no_phone": int((legacy & (o.phone_clean == "")).sum()),
    }
    if C.get("link_responses", True) is False:  # answered = real responses on legacy invites; nothing gets linked
        C["expect"].update(answered=C["expect"]["linked"], linked=0, mapped_link=0)
    CFG_PATH.write_text(json.dumps(C, indent=2, ensure_ascii=False) + "\n")
    print("expect:", C["expect"])

X = C["expect"]
T = C["staging_table"]
CODE = C["code"]
AL = C["alchemer_id"]
SRC = C["source_file"]
RAW = C["raw_columns"]
R = lambda c: "raw_" + c.lower()          # staging column for an original column
q = lambda s: "'" + s.replace("'", "''") + "'"
HEAD = f"-- {C['account_name']} legacy import ({CODE}). Rendered by tools/render_legacy_sql.py from sql_config.json - do not edit by hand.\n"

V2 = C.get("layout", 1) == 2
LINK = C.get("link_responses", True)
ANS = X.get("answered", X["linked"])      # real responses on legacy invites (= linked unless link_responses is false)
NLOC = C.get("n_locations", 1)
STG_COLS = (["row_no", "row_kind"] + [R(c) for c in RAW] +
            ["legacy_sguid", "link_sguid", "sguid_reused", "phone_clean", "est_visit_date", "est_sent_at", "est_status",
             "has_response", "procedure_out", "derived_year_of_birth", "sort_ts"] +
            (["status_source", "language_out", "location_name"] if V2 else []))
LOC = "s.loc_id" if V2 else "c.location_id"                   # Location of a legacy row
LANG = "s.language_out" if V2 else "upper(btrim(s.raw_language_code))"
STATUSES = "'DELIVERED','UNDELIVERABLE','EXPIRED','REJECTED','PENDING'" if V2 else "'DELIVERED','UNDELIVERABLE'"
SMS_NAME = ("CASE s.est_status WHEN 'DELIVERED' THEN 'DELIVERED_TO_HANDSET' WHEN 'EXPIRED' THEN 'EXPIRED_EXPIRED'\n"
            "         WHEN 'REJECTED' THEN 'REJECTED_NETWORK' WHEN 'PENDING' THEN 'PENDING_ACCEPTED' ELSE 'UNDELIVERABLE_NOT_DELIVERED' END"
            if V2 else "CASE s.est_status WHEN 'DELIVERED' THEN 'DELIVERED_TO_HANDSET' ELSE 'UNDELIVERABLE_NOT_DELIVERED' END")
META = "hstore(ARRAY['send_algo', 'legacy_import', 'status_source', s.status_source])" if V2 else "hstore('send_algo', 'legacy_import')"

# ------------------------------------------------------------------------------------------------ 01
s01 = HEAD + f"""-- Part 1: EVERYTHING BEFORE THE CSV IMPORT. Run the WHOLE file once.
-- 1) stop if this Account's load is already (partly) there   2) make sure the legacy tables and trigger fallback exist
--    (they already exist where SIE was loaded; CREATE ... IF NOT EXISTS / OR REPLACE leaves them as they are)
-- 3) create the empty staging table {T} (all text, no key)
-- After this: import {C['load_file']} INTO {T}, run the count check at the bottom, then 02_load.sql.
-- On any error: run ROLLBACK; and send the message.

BEGIN;

DO $$ DECLARE acc int; n int; BEGIN
  SELECT count(*), min("accountId") INTO n, acc FROM public.survey WHERE "alchemerId"::text = {q(AL)};
  IF n <> 1 THEN RAISE EXCEPTION 'Survey {AL} found % times - wrong database (EU vs UK?) or data not present', n; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.account WHERE id = acc AND name = {q(C['account_name'])}) THEN
    RAISE EXCEPTION 'Account % is not {C['account_name']}', acc; END IF;
  IF to_regclass('public.legacy_source_row') IS NOT NULL THEN
    EXECUTE 'SELECT count(*) FROM public.legacy_source_row WHERE account_id = $1 AND source_file = $2' INTO n USING acc, {q(SRC)};
    IF n > 0 THEN RAISE EXCEPTION '{SRC} is already loaded (% rows) - run 99_rollback.sql first if you mean to reload', n; END IF;
  END IF;
  IF to_regclass('public.legacy_sending_batch') IS NOT NULL THEN
    EXECUTE 'SELECT count(*) FROM public.legacy_sending_batch WHERE code = $1' INTO n USING {q(CODE)};
    IF n > 0 THEN RAISE EXCEPTION '{CODE} already exists (% batches) - run 99_rollback.sql first', n; END IF;
  END IF;
  IF EXISTS (SELECT 1 FROM public.visit_msg_sending_batch b WHERE b.account_id = acc AND b.trigger = 'legacy_import') THEN
    RAISE EXCEPTION 'Account % already has a legacy_import sending batch - a leftover; find out where it came from first', acc; END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.legacy_sending_batch (
  sending_batch_id int PRIMARY KEY REFERENCES public.visit_msg_sending_batch(id) ON DELETE CASCADE,
  account_id       int  NOT NULL REFERENCES public.account(id),
  code             text NOT NULL,
  comment          text NOT NULL,
  source_files     text[],
  loaded_by        text,
  loaded_at        timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.legacy_invite_map (
  account_id   int  NOT NULL,
  legacy_sguid text NOT NULL,
  visit_msg_id uuid NOT NULL REFERENCES public.visit_msg(id) ON DELETE CASCADE,
  PRIMARY KEY (account_id, legacy_sguid)
);
CREATE TABLE IF NOT EXISTS public.legacy_source_row (
  account_id       int  NOT NULL REFERENCES public.account(id),
  source_file      text NOT NULL,
  row_no           int  NOT NULL,
  row_kind         text NOT NULL,
  raw              jsonb NOT NULL,
  patient_id       int  REFERENCES public.patient(id)       ON DELETE SET NULL,
  patient_visit_id int  REFERENCES public.patient_visit(id) ON DELETE SET NULL,
  visit_msg_id     uuid REFERENCES public.visit_msg(id)     ON DELETE SET NULL,
  sending_batch_id int  REFERENCES public.visit_msg_sending_batch(id) ON DELETE SET NULL,
  loaded_at        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (account_id, source_file, row_no)
);

-- Link trigger fallback (identical to what SIE installed): uuid sguid as before; other sguids -> legacy_invite_map
CREATE OR REPLACE FUNCTION public.survey_response__set_visit_msg_id_from_sguid()
 RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
  BEGIN
    SELECT id INTO NEW.visit_msg_id FROM public.visit_msg WHERE id = NEW.sguid::uuid;
  EXCEPTION WHEN invalid_text_representation THEN
    SELECT m.visit_msg_id INTO NEW.visit_msg_id
    FROM public.legacy_invite_map m
    JOIN public.survey s ON s.id = NEW."surveyId"
    WHERE m.account_id = s."accountId" AND m.legacy_sguid = NEW.sguid;
  END;
  RETURN NEW;
END $fn$;

DROP TABLE IF EXISTS public.{T};
CREATE TABLE public.{T} (
""" + ",\n".join(f"  {c:<30} text" for c in STG_COLS) + f"""
);

COMMIT;

-- Check: expect legacy_sending_batch | legacy_invite_map | legacy_source_row | {T} | 0
SELECT to_regclass('public.legacy_sending_batch') AS t1,
       to_regclass('public.legacy_invite_map')    AS t2,
       to_regclass('public.legacy_source_row')    AS t3,
       to_regclass('public.{T}')                  AS staging,
       (SELECT count(*) FROM public.{T})          AS staging_rows;

-- After the GUI import, run this on its own. Expect {X['rows']} / {X['platform']} / {X['legacy_invite']} / {X['legacy_visit']} / {X['legacy_raw']}
-- SELECT count(*) AS total, count(*) FILTER (WHERE row_kind = 'platform') AS platform,
--        count(*) FILTER (WHERE row_kind = 'legacy_invite') AS legacy_invite, count(*) FILTER (WHERE row_kind = 'legacy_visit') AS legacy_visit,
--        count(*) FILTER (WHERE row_kind = 'legacy_raw') AS legacy_raw
-- FROM public.{T};
"""

# ------------------------------------------------------------------------------------------------ 02
raw_json = ",\n         ".join(f"{q(c)}, s.{R(c)}" for c in RAW)
raw_sel = ",\n       ".join(f"coalesce({R(c)}::text, '') AS {R(c)}" for c in RAW)
STEP7 = """-- 7) Link table + link the responses ----------------------------------------------------------------------------------
-- Key = the sguid exactly as Alchemer stores it (link_sguid) for answered invites, else the legacy id.
-- Not mapped: reused ids (decision 13) and sguids whose response is Deleted (decision 12).
INSERT INTO public.legacy_invite_map (account_id, legacy_sguid, visit_msg_id)
SELECT c.account_id, coalesce(s.link_sguid, s.legacy_sguid), s.visit_msg_id
FROM stg s CROSS JOIN cfg c
WHERE s.row_kind = 'legacy_invite' AND NOT s.sguid_reused
  AND NOT EXISTS (SELECT 1 FROM public.survey_response sr WHERE sr."surveyId" = c.survey_id AND sr.status = 'Deleted'
                  AND btrim(sr.sguid) = s.legacy_sguid);

UPDATE public.survey_response sr SET sguid = sr.sguid             -- fires the trigger, which fills visit_msg_id
FROM stg s, cfg c
WHERE sr."surveyId" = c.survey_id AND sr.visit_msg_id IS NULL AND sr.sguid = s.link_sguid AND s.has_response;

""".replace("{CODE}", CODE) if LINK else (
    "-- 7) No linking (link_responses false, DEV-232 decision 2): no legacy_invite_map rows, Survey Responses untouched.\n"
    "--    Ops decide; linking later = config change, rebuild, rerun.\n\n")
V2_STG = "" if not V2 else (",\n       NULLIF(btrim(status_source::text), '')                AS status_source,"
                              "\n       NULLIF(btrim(language_out::text), '')                 AS language_out,"
                              "\n       NULLIF(btrim(location_name::text), '')                AS location_name")
LOC_SQL = "" if not V2 else (
    "\n-- Location of each legacy row, resolved by name (never by a hard-coded id)\n"
    "ALTER TABLE stg ADD COLUMN loc_id int;\n"
    "UPDATE stg s SET loc_id = coalesce((SELECT l.id FROM public.location l, cfg c WHERE l.account_id = c.account_id\n"
    "                                      AND l.name = NULLIF(btrim(s.location_name), '')), (SELECT location_id FROM cfg))\n"
    "WHERE s.is_legacy;\n")
V2_CHECKS = "" if not V2 else ("""
  SELECT count(*) INTO n FROM stg WHERE is_legacy AND (loc_id IS NULL OR (NULLIF(btrim(location_name), '') IS NOT NULL
     AND loc_id NOT IN (SELECT l.id FROM public.location l, cfg c WHERE l.account_id = c.account_id AND l.name = btrim(location_name))));
    IF n > 0 THEN RAISE EXCEPTION 'legacy rows whose Location name is not found %', n; END IF;
  -- append only: a legacy row must not be an invite that already exists (the platform rows are those)
  SELECT count(*) INTO n FROM stg s JOIN public.visit_msg vm ON vm.account_id = (SELECT account_id FROM cfg)
     AND btrim(s.raw_id) ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' AND vm.id = btrim(s.raw_id)::uuid
     WHERE s.is_legacy;
    IF n > 0 THEN RAISE EXCEPTION 'legacy rows that already exist as Visit Msgs %', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_invite' AND NULLIF(btrim(status_source), '') IS NULL;
    IF n > 0 THEN RAISE EXCEPTION 'invites without status_source %', n; END IF;""")
LINK_TXT = (f"links {X['linked']} legacy Survey Responses" if LINK else
            f"links NO Survey Responses (link_responses false: the {ANS} real responses stay as they are, no legacy_invite_map rows)")
s02 = HEAD + f"""-- Part 2: the load. Requires 01_before_import.sql, and {C['load_file']} imported into public.{T} (all columns TEXT).
-- Creates: Patients that don't exist yet (existing Patients are never changed); {X['legacy_invite'] + X['legacy_visit']} legacy Patient Visits
-- (never surveyed); 1 mock sending batch with {X['legacy_invite']} legacy invites; {LINK_TXT};
-- stores all {X['rows']} source rows untouched in legacy_source_row. Platform rows ({X['platform']}) are only linked, never created.
-- Run the WHOLE file. Check the GUI's commit mode first. On any error: run ROLLBACK; and send the message.

BEGIN;

-- 0) Resolve this environment -------------------------------------------------------------------------------------
CREATE TEMP TABLE cfg ON COMMIT DROP AS
SELECT s."accountId" AS account_id, s.id AS survey_id,
       (SELECT min(l.id) FROM public.location l WHERE l.account_id = s."accountId") AS location_id,
       (SELECT count(*)  FROM public.location l WHERE l.account_id = s."accountId") AS n_locations,
       (SELECT coalesce(min(l.quarantine_days), 90) FROM public.location l WHERE l.account_id = s."accountId") AS quarantine_days,
       (SELECT a.sms_sender FROM public.account a WHERE a.id = s."accountId") AS sms_from,
       now() AS loaded_at,
       {q(SRC)}::text AS source_file
FROM public.survey s WHERE s."alchemerId"::text = {q(AL)};

DO $$ DECLARE c record; n int; BEGIN
  SELECT count(*) INTO n FROM cfg;
  IF n <> 1 THEN RAISE EXCEPTION 'Survey {AL} found % times - wrong database (EU vs UK?) or data not present', n; END IF;
  SELECT * INTO c FROM cfg;
  IF c.n_locations <> {NLOC} THEN RAISE EXCEPTION 'Account % has % Locations, expected {NLOC}', c.account_id, c.n_locations; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.account WHERE id = c.account_id AND name = {q(C['account_name'])}) THEN
    RAISE EXCEPTION 'Account % is not {C['account_name']}', c.account_id; END IF;
  IF c.sms_from IS NULL THEN RAISE EXCEPTION 'Account % has no sms_sender', c.account_id; END IF;
  IF to_regclass('public.legacy_source_row') IS NULL OR to_regclass('public.legacy_invite_map') IS NULL THEN
    RAISE EXCEPTION 'Run 01_before_import.sql first'; END IF;
  IF EXISTS (SELECT 1 FROM public.legacy_source_row WHERE account_id = c.account_id AND source_file = c.source_file) THEN
    RAISE EXCEPTION 'Source file already loaded'; END IF;
  IF EXISTS (SELECT 1 FROM public.legacy_sending_batch WHERE code = {q(CODE)}) THEN RAISE EXCEPTION '{CODE} already loaded'; END IF;
  IF to_regclass('public.{T}') IS NULL THEN RAISE EXCEPTION 'Import {C['load_file']} into public.{T} first'; END IF;
  RAISE NOTICE 'Using account_id=%, location_id=%, survey_id=%', c.account_id, c.location_id, c.survey_id;
END $$;

-- 1) Stage + type --------------------------------------------------------------------------------------------------
CREATE TEMP TABLE stg ON COMMIT DROP AS
SELECT row_no::int AS row_no,
       btrim(row_kind::text) AS row_kind,
       -- original columns, untouched (NULL from the import tool = empty in the file)
       {raw_sel},
       -- computed by scripts/1_build_load_file.py
       NULLIF(btrim(legacy_sguid::text), '')                AS legacy_sguid,
       NULLIF(link_sguid::text, '')                         AS link_sguid,      -- exactly as Alchemer stores it (may start with a space)
       (btrim(coalesce(sguid_reused::text, '')) = 'true')   AS sguid_reused,
       NULLIF(btrim(phone_clean::text), '')                 AS phone_clean,
       NULLIF(btrim(est_visit_date::text), '')::timestamptz AS est_visit_date,
       NULLIF(btrim(est_sent_at::text), '')::timestamptz    AS est_sent_at,
       NULLIF(btrim(est_status::text), '')                  AS est_status,
       (btrim(coalesce(has_response::text, '')) = 'true')   AS has_response,
       NULLIF(btrim(procedure_out::text), '')               AS procedure_out,
       CASE WHEN NULLIF(btrim(derived_year_of_birth::text), '')::numeric BETWEEN 1900 AND 2026
            THEN NULLIF(btrim(derived_year_of_birth::text), '')::numeric::int END AS derived_year_of_birth,
       NULLIF(btrim(sort_ts::text), '')::timestamp          AS sort_ts{V2_STG}
FROM public.{T};

ALTER TABLE stg ADD COLUMN patient_id int, ADD COLUMN pv_id int, ADD COLUMN visit_msg_id uuid,
                ADD COLUMN sid text, ADD COLUMN is_legacy boolean;
UPDATE stg SET sid = NULLIF(btrim(raw_source_id), ''), is_legacy = row_kind IN ('legacy_invite', 'legacy_visit');
{LOC_SQL}
-- 2) Prep checks ---------------------------------------------------------------------------------------------------
DO $$ DECLARE n int; BEGIN
  SELECT count(*) INTO n FROM stg;                                  IF n <> {X['rows']} THEN RAISE EXCEPTION 'rows %, expected {X['rows']}', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'platform';      IF n <> {X['platform']} THEN RAISE EXCEPTION 'platform rows %, expected {X['platform']}', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_invite'; IF n <> {X['legacy_invite']} THEN RAISE EXCEPTION 'legacy_invite rows %, expected {X['legacy_invite']}', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_visit';  IF n <> {X['legacy_visit']} THEN RAISE EXCEPTION 'legacy_visit rows %, expected {X['legacy_visit']}', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_raw';    IF n <> {X['legacy_raw']} THEN RAISE EXCEPTION 'legacy_raw rows %, expected {X['legacy_raw']}', n; END IF;
  SELECT count(*) INTO n FROM (SELECT row_no FROM stg GROUP BY 1 HAVING count(*) > 1) d; IF n > 0 THEN RAISE EXCEPTION 'duplicate row_no %', n; END IF;
  -- raw columns must arrive as text exactly as in the file (an auto-typed date or number column would change them)
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'platform' AND raw_visit_date !~ '^\\d{{2}}/\\d{{2}}/\\d{{4}} \\d{{2}}:\\d{{2}}:\\d{{2}}$';
    IF n > 0 THEN RAISE EXCEPTION 'raw_visit_date was converted by the import tool (% rows) - re-import with ALL columns as TEXT', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE raw_phone ~ '^\\d+\\.\\d+$|e\\+';
    IF n > 0 THEN RAISE EXCEPTION 'raw_phone was converted to a number (% rows) - re-import with ALL columns as TEXT', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE is_legacy AND (est_visit_date IS NULL OR legacy_sguid IS NULL);
    IF n > 0 THEN RAISE EXCEPTION 'incomplete legacy rows %', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE is_legacy AND phone_clean IS NULL; IF n <> {X['legacy_no_phone']} THEN RAISE EXCEPTION 'legacy rows without phone %, expected {X['legacy_no_phone']}', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_invite' AND (est_sent_at IS NULL OR est_status NOT IN ({STATUSES}));
    IF n > 0 THEN RAISE EXCEPTION 'incomplete invite rows %', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE row_kind = 'legacy_invite' AND NOT has_response
     AND est_sent_at >= ('{C['platform_start']} 00:00'::timestamp AT TIME ZONE 'Europe/Zagreb');
    IF n > 0 THEN RAISE EXCEPTION 'estimated legacy sends in the platform period %', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE has_response AND (row_kind <> 'legacy_invite' OR link_sguid IS NULL OR sguid_reused);
    IF n > 0 THEN RAISE EXCEPTION 'responded rows that cannot be linked %', n; END IF;
  SELECT count(*) INTO n FROM stg s JOIN public.survey_response sr
     ON sr."surveyId" = (SELECT survey_id FROM cfg) AND sr.sguid = s.link_sguid AND sr.visit_msg_id IS NULL
     WHERE s.has_response;
    IF n <> {ANS} THEN RAISE EXCEPTION 'unlinked legacy responses found %, expected {ANS} (staging older than prod?)', n; END IF;{V2_CHECKS}
END $$;

UPDATE stg SET visit_msg_id = uuid_generate_v5({q(C['uuid_ns'])}::uuid, {q(C['slug'] + '-legacy-')} || row_no) WHERE row_kind = 'legacy_invite';

DO $$ DECLARE n int; BEGIN
  SELECT count(*) INTO n FROM stg s JOIN public.visit_msg vm ON vm.id = s.visit_msg_id; IF n > 0 THEN RAISE EXCEPTION 'legacy visit_msg ids already exist %', n; END IF;
END $$;

-- 3) Patients (decision 14). Existing Patients are never changed. -------------------------------------------------
-- Phones that belong to exactly one Patient of this Account BEFORE the load
CREATE TEMP TABLE ph_one ON COMMIT DROP AS
SELECT regexp_replace(p.phone, '\\D', '', 'g') AS phone_clean, min(p.id) AS patient_id
FROM public.patient p WHERE p.account_id = (SELECT account_id FROM cfg) AND regexp_replace(p.phone, '\\D', '', 'g') <> ''
GROUP BY 1 HAVING count(*) = 1;

-- 3a) rows with a source_id: the existing Patient with that source_id
UPDATE stg s SET patient_id = p.id FROM public.patient p, cfg c
WHERE s.is_legacy AND s.sid IS NOT NULL AND p.account_id = c.account_id AND p.source_id = s.sid;
-- 3b) rows without a source_id: the one existing Patient with that phone
UPDATE stg s SET patient_id = m.patient_id FROM ph_one m
WHERE s.is_legacy AND s.sid IS NULL AND s.phone_clean = m.phone_clean;

-- 3c) new Patients: one per source_id, else one per phone, else one per row; data from the latest legacy row
CREATE TEMP TABLE np ON COMMIT DROP AS
SELECT DISTINCT ON (k) k, nextval(pg_get_serial_sequence('public.patient', 'id'))::int AS id, row_no
FROM (SELECT coalesce('sid:' || sid, 'ph:' || phone_clean, 'row:' || row_no) AS k, row_no, sort_ts
      FROM stg WHERE is_legacy AND patient_id IS NULL) x
ORDER BY k, sort_ts DESC NULLS LAST, row_no DESC;

INSERT INTO public.patient (id, account_id, source_id, first_name, last_name, phone, gender_code, language_code,
                            country_code, year_of_birth, lead_source)
OVERRIDING SYSTEM VALUE
SELECT np.id, c.account_id, s.sid,
       NULLIF(btrim(s.raw_first_name), ''), NULLIF(btrim(s.raw_last_name), ''), coalesce(s.phone_clean, ''),
       CASE WHEN upper(btrim(s.raw_gender_code)) IN ('F','M') THEN upper(btrim(s.raw_gender_code)) END,
       CASE WHEN {LANG} ~ '^[A-Z]{{2}}$' THEN {LANG} END,
       CASE upper(btrim(s.raw_country_code)) WHEN '' THEN NULL WHEN 'ROM' THEN 'ROU' ELSE left(upper(btrim(s.raw_country_code)), 3) END,
       s.derived_year_of_birth, NULLIF(btrim(s.raw_lead_source), '')
FROM np JOIN stg s ON s.row_no = np.row_no CROSS JOIN cfg c;

UPDATE stg s SET patient_id = np.id FROM np
WHERE s.is_legacy AND s.patient_id IS NULL AND np.k = coalesce('sid:' || s.sid, 'ph:' || s.phone_clean, 'row:' || s.row_no);

-- 4) One mock sending batch for all legacy invites -------------------------------------------------------------------
CREATE TEMP TABLE sb ON COMMIT DROP AS
SELECT nextval(pg_get_serial_sequence('public.visit_msg_sending_batch', 'id'))::int AS batch_id;

INSERT INTO public.visit_msg_sending_batch (id, account_id, created_at, trigger, sent_at, processed_visits, processed_patients,
                                            created_messages, quarantine_blocked, ignored_visits, type, msg_sending_method)
OVERRIDING SYSTEM VALUE
SELECT sb.batch_id, c.account_id,
       (SELECT min(est_sent_at) FROM stg WHERE row_kind = 'legacy_invite') - interval '54 seconds', 'legacy_import',
       (SELECT min(est_sent_at) FROM stg WHERE row_kind = 'legacy_invite'),
       (SELECT count(*) FROM stg WHERE is_legacy),
       (SELECT count(DISTINCT patient_id) FROM stg WHERE is_legacy),
       (SELECT count(*) FROM stg WHERE row_kind = 'legacy_invite'),
       (SELECT count(*) FROM stg WHERE row_kind = 'legacy_visit'),
       '[]'::json, 'SURVEY_INVITE', 'INFOBIP_SMS_MAIN'
FROM sb CROSS JOIN cfg c;

INSERT INTO public.legacy_sending_batch (sending_batch_id, account_id, code, comment, source_files, loaded_by, loaded_at)
SELECT sb.batch_id, c.account_id, {q(CODE)},
       {q('LEGACY DATA - ' + C['account_name'] + ', ' + C['period'] + ': one mock sending batch holding all pre-platform survey invites. ESTIMATED: ' + C['estimated'] + '. REAL: Survey Responses, Patient data, doctor, procedure, visit comment. Original rows in legacy_source_row.')},
       ARRAY[c.source_file, {q(C['survey_file'])}, {q(C['load_file'])}], 'ana@insidercx.com', c.loaded_at
FROM sb CROSS JOIN cfg c;

-- 5) Legacy Patient Visits + "never survey" param ------------------------------------------------------------------
UPDATE stg SET pv_id = nextval(pg_get_serial_sequence('public.patient_visit', 'id')) WHERE is_legacy;

INSERT INTO public.patient_visit (id, account_id, location_id, patient_id, visit_date, doctor, procedure, comment)
OVERRIDING SYSTEM VALUE
SELECT s.pv_id, c.account_id, {LOC}, s.patient_id, s.est_visit_date,
       NULLIF(btrim(s.raw_doctor), ''), s.procedure_out, NULLIF(btrim(s.raw_comment), '')
FROM stg s CROSS JOIN cfg c WHERE s.is_legacy;

INSERT INTO public.patient_visit_param (patient_visit_id, param, value, account_id)
SELECT s.pv_id, 'ignore_for_survey', 'true', c.account_id FROM stg s CROSS JOIN cfg c WHERE s.is_legacy;

UPDATE public.visit_msg_sending_batch SET last_processed_visit_id = (SELECT max(pv_id) FROM stg)
WHERE id = (SELECT batch_id FROM sb);

-- 6) Legacy Visit Msgs, filled like real SMS invites of this Account ---------------------------------------------------
INSERT INTO public.visit_msg (id, invite_id, account_id, location_id, patient_visit_id, sending_batch_id, template_id,
                              sms_from, destination, sms_text, status, sms_status_group, sms_status_name,
                              created_at, sent_at, status_updated_at, quarantine_expiration, meta)
SELECT s.visit_msg_id, s.visit_msg_id, c.account_id, {LOC}, s.pv_id, (SELECT batch_id FROM sb), t.id,
       c.sms_from, coalesce(s.phone_clean, ''), coalesce(t.sms_text, '[legacy invite]'),
       s.est_status, s.est_status,
       {SMS_NAME},
       s.est_sent_at - interval '54 seconds', s.est_sent_at, s.est_sent_at + interval '27393 seconds',
       s.est_sent_at + make_interval(days => c.quarantine_days),
       {META}
FROM stg s CROSS JOIN cfg c
LEFT JOIN LATERAL (
  SELECT vt.id, vt.sms_text FROM public.visit_msg_template vt
  WHERE vt.account_id = c.account_id AND vt.type = 'SURVEY_INVITE'
    AND (vt.location_id = {LOC} OR vt.location_id IS NULL)
  ORDER BY (vt.language_code = {LANG}) DESC, (vt.language_code = 'HR') DESC, vt.id
  LIMIT 1) t ON true
WHERE s.row_kind = 'legacy_invite';

{STEP7}-- 8) Platform rows: link to the existing invite / visit (nothing created) ----------------------------------------------
UPDATE stg s SET visit_msg_id = vm.id, pv_id = vm.patient_visit_id
FROM public.visit_msg vm, cfg c
WHERE s.row_kind = 'platform' AND vm.account_id = c.account_id
  AND btrim(s.raw_id) ~ '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$' AND vm.id = btrim(s.raw_id)::uuid;
UPDATE stg s SET patient_id = pv.patient_id FROM public.patient_visit pv WHERE s.row_kind = 'platform' AND pv.id = s.pv_id;

-- 9) Source rows, untouched -----------------------------------------------------------------------------------------
INSERT INTO public.legacy_source_row (account_id, source_file, row_no, row_kind, raw, patient_id, patient_visit_id,
                                      visit_msg_id, sending_batch_id, loaded_at)
SELECT c.account_id, c.source_file, s.row_no, s.row_kind,
       jsonb_build_object(
         {raw_json}),
       s.patient_id, s.pv_id, s.visit_msg_id,
       CASE WHEN s.row_kind = 'legacy_invite' THEN (SELECT batch_id FROM sb) END, c.loaded_at
FROM stg s CROSS JOIN cfg c;

-- 10) Post-load checks (abort everything on mismatch) -----------------------------------------------------------------
DO $$ DECLARE n int; c record; b int; BEGIN
  SELECT * INTO c FROM cfg; SELECT batch_id INTO b FROM sb;
  SELECT count(*) INTO n FROM public.visit_msg WHERE sending_batch_id = b;   IF n <> {X['legacy_invite']} THEN RAISE EXCEPTION 'visit_msg %', n; END IF;
  SELECT count(*) INTO n FROM public.patient_visit WHERE id IN (SELECT pv_id FROM stg WHERE is_legacy);
    IF n <> {X['legacy_invite'] + X['legacy_visit']} THEN RAISE EXCEPTION 'patient_visit %', n; END IF;
  SELECT count(*) INTO n FROM public.patient_visit_param WHERE patient_visit_id IN (SELECT pv_id FROM stg WHERE is_legacy);
    IF n <> {X['legacy_invite'] + X['legacy_visit']} THEN RAISE EXCEPTION 'params %', n; END IF;
  SELECT count(*) INTO n FROM public.survey_response sr JOIN public.visit_msg vm ON vm.id = sr.visit_msg_id
    WHERE vm.sending_batch_id = b;                                           IF n <> {X['linked']} THEN RAISE EXCEPTION 'linked responses %, expected {X['linked']}', n; END IF;
  SELECT count(*) INTO n FROM public.survey_response sr JOIN public.visit_msg vm ON vm.id = sr.visit_msg_id
    WHERE vm.sending_batch_id = b AND sr.status = 'Deleted';                 IF n > 0 THEN RAISE EXCEPTION 'Deleted responses linked %', n; END IF;
  SELECT count(*) INTO n FROM public.legacy_source_row WHERE account_id = c.account_id AND source_file = c.source_file;
    IF n <> {X['rows']} THEN RAISE EXCEPTION 'source rows %', n; END IF;
  SELECT count(*) INTO n FROM stg WHERE is_legacy AND patient_id IS NULL;    IF n > 0 THEN RAISE EXCEPTION 'legacy rows without patient %', n; END IF;
  SELECT count(*) INTO n FROM public.patient WHERE account_id = c.account_id AND created < c.loaded_at AND updated >= c.loaded_at;
    IF n > 0 THEN RAISE EXCEPTION 'existing patients modified %', n; END IF;
END $$;

-- Result
SELECT {q(CODE)} AS code,
  (SELECT account_id FROM cfg) AS account_id, (SELECT location_id FROM cfg) AS location_id, (SELECT survey_id FROM cfg) AS survey_id,
  (SELECT batch_id FROM sb) AS mock_sending_batch_id,
  (SELECT count(*) FROM public.patient WHERE account_id = (SELECT account_id FROM cfg) AND created = (SELECT loaded_at FROM cfg)) AS new_patients,
  (SELECT count(*) FROM stg WHERE is_legacy) AS legacy_visits,
  (SELECT count(*) FROM stg WHERE row_kind = 'legacy_invite') AS legacy_invites,
  (SELECT count(*) FROM public.survey_response sr JOIN public.visit_msg vm ON vm.id = sr.visit_msg_id
     WHERE vm.sending_batch_id = (SELECT batch_id FROM sb)) AS linked_responses,
  (SELECT count(*) FROM stg WHERE row_kind = 'platform' AND visit_msg_id IS NOT NULL) AS platform_rows_linked,   -- {X['platform']} on prod; fewer on an older stg copy
  (SELECT count(*) FROM stg) AS source_rows_stored;

COMMIT;
"""

# ------------------------------------------------------------------------------------------------ 03
B = f"(SELECT sending_batch_id FROM legacy_sending_batch WHERE code = {q(CODE)})"
IF_LINKED = "" if LINK else f"""
-- 4) Not linked (link_responses false): what each legacy quarter WOULD show if ops decide to link (ESTIMATED sends,
--    real responses matched by sguid = the clinic id). Expect {ANS} responses in total; linked_now must be 0.
SELECT date_trunc('quarter', vm.sent_at AT TIME ZONE 'Europe/Zagreb')::date AS quarter,
       count(*) AS sent,
       count(*) FILTER (WHERE vm.status = 'DELIVERED') AS delivered,
       count(sr.id) AS responses_if_linked,
       floor(1000.0 * count(sr.id) / NULLIF(count(*) FILTER (WHERE vm.status = 'DELIVERED'), 0) + 0.5) / 10 AS response_rate_if_linked,
       count(sr.id) FILTER (WHERE sr.visit_msg_id IS NOT NULL) AS linked_now
FROM legacy_source_row r
JOIN visit_msg vm ON vm.id = r.visit_msg_id AND vm.sending_batch_id IN {B}
LEFT JOIN survey_response sr ON sr."surveyId" = (SELECT id FROM survey WHERE "alchemerId"::text = {q(AL)})
  AND btrim(sr.sguid) = btrim(r.raw->>'id') AND sr.status <> 'Deleted' AND NOT coalesce(sr."isTestData", false)
WHERE r.source_file = {q(SRC)}
GROUP BY 1 ORDER BY 1;
"""
s03 = HEAD + f"""-- Part 3: validation (read-only). Run each query on its own.

-- 1) Summary: expect {X['rows']} source rows, {X['legacy_invite'] + X['legacy_visit']} legacy visits, {X['legacy_invite']} invites, {X['linked']} linked,
--    0 existing Patients changed, 0 legacy rows without Patient, 0 Deleted responses linked
WITH r AS (SELECT * FROM legacy_source_row WHERE source_file = {q(SRC)}
             AND account_id = (SELECT "accountId" FROM survey WHERE "alchemerId"::text = {q(AL)})),
     b AS (SELECT * FROM legacy_sending_batch WHERE code = {q(CODE)})
SELECT (SELECT count(*) FROM r)                                                          AS source_rows,
       (SELECT count(*) FROM r WHERE row_kind IN ('legacy_invite','legacy_visit') AND patient_visit_id IS NOT NULL) AS legacy_visits,
       (SELECT count(*) FROM visit_msg WHERE sending_batch_id IN (SELECT sending_batch_id FROM b)) AS legacy_invites,
       (SELECT count(*) FROM survey_response sr JOIN visit_msg vm ON vm.id = sr.visit_msg_id
          WHERE vm.sending_batch_id IN (SELECT sending_batch_id FROM b))                 AS linked_responses,
       (SELECT count(*) FROM survey_response sr JOIN visit_msg vm ON vm.id = sr.visit_msg_id
          WHERE vm.sending_batch_id IN (SELECT sending_batch_id FROM b) AND sr.status = 'Deleted') AS deleted_linked,
       (SELECT count(*) FROM r WHERE row_kind = 'platform' AND visit_msg_id IS NOT NULL) AS platform_rows_linked,
       (SELECT count(*) FROM patient p WHERE p.account_id = (SELECT min(account_id) FROM b)
          AND p.created < (SELECT min(loaded_at) FROM b) AND p.updated >= (SELECT min(loaded_at) FROM b)) AS existing_patients_changed,
       (SELECT count(*) FROM patient p WHERE p.account_id = (SELECT min(account_id) FROM b)
          AND p.created = (SELECT min(loaded_at) FROM b))                                AS new_patients,
       (SELECT count(*) FROM r WHERE row_kind IN ('legacy_invite','legacy_visit') AND patient_id IS NULL) AS legacy_rows_without_patient,
       (SELECT count(*) FROM survey_response sr JOIN survey s ON s.id = sr."surveyId"
          WHERE s."alchemerId"::text = {q(AL)} AND sr.visit_msg_id IS NULL)              AS still_unlinked;

-- 2) Message performance, legacy quarters (sent/delivered ESTIMATED, responses real)
SELECT date_trunc('quarter', vm.sent_at AT TIME ZONE 'Europe/Zagreb')::date AS quarter,
       count(*) AS sent,
       count(*) FILTER (WHERE vm.status = 'DELIVERED') AS delivered,
       count(r.id) AS responses,
       floor(1000.0 * count(r.id) / NULLIF(count(*) FILTER (WHERE vm.status = 'DELIVERED'), 0) + 0.5) / 10 AS response_rate
FROM visit_msg vm
LEFT JOIN survey_response r ON r.visit_msg_id = vm.id
WHERE vm.sending_batch_id IN {B} AND vm.id = vm.invite_id
GROUP BY 1 ORDER BY 1;

-- 3) Legacy NPS (real): responses / promoters / detractors / NPS
SELECT count(*) AS responses,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9) AS promoters,
       count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6) AS detractors,
       floor(1000.0 * (count(*) FILTER (WHERE round(sr."NPS_SCORE") >= 9)
                     - count(*) FILTER (WHERE round(sr."NPS_SCORE") <= 6)) / NULLIF(count(*), 0) + 0.5) / 10 AS nps
FROM survey_response sr
JOIN visit_msg vm ON vm.id = sr.visit_msg_id
WHERE vm.sending_batch_id IN {B} AND sr."NPS_SCORE" BETWEEN 0 AND 10;
{IF_LINKED}
-- When satisfied: DROP TABLE public.{T};   -- contains PII
"""

# ------------------------------------------------------------------------------------------------ 04
cols04 = ",\n       ".join(f"raw->>{q(c)} AS \"{c}\"" for c in RAW)
s04 = HEAD + f"""-- Re-create {SRC} (same {X['rows']} rows, order, columns and values).
-- Export the result as CSV (comma, header on, UTF-8). Contains Patient PII - handle like the original file.
-- Compare by value with the clinic file: some values are quoted in the original where no quotes are needed, and the
-- export tool decides its own quoting, so a byte compare can differ while every value is identical.
SELECT {cols04}
FROM legacy_source_row
WHERE source_file = {q(SRC)}
  AND account_id = (SELECT "accountId" FROM survey WHERE "alchemerId"::text = {q(AL)})
ORDER BY row_no;
"""

# ------------------------------------------------------------------------------------------------ 99
s99 = HEAD + f"""-- Rollback of the load (data only; the legacy tables and the trigger fallback stay - other Accounts use them).
-- Run the WHOLE file. On any error: run ROLLBACK; and send the message.

BEGIN;

CREATE TEMP TABLE lr ON COMMIT DROP AS
SELECT r.* FROM public.legacy_source_row r
JOIN public.survey s ON s."accountId" = r.account_id AND s."alchemerId"::text = {q(AL)}
WHERE r.source_file = {q(SRC)};

CREATE TEMP TABLE lb ON COMMIT DROP AS
SELECT lsb.sending_batch_id, lsb.account_id, lsb.loaded_at FROM public.legacy_sending_batch lsb
JOIN public.survey s ON s."accountId" = lsb.account_id AND s."alchemerId"::text = {q(AL)}
WHERE lsb.code = {q(CODE)};

DO $$ BEGIN
  IF (SELECT count(*) FROM lb) > 1 THEN RAISE EXCEPTION 'more than one {CODE} batch - stop and check'; END IF;
  IF EXISTS (SELECT 1 FROM public.patient_ticket WHERE patient_visit_id IN (SELECT patient_visit_id FROM lr WHERE row_kind IN ('legacy_invite','legacy_visit'))) THEN
    RAISE EXCEPTION 'Patient Tickets exist on legacy visits - resolve them before rolling back';
  END IF;
  IF EXISTS (SELECT 1 FROM public.survey_invite_reminder_prep_log WHERE sending_batch_id IN (SELECT sending_batch_id FROM lb)) THEN
    RAISE EXCEPTION 'Reminder logs reference the legacy sending batch - resolve before rolling back';
  END IF;
END $$;

-- unlink responses (map first so the trigger leaves the link empty)
DELETE FROM public.legacy_invite_map WHERE visit_msg_id IN (SELECT id FROM public.visit_msg WHERE sending_batch_id IN (SELECT sending_batch_id FROM lb));
UPDATE public.survey_response SET visit_msg_id = NULL
WHERE visit_msg_id IN (SELECT id FROM public.visit_msg WHERE sending_batch_id IN (SELECT sending_batch_id FROM lb));

DELETE FROM public.legacy_source_row r USING lr
WHERE r.account_id = lr.account_id AND r.source_file = lr.source_file AND r.row_no = lr.row_no;

DELETE FROM public.visit_msg WHERE sending_batch_id IN (SELECT sending_batch_id FROM lb);
-- batches before visits: last_processed_visit_id references patient_visit (cascades legacy_sending_batch)
DELETE FROM public.visit_msg_sending_batch WHERE id IN (SELECT sending_batch_id FROM lb);
DELETE FROM public.patient_visit_param WHERE patient_visit_id IN (SELECT patient_visit_id FROM lr WHERE row_kind IN ('legacy_invite','legacy_visit'));
DELETE FROM public.patient_visit       WHERE id               IN (SELECT patient_visit_id FROM lr WHERE row_kind IN ('legacy_invite','legacy_visit'));
DELETE FROM public.patient p
WHERE p.account_id = (SELECT min(account_id) FROM lb) AND p.created = (SELECT min(loaded_at) FROM lb)
  AND NOT EXISTS (SELECT 1 FROM public.patient_visit pv WHERE pv.patient_id = p.id)
  AND NOT EXISTS (SELECT 1 FROM public.patient_ticket t WHERE t.patient_id = p.id);

SELECT (SELECT count(*) FROM lr) AS source_rows_removed,
       (SELECT count(*) FROM lr WHERE row_kind IN ('legacy_invite','legacy_visit')) AS legacy_visits_removed,
       (SELECT count(*) FROM public.legacy_sending_batch WHERE code = {q(CODE)}) AS remaining_batches;   -- 0
COMMIT;
"""

out = ROOT / "sql"
out.mkdir(exist_ok=True)
for name, body in [("01_before_import.sql", s01), ("02_load.sql", s02), ("03_validation.sql", s03),
                   ("04_export_original_csv.sql", s04), ("99_rollback.sql", s99)]:
    (out / name).write_text(body)
print("rendered", out)
