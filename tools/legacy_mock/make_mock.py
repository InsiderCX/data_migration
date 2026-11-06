"""
Generate a mock database (mock.sql) for one Account's legacy load, with the real constraints the scripts touch:
GENERATED ALWAYS identity ids on patient / patient_visit / visit_msg_sending_batch, fk_last_processed_visit_id,
patient_ticket and reminder-log foreign keys, survey_response FK ON DELETE SET NULL, hstore, uuid-ossp, and the link
trigger WITH SIE's legacy fallback and SIE's legacy tables already present (as on EU prod since 28 Oct 2026).

Mock state for the Account (ids as on EU prod):
  - every answered invite has an unlinked response with exactly the stored sguid (Complete, score 9)
  - Deleted response on one non-answered legacy invite (must not link and must not be mapped)
  - test responses that stay unlinked; on Arcadia also a response on a reused id (must stay unlinked)
  - existing Patients: 40% of legacy source_ids; for legacy rows without source_id, 300 phones on exactly one Patient
    (visits must attach to it) and 100 phones on two Patients (a new Patient must be created)
  - 90% of the platform invites (an older stg copy has fewer)
  - another Account's legacy_import batch (SIE) - 01 must not refuse because of it; one unrelated Patient Ticket

Usage: python3 make_mock.py <account dir> <out mock.sql> <out expectations.json>
"""
import json
import pathlib
import sys

import pandas as pd

ROOT, OUT_MOCK, OUT_EXP = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
C = json.loads((ROOT / "sql_config.json").read_text())
f = pd.read_csv(ROOT / "data" / C["load_file"], dtype=str, keep_default_na=False)
ACC = C["account_id_prod"]
TPL = {"videntis": [(79, "HR"), (80, "EN"), (81, "FR"), (82, "DE"), (83, "IT")], "arcadia": [(114, "HR")], "apolonija": [(84, "HR")],
       "kvaternik": [(40, "HR", 2), (39, "HR", 1)], "mazalin": [(44, "HR", None)], "opticalexpress": [(112, "HR"), (113, "SL")]}[C["slug"]]
TPL = [t + (1,) if len(t) == 2 else t for t in TPL]          # (id, language, mock Location id or None)
# Locations as on EU prod (names matter: layout-2 loads resolve a row's Location by name)
LOCS = {"kvaternik": ["Kvaternik Subiceva", "Kvaternik Kostanjevec"]}.get(C["slug"], [C["account_name"]])
COUNTRIES = (pathlib.Path(__file__).parent / "country_codes.txt").read_text().split()   # public.country on EU prod, 6 Nov 2026
q = lambda xs: ",".join("'" + str(x).replace("'", "''") + "'" for x in xs)

legacy = f[f.row_kind.isin(["legacy_invite", "legacy_visit"])]
resp = f[f.has_response == "true"].link_sguid
plat = f[f.row_kind == "platform"].raw_id.str.strip()
plat = plat.sample(int(len(plat) * 0.9), random_state=1)
sids = legacy.raw_source_id.str.strip()
existing_sid = sids[sids != ""].drop_duplicates()
existing_sid = existing_sid.sample(int(len(existing_sid) * 0.4), random_state=3)
nosid = legacy[(sids == "") & (legacy.phone_clean != "")]
phones = nosid.phone_clean.drop_duplicates().sample(frac=1, random_state=5)
one_phone, two_phone = phones[:300], phones[300:400]
deleted_on = f[(f.row_kind == "legacy_invite") & (f.has_response != "true") & (f.sguid_reused != "true")].legacy_sguid.iloc[0]
reused_resp = f[(f.sguid_reused == "true")].legacy_sguid.head(1).tolist()

exp = {"one_phone_rows": int(nosid.phone_clean.isin(set(one_phone)).sum()),
       "two_phone_rows": int(nosid.phone_clean.isin(set(two_phone)).sum()),
       "deleted_sguid": deleted_on, "reused_sguid": reused_resp[0] if reused_resp else None}
json.dump(exp, open(OUT_EXP, "w"))

