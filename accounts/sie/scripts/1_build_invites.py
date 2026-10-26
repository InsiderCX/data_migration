"""
Step 1 of 2 - select the legacy Survey Invites for Stomatologija i estetika (EU, Account 36),
May 2023 - 15 Oct 2024, with ESTIMATED send dates, visit dates and delivery status -> invites.csv.
Step 2 (2_build_full_v4.py) combines invites.csv with every source row into data/sie_full_v4.csv.

Usage: python3 1_build_invites.py <Pacijenti_JOINED...csv> <Sie_surveys.csv> <out invites.csv>
Method name: isotonic_id_quarantine (used by load code SIE_LEGACY_V4)

Inputs
  legacy CSV : Pacijenti_JOINED_Stomatologija_i_estetika.csv  (rows without visit_date = legacy)
  surveys CSV: Sie_surveys.csv  (Alchemer export, 'Time Started' in Europe/Zagreb, month-first)

Method
  1. Anchors: the 480 legacy rows whose id appears as numeric sguid in the survey export.
  2. Send date: legacy ids are time-ordered. Fit isotonic regression id -> (response start - 0.8 h)
     separately for short ids (<1000) and '100'-prefixed ids (sequence = id without '100').
     Day = predicted day; time = 17:05 Europe/Zagreb (observed legacy batch time).
     Responded rows: sent_at = min(estimate, response start - 2 min).
  3. Visit date = sent_at - 27 h (platform median visit->send for this Account).
  4. Which visits were invited: replay platform rules per phone - invite if no invite in the
     previous 90 days and Patient >= 18 at visit; responded rows always invited.
  5. Status: responded -> DELIVERED; others DELIVERED except a deterministic 4.8 %
     (md5(legacy id) mod 1000 < 48) -> UNDELIVERED  (platform delivery rate 95.2 %).
  6. year_of_birth = year(estimated visit) - age (CSV 'age' = age at visit). ROM -> ROU. Phone digits only.
"""
import hashlib
import sys
import pandas as pd
from sklearn.isotonic import IsotonicRegression

LEGACY, SURVEYS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
TZ = "Europe/Zagreb"
E = pd.Timestamp("1970-01-01", tz="UTC")

c = pd.read_csv(LEGACY, dtype=str, encoding="utf-8-sig")
s = pd.read_csv(SURVEYS, dtype=str, encoding="utf-8-sig")

leg = c[c.visit_date.isna()].copy()
s = s[s["URL Variable: sguid"].str.fullmatch(r"\d+")].copy()
s["resp_start"] = (pd.to_datetime(s["Time Started"], format="%m/%d/%Y %H:%M:%S")
                   .dt.tz_localize(TZ, ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC"))
leg = leg.merge(s[["URL Variable: sguid", "resp_start"]], left_on="id",
                right_on="URL Variable: sguid", how="left").drop(columns="URL Variable: sguid")
leg["has_response"] = leg.resp_start.notna()

# 2. estimated send day from id order
leg["short"] = ~(leg.id.str.startswith("100") & (leg.id.str.len() > 3))
leg["seq"] = [int(i) if sh else int(i[3:]) for i, sh in zip(leg.id, leg.short)]
parts = []
for _, g in leg.groupby("short"):
    a = g[g.has_response]
    y = ((a.resp_start - pd.Timedelta(hours=0.8)) - E).dt.total_seconds()
    ir = IsotonicRegression(out_of_bounds="clip").fit(a.seq, y)
    g = g.copy()
    est = pd.Series(E + pd.to_timedelta(ir.predict(g.seq), unit="s"), index=g.index).dt.tz_convert(TZ)
    g["est_sent_at"] = (est.dt.normalize() + pd.Timedelta(hours=17, minutes=5)).dt.tz_convert("UTC")
    parts.append(g)
leg = pd.concat(parts)
cap = leg.resp_start - pd.Timedelta(minutes=2)
leg.loc[leg.has_response & (leg.est_sent_at > cap), "est_sent_at"] = cap

# 3. visit date
leg["visit_utc"] = leg.est_sent_at - pd.Timedelta(hours=27)

# 4. invite selection (age + 90-day quarantine per phone)
# CSV 'age' is the Patient's age at the visit (verified against existing Patients' real year of birth)
age_at_visit = pd.to_numeric(leg.age, errors="coerce")
leg["year_of_birth"] = (leg.visit_utc.dt.tz_convert(TZ).dt.year - age_at_visit).astype("Int64")
age_ok = age_at_visit.isna() | (age_at_visit >= 18)
leg = leg[age_ok | leg.has_response].sort_values(["phone", "visit_utc", "seq"])
invited, last = [], {}
for ph, t, r in zip(leg.phone, leg.visit_utc, leg.has_response):
    prev = last.get(ph)
    ok = bool(r) or prev is None or t >= prev + pd.Timedelta(days=90)
    invited.append(ok)
    if ok:
        last[ph] = t
leg = leg[invited].copy()

# 5. status
undeliv = leg.id.map(lambda x: int(hashlib.md5(x.encode()).hexdigest(), 16) % 1000 < 48)
leg["est_status"] = "DELIVERED"
leg.loc[~leg.has_response & undeliv, "est_status"] = "UNDELIVERED"

# 6. cleaning
leg["phone"] = leg.phone.str.replace(r"\D", "", regex=True)
leg.loc[leg.phone.str.len() < 8, "phone"] = ""          # broken values (e.g. 9,99999E+99)
leg["country_code"] = leg.country_code.replace({"ROM": "ROU"})
for col in ["first_name", "last_name", "comment", "doctor", "lead_source"]:
    leg[col] = leg[col].str.strip()

# Output: est_sent_at is a real instant (UTC); est_visit_date follows the existing
# patient_visit convention = Zagreb wall-clock time labelled +00.
leg["est_sent_at_out"] = leg.est_sent_at.dt.strftime("%Y-%m-%d %H:%M:%S+00")
leg["est_visit_date_out"] = leg.visit_utc.dt.tz_convert(TZ).dt.strftime("%Y-%m-%d %H:%M:00+00")

out = pd.DataFrame({
    "legacy_sguid": leg.id, "source_id": leg.source_id,
    "first_name": leg.first_name, "last_name": leg.last_name, "phone": leg.phone,
    "gender_code": leg.gender_code, "language_code": leg.language_code,
    "country_code": leg.country_code, "year_of_birth": leg.year_of_birth,
    "lead_source": leg.lead_source, "doctor": leg.doctor, "comment": leg.comment,
    "est_sent_at": leg.est_sent_at_out, "est_visit_date": leg.est_visit_date_out,
    "est_status": leg.est_status, "has_response": leg.has_response.map({True: "true", False: "false"}),
}).sort_values("est_sent_at")
out.to_csv(OUT, index=False, encoding="utf-8")

# summary
q = out.assign(q=pd.to_datetime(out.est_sent_at.str[:10]).dt.to_period("Q")).groupby("q").agg(
    invites=("legacy_sguid", "size"),
    delivered=("est_status", lambda x: (x == "DELIVERED").sum()),
    responses=("has_response", lambda x: (x == "true").sum()))
q["resp_rate_%"] = (100 * q.responses / q.delivered).round(1)
print(q.to_string())
print("rows", len(out), "| patients", out.source_id.nunique(), "| responses", (out.has_response == "true").sum(),
      "| empty phone", (out.phone == "").sum(), "| yob filled", out.year_of_birth.notna().sum())
