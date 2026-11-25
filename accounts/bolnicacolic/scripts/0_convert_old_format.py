"""
Convert Bolnica Colić's patient file from the old 12-column structure to the current one (Karlo, 11 Nov 2026:
"there is still the old table structure, adapt it to the current format").

Usage: python3 -I scripts/0_convert_old_format.py data/Pacijenti_DrColic.csv data/Pacijenti_Joined_BolnicaColic.csv

Mapping (old -> current), checked below on every row:
  Sguid -> id            Ime -> first_name       Prezime -> last_name     Telefon -> phone
  Izvor -> lead_source   Jezik -> language_code  Doktor -> doctor         Dob -> age (extra column, read by yob_rule)
  Spol2 -> gender_code   (Ženski -> F, Muški -> M, anything else -> empty; Spol says the same in other spellings)
  source_id, year_of_birth, country_code, visit_date, procedure, comment, status, sent_at -> empty (not in the old file)
Dropped, because they add nothing: Telefon2 (identical to Telefon on every row), R (empty on every row), Spol
(same as Spol2, 7 spellings). The script stops if any of that stops being true.
The output is the "clinic file" of this Account from here on: the load stores it and 04 exports it back.
"""
import csv
import sys

SRC, OUT = sys.argv[1:3]
OLD = ["Spol", "Dob", "Izvor", "Jezik", "Telefon", "Doktor", "Sguid", "Ime", "Prezime", "R", "Spol2", "Telefon2"]
NEW = ["id", "first_name", "last_name", "source_id", "phone", "lead_source", "year_of_birth", "gender_code",
       "country_code", "language_code", "visit_date", "procedure", "comment", "doctor", "status", "sent_at", "age"]
GENDER = {"Ženski": "F", "Muški": "M", "ŽenskiŽenski": "F"}

with open(SRC, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
assert list(rows[0].keys()) == OLD, f"unexpected columns {list(rows[0].keys())}"

out = []
for r in rows:
    assert r["Telefon2"] == r["Telefon"], "Telefon2 differs from Telefon"
    assert r["R"].strip() == "", "R is not empty"
    g = GENDER.get(r["Spol2"].strip(), "")
    old_g = r["Spol"].strip().lower().replace("ž", "z")[:1]
    assert (g, old_g) in {("F", "z"), ("M", "m"), ("", "t")}, "Spol and Spol2 disagree"
    out.append({"id": r["Sguid"], "first_name": r["Ime"], "last_name": r["Prezime"], "source_id": "", "phone": r["Telefon"],
                "lead_source": r["Izvor"], "year_of_birth": "", "gender_code": g, "country_code": "",
                "language_code": r["Jezik"], "visit_date": "", "procedure": "", "comment": "", "doctor": r["Doktor"],
                "status": "", "sent_at": "", "age": r["Dob"]})

assert len({o["id"].strip() for o in out}) == len(out), "repeated Sguid"
with open(OUT, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=NEW)
    w.writeheader()
    w.writerows(out)

# back-check: every kept old value is in the new file unchanged
back = list(csv.DictReader(open(OUT, encoding="utf-8", newline="")))
pairs = [("Sguid", "id"), ("Ime", "first_name"), ("Prezime", "last_name"), ("Telefon", "phone"), ("Izvor", "lead_source"),
         ("Jezik", "language_code"), ("Doktor", "doctor"), ("Dob", "age")]
assert all(r[o] == b[n] for r, b in zip(rows, back) for o, n in pairs), "value changed in conversion"
print(f"converted {len(out)} rows: gender F {sum(o['gender_code'] == 'F' for o in out)}, M {sum(o['gender_code'] == 'M' for o in out)}, "
      f"empty {sum(o['gender_code'] == '' for o in out)}; age filled {sum(o['age'].strip() != '' for o in out)}")