mock = f"""
CREATE EXTENSION hstore; CREATE EXTENSION "uuid-ossp";
CREATE TYPE visit_msg_type_enum AS ENUM ('SURVEY_INVITE','INVITE_REMINDER');
CREATE TYPE msg_sending_method_enum AS ENUM ('INFOBIP_OMNI_MAIN','INFOBIP_SMS_MAIN','INFOBIP_SMS_SUB');
CREATE TABLE account(id serial primary key, name text, sms_sender varchar);
CREATE TABLE location(id serial primary key, account_id int, name text, quarantine_days int not null default 90);
CREATE TABLE survey(id serial primary key, "accountId" int, "alchemerId" varchar);
CREATE TABLE patient(id int GENERATED ALWAYS AS IDENTITY primary key, account_id int not null, first_name varchar, last_name varchar,
  phone varchar not null, source_id varchar, gender_code char, lead_source varchar, year_of_birth int, country_code char(3),
  language_code char(2), created timestamptz not null default now(), updated timestamptz not null default now());
CREATE UNIQUE INDEX uq_source_id_per_account ON patient(account_id, source_id);
CREATE TABLE country(code char(3) primary key);
INSERT INTO country VALUES {", ".join(f"('{c}')" for c in COUNTRIES)};
ALTER TABLE patient ADD CONSTRAINT fk_country_code FOREIGN KEY (country_code) REFERENCES country(code);
CREATE TABLE patient_visit(id int GENERATED ALWAYS AS IDENTITY primary key, account_id int not null, location_id int not null,
  visit_date timestamptz not null, doctor varchar, procedure varchar, comment text, patient_id int not null references patient(id),
  created_at timestamptz not null default now());
CREATE TABLE patient_visit_param(patient_visit_id int not null references patient_visit(id), param varchar not null,
  value varchar not null, account_id int not null, primary key(patient_visit_id, param));
CREATE TABLE visit_msg_sending_batch(id int GENERATED ALWAYS AS IDENTITY primary key, account_id int not null,
  created_at timestamptz not null default now(),
  last_processed_visit_id int CONSTRAINT fk_last_processed_visit_id REFERENCES patient_visit(id),
  trigger varchar not null, sent_at timestamptz, processed_visits int not null, processed_patients int not null,
  created_messages int not null, quarantine_blocked int not null, ignored_visits json not null,
  type visit_msg_type_enum not null default 'SURVEY_INVITE', msg_sending_method msg_sending_method_enum);
CREATE TABLE survey_invite_reminder_prep_log(id serial primary key, sending_batch_id int references visit_msg_sending_batch(id));
CREATE TABLE patient_ticket(id serial primary key, patient_id int references patient(id), patient_visit_id int references patient_visit(id));
CREATE TABLE visit_msg_template(id serial primary key, account_id int, location_id int, language_code char(2),
  type visit_msg_type_enum, sms_text text);
CREATE TABLE visit_msg(id uuid primary key, account_id int not null,
  sending_batch_id int not null references visit_msg_sending_batch(id), patient_visit_id int not null references patient_visit(id),
  sms_from varchar not null, destination varchar not null, sms_text varchar not null, quarantine_expiration timestamptz,
  status varchar not null, created_at timestamptz not null default now(), sent_at timestamptz, status_updated_at timestamptz,
  sms_status_group text, sms_status_name text, invite_id uuid not null, send_at timestamptz,
  template_id int references visit_msg_template(id), location_id int, meta hstore);
CREATE TABLE survey_response(id serial primary key, "surveyId" int, sguid text, "alchemerResponseId" varchar, "dateSubmitted" timestamptz,
  status varchar, language varchar, comment_sentiment varchar,
  visit_msg_id uuid references visit_msg(id) on update cascade on delete set null, "NPS_SCORE" numeric, "dateStarted" timestamptz,
  "isTestData" boolean not null default false);

-- SIE's legacy tables and trigger fallback, as on EU prod
CREATE TABLE legacy_sending_batch (sending_batch_id int PRIMARY KEY REFERENCES visit_msg_sending_batch(id) ON DELETE CASCADE,
  account_id int NOT NULL REFERENCES account(id), code text NOT NULL, comment text NOT NULL, source_files text[], loaded_by text,
  loaded_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE legacy_invite_map (account_id int NOT NULL, legacy_sguid text NOT NULL,
  visit_msg_id uuid NOT NULL REFERENCES visit_msg(id) ON DELETE CASCADE, PRIMARY KEY (account_id, legacy_sguid));
CREATE TABLE legacy_source_row (account_id int NOT NULL REFERENCES account(id), source_file text NOT NULL, row_no int NOT NULL,
  row_kind text NOT NULL, raw jsonb NOT NULL, patient_id int REFERENCES patient(id) ON DELETE SET NULL,
  patient_visit_id int REFERENCES patient_visit(id) ON DELETE SET NULL, visit_msg_id uuid REFERENCES visit_msg(id) ON DELETE SET NULL,
  sending_batch_id int REFERENCES visit_msg_sending_batch(id) ON DELETE SET NULL, loaded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (account_id, source_file, row_no));
CREATE FUNCTION survey_response__set_visit_msg_id_from_sguid() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
  BEGIN
    SELECT id INTO NEW.visit_msg_id FROM public.visit_msg WHERE id = NEW.sguid::uuid;
  EXCEPTION WHEN invalid_text_representation THEN
    SELECT m.visit_msg_id INTO NEW.visit_msg_id FROM public.legacy_invite_map m JOIN public.survey s ON s.id = NEW."surveyId"
    WHERE m.account_id = s."accountId" AND m.legacy_sguid = NEW.sguid;
  END;
  RETURN NEW;
END $fn$;
CREATE TRIGGER survey_response__set_visit_msg_id BEFORE INSERT OR UPDATE ON survey_response
  FOR EACH ROW EXECUTE FUNCTION survey_response__set_visit_msg_id_from_sguid();

-- another Account with a legacy load (SIE, Account 36)
SELECT setval('account_id_seq', 35);
INSERT INTO account(name, sms_sender) VALUES ('Stomatologija i estetika', 'SiE');
INSERT INTO patient(account_id, source_id, phone) VALUES (36, 'SIEPAT', '385');
INSERT INTO patient_visit(account_id, location_id, visit_date, patient_id) VALUES (36, 57, '2024-01-01', 1);
INSERT INTO visit_msg_sending_batch(account_id, trigger, processed_visits, processed_patients, created_messages, quarantine_blocked,
  ignored_visits, last_processed_visit_id) VALUES (36, 'legacy_import', 1, 1, 0, 0, '[]', 1);
INSERT INTO legacy_sending_batch(sending_batch_id, account_id, code, comment) VALUES (1, 36, 'SIE_LEGACY_V4', 'mock');

-- this Account, ids as on EU prod
SELECT setval('account_id_seq', {ACC - 1});
INSERT INTO account(name, sms_sender) VALUES ('{C['account_name']}', 'Mock');
INSERT INTO location(account_id, name) VALUES {", ".join(f"({ACC}, '{n}')" for n in LOCS)};
INSERT INTO survey("accountId", "alchemerId") VALUES ({ACC}, '{C['alchemer_id']}');
INSERT INTO visit_msg_template(id, account_id, location_id, language_code, type, sms_text) VALUES
  {", ".join(f"({i},{ACC},{'NULL' if loc is None else loc},'{l}','SURVEY_INVITE','{l} tpl')" for i, l, loc in TPL)};
INSERT INTO patient(account_id, source_id, phone) VALUES ({ACC}, 'PLATFORMPAT', '385');
INSERT INTO patient_visit(account_id, location_id, visit_date, patient_id)
  SELECT {ACC}, 1, '2025-06-01', (SELECT id FROM patient WHERE source_id = 'PLATFORMPAT') FROM generate_series(1, {len(plat)});
INSERT INTO visit_msg_sending_batch(account_id, trigger, processed_visits, processed_patients, created_messages,
  quarantine_blocked, ignored_visits) VALUES ({ACC}, 'cron', 1, 1, 1, 0, '[]');
INSERT INTO visit_msg(id, account_id, sending_batch_id, patient_visit_id, sms_from, destination, sms_text, status, invite_id)
  SELECT x::uuid, {ACC}, 2, 1 + row_number() OVER (), 'Mock', '385', 'x', 'DELIVERED', x::uuid FROM unnest(ARRAY[{q(plat)}]) x;
INSERT INTO patient_ticket(patient_id, patient_visit_id) VALUES (1, 1);
INSERT INTO survey_response("surveyId", sguid, status, "NPS_SCORE", "dateStarted")
  SELECT 1, x, 'Complete', 9, '2024-01-01' FROM unnest(ARRAY[{q(resp)}]) x;
INSERT INTO survey_response("surveyId", sguid, status, "NPS_SCORE", "dateStarted") VALUES (1, '{deleted_on}', 'Deleted', 3, '2024-01-01');
INSERT INTO survey_response("surveyId", sguid, status, "NPS_SCORE", "dateStarted") SELECT 1, 'test' || g, 'Complete', 5, '2023-06-01' FROM generate_series(1, 5) g;
{"INSERT INTO survey_response(" + '"surveyId", sguid, status, "NPS_SCORE", "dateStarted"' + f") VALUES (1, '{reused_resp[0]}', 'Complete', 10, '2024-01-01');" if reused_resp else ""}
INSERT INTO patient(account_id, source_id, phone, year_of_birth, first_name)
  SELECT {ACC}, x, '385000', 1950, 'EXISTING' FROM unnest(ARRAY[{q(existing_sid) or "''"}]::text[]) x WHERE x <> '';
INSERT INTO patient(account_id, source_id, phone, first_name) SELECT {ACC}, NULL, x, 'PHONE1' FROM unnest(ARRAY[{q(one_phone) or "''"}]::text[]) x WHERE x <> '';
INSERT INTO patient(account_id, source_id, phone, first_name) SELECT {ACC}, NULL, x, 'PHONE2' FROM unnest(ARRAY[{q(two_phone) or "''"}]::text[]) x, generate_series(1, 2) WHERE x <> '';
UPDATE patient SET created = now() - interval '2 day', updated = now() - interval '1 day';
"""
open(OUT_MOCK, "w").write(mock)
print("mock: platform invites", len(plat), "| responses", len(resp), "| existing by source_id", len(existing_sid),
      "| phones on 1 / 2 Patients", len(one_phone), "/", len(two_phone))
