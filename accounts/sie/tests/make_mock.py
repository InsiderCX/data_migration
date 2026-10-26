"""
Generate a mock database (mock.sql) that mirrors the parts of the real InsiderCX schema the v4 scripts touch,
with the real constraints that matter: GENERATED ALWAYS identity ids on patient / patient_visit /
visit_msg_sending_batch, fk_last_processed_visit_id, patient_ticket and reminder-log foreign keys,
survey_response FK ON DELETE SET NULL, the original sguid->visit_msg link trigger, enums, hstore, uuid-ossp.

State mirrors EU stg before the load: Account 36 / Location 57 / Survey 17 (Alchemer 90558103),
507 unlinked responses (480 legacy + 27 others), ~780 legacy Patients that already exist,
2,000 platform invites (an older stg copy has fewer than the file's 2,681), one unrelated Patient Ticket.
Mock scores are all 9, so mock NPS = 100 (real data gives 86.5).

Usage: python3 make_mock.py <data/sie_full_v4.csv> <out mock.sql> <out stg_table.sql>
"""
import sys
import pandas as pd

src, out_mock, out_stg = sys.argv[1:4]
f = pd.read_csv(src, dtype=str, keep_default_na=False)
resp = f[f.has_response == "true"].legacy_sguid
plat = f[f.row_kind == "platform"].raw_id.sample(2000, random_state=1)
existing = f[f.row_kind != "platform"].raw_source_id.drop_duplicates().sample(780, random_state=3)
q = lambda xs: ",".join("'" + x + "'" for x in xs)

mock = f"""
CREATE EXTENSION hstore; CREATE EXTENSION "uuid-ossp";
CREATE TYPE visit_msg_type_enum AS ENUM ('SURVEY_INVITE','INVITE_REMINDER');
CREATE TYPE msg_sending_method_enum AS ENUM ('INFOBIP_OMNI_MAIN','INFOBIP_SMS_MAIN','INFOBIP_SMS_SUB');
CREATE TABLE account(id serial primary key, name text, sms_sender varchar);
CREATE TABLE location(id serial primary key, account_id int, quarantine_days int not null default 90);
CREATE TABLE survey(id serial primary key, "accountId" int, "alchemerId" varchar);
CREATE TABLE patient(id int GENERATED ALWAYS AS IDENTITY primary key, account_id int not null, first_name varchar, last_name varchar,
  phone varchar not null, source_id varchar, gender_code char, lead_source varchar, year_of_birth int, country_code char(3),
  language_code char(2), created timestamptz not null default now(), updated timestamptz not null default now());
CREATE UNIQUE INDEX uq_source_id_per_account ON patient(account_id, source_id);
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
CREATE TABLE survey_response(id serial primary key, "surveyId" int, sguid text, "alchemerResponseId" varchar, "dateSubmitted" timestamptz, status varchar, language varchar, comment_sentiment varchar,
  visit_msg_id uuid references visit_msg(id) on update cascade on delete set null, "NPS_SCORE" numeric, "dateStarted" timestamptz);
CREATE FUNCTION survey_response__set_visit_msg_id_from_sguid() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN BEGIN SELECT id INTO NEW.visit_msg_id FROM visit_msg WHERE id = NEW.sguid::uuid;
EXCEPTION WHEN invalid_text_representation THEN NEW.visit_msg_id := NULL; END; RETURN NEW; END $$;
CREATE TRIGGER survey_response__set_visit_msg_id BEFORE INSERT OR UPDATE ON survey_response
  FOR EACH ROW EXECUTE FUNCTION survey_response__set_visit_msg_id_from_sguid();

SELECT setval('account_id_seq', 35); SELECT setval('location_id_seq', 56); SELECT setval('survey_id_seq', 16);
INSERT INTO account(name, sms_sender) VALUES ('Stomatologija i estetika', 'SiE');
INSERT INTO location(account_id) VALUES (36);
INSERT INTO survey("accountId", "alchemerId") VALUES (36, '90558103');
INSERT INTO visit_msg_template(id, account_id, location_id, language_code, type, sms_text) VALUES
  (70,36,57,'HR','SURVEY_INVITE','HR tpl'), (71,36,57,'EN','SURVEY_INVITE','EN tpl'),
  (72,36,57,'IT','SURVEY_INVITE','IT tpl'), (73,36,57,'SL','SURVEY_INVITE','SL tpl');
INSERT INTO patient(account_id, source_id, phone) VALUES (36, 'PLATFORMPAT', '385');
INSERT INTO patient_visit(account_id, location_id, visit_date, patient_id) SELECT 36, 57, '2025-01-01', 1 FROM generate_series(1, 2000);
INSERT INTO visit_msg_sending_batch(account_id, trigger, processed_visits, processed_patients, created_messages,
  quarantine_blocked, ignored_visits, last_processed_visit_id) VALUES (36, 'cron', 1, 1, 1, 0, '[]', 2000);
INSERT INTO visit_msg(id, account_id, sending_batch_id, patient_visit_id, sms_from, destination, sms_text, status, invite_id)
  SELECT x::uuid, 36, 1, row_number() OVER (), 'SiE', '385', 'x', 'DELIVERED', x::uuid FROM unnest(ARRAY[{q(plat)}]) x;
INSERT INTO patient_ticket(patient_id, patient_visit_id) VALUES (1, 5);
INSERT INTO survey_response("surveyId", sguid, "NPS_SCORE", "dateStarted") SELECT 17, x, 9, '2024-01-01' FROM unnest(ARRAY[{q(resp)}]) x;
INSERT INTO survey_response("surveyId", sguid, "NPS_SCORE", "dateStarted") SELECT 17, 'TEST' || g, 5, '2023-06-01' FROM generate_series(1, 27) g;
INSERT INTO patient(account_id, source_id, phone, year_of_birth, language_code, first_name)
  SELECT 36, x, '385000', 1950, 'HR', 'EXISTING' FROM unnest(ARRAY[{q(existing)}]) x;
UPDATE patient SET created = now() - interval '2 day', updated = now() - interval '1 day';
"""
open(out_mock, "w").write(mock)
# staging table filled the way the GUI does it: header row, empty -> NULL (only needed if 01 was not run)
open(out_stg, "w").write("\\copy stg_sie_full FROM 'data/sie_full_v4.csv' CSV HEADER NULL ''\n")
