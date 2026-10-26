"""
Build sie_full_v4.csv - every row of Pacijenti_JOINED_Stomatologija_i_estetika.csv (14,254) with:
  raw_*     : the original 18 columns, exactly as in the file (for exact re-export from legacy_source_row)
  computed  : what the load needs for legacy rows (estimated dates, invite selection, status, procedure, year of birth)
Row kinds: platform (has visit_date; already in DB, only linked), legacy_invite (2,692), legacy_visit (8,881).
Invite set, send times and statuses are identical to invites.csv (validated on EU stg).
Usage: python3 2_build_full_v4.py <legacy csv> <surveys csv> <batch v2 csv> <out csv>
"""
import sys, re, pandas as pd
from sklearn.isotonic import IsotonicRegression
LEG, SUR, V2, OUT = sys.argv[1:5]
TZ = "Europe/Zagreb"; E = pd.Timestamp("1970-01-01", tz="UTC")
raw = pd.read_csv(LEG, dtype=str, encoding="utf-8-sig", keep_default_na=False)
RAW_COLS = list(raw.columns)
raw.insert(0, "row_no", range(1, len(raw) + 1))
s = pd.read_csv(SUR, dtype=str, encoding="utf-8-sig", keep_default_na=False)
s = s[s["URL Variable: sguid"].str.fullmatch(r"\d+")].copy()
s["rs"] = (pd.to_datetime(s["Time Started"], format="%m/%d/%Y %H:%M:%S")
           .dt.tz_localize(TZ, ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC"))
v2 = pd.read_csv(V2, dtype=str, keep_default_na=False).set_index("legacy_sguid")

d = raw.copy()
d["is_legacy"] = d.visit_date == ""
leg = d[d.is_legacy].merge(s[["URL Variable: sguid", "rs"]], left_on="id", right_on="URL Variable: sguid", how="left")
leg["short"] = ~(leg.id.str.startswith("100") & (leg.id.str.len() > 3))
leg["seq"] = [int(i) if sh else int(i[3:]) for i, sh in zip(leg.id, leg.short)]
parts = []
for _, g in leg.groupby("short"):
    a = g[g.rs.notna()]
    ir = IsotonicRegression(out_of_bounds="clip").fit(a.seq, ((a.rs - pd.Timedelta(hours=0.8)) - E).dt.total_seconds())
    g = g.copy()
    est = pd.Series(E + pd.to_timedelta(ir.predict(g.seq), unit="s"), index=g.index).dt.tz_convert(TZ)
    g["sent"] = (est.dt.normalize() + pd.Timedelta(hours=17, minutes=5)).dt.tz_convert("UTC")
    parts.append(g)
leg = pd.concat(parts).set_index("row_no")

# invites: take exactly the validated v2 values
inv = leg.id.isin(v2.index)
leg["est_sent_at"] = ""
leg.loc[inv, "est_sent_at"] = leg.loc[inv, "id"].map(v2.est_sent_at)
leg["est_status"] = ""
leg.loc[inv, "est_status"] = leg.loc[inv, "id"].map(v2.est_status).replace({"UNDELIVERED": "UNDELIVERABLE"})
leg["has_response"] = ""
leg.loc[inv, "has_response"] = leg.loc[inv, "id"].map(v2.has_response)
# visit date: invites from v2; other legacy rows from the same timeline (send - 27 h), wall-clock labelled +00
sent_any = pd.to_datetime(leg.est_sent_at.where(inv), utc=True).fillna(leg.sent)
visit_utc = sent_any - pd.Timedelta(hours=27)
leg["est_visit_date"] = visit_utc.dt.tz_convert(TZ).dt.strftime("%Y-%m-%d %H:%M:00+00")
age = pd.to_numeric(leg.age, errors="coerce")
leg["derived_year_of_birth"] = (visit_utc.dt.tz_convert(TZ).dt.year - age).astype("Int64").astype(str).replace("<NA>", "")
pp = re.compile(r"(^|[^a-zčćžšđ])pp([^a-zčćžšđ]|$)|prvi pregled", re.I)
leg["procedure_mock"] = leg.comment.map(lambda c: "Prvi pregled" if pp.search(c or "") else "Zahvat")
leg["row_kind"] = "legacy_visit"
leg.loc[inv, "row_kind"] = "legacy_invite"
leg["sort_ts"] = sent_any.dt.strftime("%Y-%m-%d %H:%M:%S")

d = d.set_index("row_no")
for c in ["row_kind", "est_visit_date", "est_sent_at", "est_status", "has_response", "procedure_mock", "derived_year_of_birth", "sort_ts"]:
    d[c] = ""
    d.loc[leg.index, c] = leg[c]
d.loc[~d.is_legacy, "row_kind"] = "platform"
d["legacy_sguid"] = d.id.where(d.is_legacy, "")
d["phone_clean"] = d.phone.str.replace(r"\D", "", regex=True)
d.loc[d.phone_clean.str.len() < 8, "phone_clean"] = ""

out = d.reset_index()[["row_no", "row_kind"] + RAW_COLS + ["legacy_sguid", "phone_clean", "est_visit_date", "est_sent_at",
                                                             "est_status", "has_response", "procedure_mock", "derived_year_of_birth", "sort_ts"]]
out = out.rename(columns={c: "raw_" + c for c in RAW_COLS})
out.to_csv(OUT, index=False)
print(out.row_kind.value_counts().to_dict(), "| responded", (out.has_response == "true").sum(),
      "| legacy rows with empty phone_clean", ((out.row_kind != "platform") & (out.phone_clean == "")).sum())
print("max len", {c: int(out[c].astype(str).str.len().max()) for c in out.columns if out[c].astype(str).str.len().max() > 60})
