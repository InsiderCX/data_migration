"""
Build the load file for one Account's legacy import: every row of the clinic file, with what the load needs.

Usage: python3 -I 1_build_load_file.py <clinic csv> <db unlinked responses csv> <out load csv> [<db visit_msg ids csv>]

  clinic csv     : Pacijenti_JOINED_<Account>.csv from ops (rows with visit_date = platform, already in the DB)
  db responses   : data/db_unlinked_responses_<date>.csv, exported from the prod replica
                   (alchemer_response_id, sguid exactly as stored, started_utc, status, is_test)
  out            : data/<account>_full_v1.csv, imported into stg_<account>_full by the GUI
  visit_msg ids  : platform_rule "db_ids" only: data/db_visit_msg_ids_<date>.csv (the Account's Visit Msg ids on prod)

Only the CONFIG block differs between Accounts; the code below it is identical (diff it to check).

Method (SIE's, re-fitted per Account; every est_* value is ESTIMATED):
  1. Anchors: legacy rows whose id is the sguid of an unlinked DB response (sguid trimmed, test links excluded).
     Ids used by two clinic rows (reused) are never anchors and never linked.
  2. Send date: within each id scheme, legacy ids are time-ordered. Schemes with Spearman < 0.95 (check C10)
     instead get the anchors' send-time quantiles by id rank. Isotonic fit id sequence ->
     (response start - send->response median), interpolated between isotonic block midpoints. Day = predicted day
     (weekend -> Monday: legacy sends were on weekdays), time = SEND_TIME (Zagreb).
     Anchors: sent_at = min(estimate, response start - 2 min).
  3. Visit date = sent_at - visit->send median, stored as Zagreb wall-clock labelled +00 (platform convention).
  4. Invites: replay platform rules per phone - first visit, then none within QUARANTINE_DAYS, age rule if
     AGE_RULE; anchors always invited; rows without a phone only if they are anchors.
  5. Status: anchors DELIVERED; others DELIVERED except a deterministic share (md5(id) mod 1000 < UNDELIVERED_PER_MILLE).
  6. Year of birth per YOB_RULE.
Linked responses: anchors that are not Deleted (decision 12). link_sguid is the sguid exactly as Alchemer stores it.
DEV-232 options (CONFIG keys, see the code): layout, platform_rule, scheme_rule, send_rule, visit_rule, invite_rule,
status_rule, reused_rule. Left out, each keeps the DEV-162 behaviour above.
"""
# ---------------------------------------------------------------- CONFIG (Kvaternik, EU Account 21)
CONFIG = dict(
    account="kvaternik",
    layout=2,
    platform_rule="db_ids",            # 6 platform rows have no sent_at; the Visit Msg ids on prod decide
    send_rule="waves",                 # decision 5: one bulk send, first real response 21 Feb 2024 15:57 Zagreb
    waves=[(None, "2024-02-21 14:50")],
    visit_rule="file_or_send",         # the file's 21 Feb 2024 12:00 (a placeholder, decision 5)
    invite_rule="all",                 # decision 6: the file lists sent messages
    status_rule="file",                # decisions 3-4: real SMS status
    reused_rule="raw_only",
    send_time=(14, 50),                # unused with waves
    send_to_response_h=0.37,           # platform median, Mar 2024 - Nov 2026
    visit_to_send_h=28.0,              # platform median
    quarantine_days=180,
    age_rule=None,                     # no replay
    undelivered_per_mille=34,          # platform delivery 96.6 % (no empty status on legacy rows)
    yob_rule="file",                   # real years; 1900-2026 only (02_load)
    raw_only_ids=(),
    location_column="location_id",     # decision 11: legacy rows name their Location
    location_map={"Subiceva": "Kvaternik Subiceva", "Kostanjevec": "Kvaternik Kostanjevec"},
    platform_response_rate=21.4,       # 2024 - Oct 2026, over delivered (decision 12: refuse if > 5 points off)
)
# ---------------------------------------------------------------- code (identical for every Account)
import hashlib
import re
import sys

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

CLINIC, RESP, OUT = sys.argv[1:4]
TZ = "Europe/Zagreb"
E = pd.Timestamp("1970-01-01", tz="UTC")
TEST = re.compile(r"test|^t+1?t*s+|^1111\d{8,}$|^111222666$|^40275999993$", re.I)  # test links seen on prod
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
# Options added for DEV-232; the defaults are the DEV-162 behaviour (Videntis, Arcadia, Apolonija build unchanged)
LAYOUT = CONFIG.get("layout", 1)                   # 2: extra output columns status_source, language_out, location_name
PLATFORM_RULE = CONFIG.get("platform_rule", "visit_date")  # "db_ids": platform = id is a Visit Msg on prod (4th arg)
SCHEME_RULE = CONFIG.get("scheme_rule", "first2")  # "len_prefix": id scheme = digit count (+ first two digits if > 3)
SEND_RULE = CONFIG.get("send_rule", "isotonic")    # "waves": fixed send per visit-date wave (CONFIG waves)
VISIT_RULE = CONFIG.get("visit_rule", "from_send") # "file_or_send": the file's visit date when before the send
INVITE_RULE = CONFIG.get("invite_rule", "replay")  # "all": every legacy row with a phone was sent
STATUS_RULE = CONFIG.get("status_rule", "estimate")  # "file": the file's SMS status (real), estimate only when empty
REUSED_RULE = CONFIG.get("reused_rule", "keep")    # "raw_only": rows on repeated ids are stored as source rows only
FILE_STATUS = {"DELIVERED": "DELIVERED", "UNDELIVERABLE": "UNDELIVERABLE", "UNDELIVERED": "UNDELIVERABLE",
               "EXPIRED": "EXPIRED", "REJECTED": "REJECTED", "PENDING": "PENDING"}

raw = pd.read_csv(CLINIC, dtype=str, encoding="utf-8-sig", keep_default_na=False)
RAW_COLS = list(raw.columns)
d = raw.copy()
d.insert(0, "row_no", range(1, len(d) + 1))
d["cid"] = d["id"].str.strip()

# row kinds before invite selection
if PLATFORM_RULE == "db_ids":
    vm_ids = set(pd.read_csv(sys.argv[4], dtype=str, keep_default_na=False).visit_msg_id.str.lower())
    platform = d.cid.str.lower().isin(vm_ids)
else:
    platform = d.visit_date.str.strip() != ""
assert d.loc[platform, "cid"].str.match(UUID).all(), "platform row without a uuid id"
raw_only = ~platform & ((d.cid == "") | d.cid.isin(CONFIG["raw_only_ids"]))
counts = d.loc[~platform & ~raw_only, "cid"].value_counts()
if REUSED_RULE == "raw_only":  # decision DEV-232/7: not loaded, ops decide
    raw_only = raw_only | (~platform & d.cid.map(counts).gt(1))
legacy = ~platform & ~raw_only
counts = d.loc[legacy, "cid"].value_counts()
reused = legacy & d.cid.map(counts).gt(1)


def scheme(i):
    """(scheme key, sequence) of a legacy id: text prefix, else the first two digits (len_prefix: digit count too)."""
    m = re.fullmatch(r"([a-z]+)(\d+)", i, re.I)
    if m:
        return m.group(1).lower(), int(m.group(2))
    if SCHEME_RULE == "len_prefix" and i.isdigit():
        return (f"len{len(i)}" if len(i) <= 3 else f"len{len(i)}:{i[:2]}"), int(i)
    if i.isdigit() and len(i) > 2:
        return i[:2], int(i[2:])
    return "other", int(i) if i.isdigit() else 0


leg = d[legacy].copy()
leg[["scheme", "seq"]] = pd.DataFrame([scheme(i) for i in leg.cid], index=leg.index)

# responses: trimmed sguid -> clinic id
r = pd.read_csv(RESP, dtype=str, keep_default_na=False)
r["key"] = r.sguid.str.strip()
r = r[(r.is_test != "True") & ~r.key.str.contains(TEST)]
r["start"] = pd.to_datetime(r.started_utc).dt.tz_localize("UTC")
unique_ids = set(leg.loc[~reused[legacy], "cid"])
anc = r[r.key.isin(unique_ids)].sort_values("start").drop_duplicates("key")
anc = anc.rename(columns={"sguid": "resp_sguid", "status": "resp_status", "start": "resp_start"})
leg = leg.merge(anc[["key", "resp_sguid", "resp_start", "resp_status"]], how="left", left_on="cid", right_on="key")
leg.index = d.index[legacy]
leg["anchor"] = leg.resp_start.notna()

# 2. send date per id scheme
leg["sent"] = pd.Series(pd.NaT, index=leg.index, dtype="datetime64[ns, UTC]")
if SEND_RULE == "waves":
    # bulk sends seen in the real responses: CONFIG waves = [(visits before this local date or None, send local time)]
    vd = pd.to_datetime(leg.visit_date.str.strip(), format="%d/%m/%Y %H:%M:%S")
    todo = pd.Series(True, index=leg.index)
    for until, at in CONFIG["waves"]:
        w = todo & (vd < pd.Timestamp(until) if until else todo)
        leg.loc[w, "sent"] = pd.Timestamp(at).tz_localize(TZ).tz_convert("UTC")
        todo &= ~w
    assert not todo.any(), "legacy rows outside every wave"
else:
    for k, g in leg.groupby("scheme"):
        a = g[g.anchor]
        y = ((a.resp_start - pd.Timedelta(hours=CONFIG["send_to_response_h"])) - E).dt.total_seconds() if len(a) else None
        rho = a.seq.corr(y, method="spearman") if len(a) >= 3 else float("nan")
        if len(a) >= 3 and not rho >= 0.95:
            # weakly ordered scheme (check C10): ids -> anchor send-time quantiles by rank, so the scheme keeps the
            # anchors' period and density without stacking on one day
            pred = np.quantile(y.values, (g.seq.rank(method="first").values - 0.5) / len(g))
            print(f"scheme {k}: {len(g)} rows, {len(a)} anchors, spearman {rho:.3f} -> rank quantiles", file=sys.stderr)
        elif len(a) >= 2:
            ir = IsotonicRegression(out_of_bounds="clip").fit(a.seq, y)
            # isotonic pools out-of-order anchors into flat blocks; interpolate between block midpoints so ids inside
            # and between blocks are spread over the gap instead of stacked on one day
            xs = np.array(sorted(set(a.seq)), dtype=float); fit = ir.predict(xs)
            blocks = pd.DataFrame({"x": xs, "y": fit}).groupby("y", sort=True).x.mean()
            pred = np.interp(g.seq, blocks.values, blocks.index.values)
        else:  # scheme without anchors: place it at the median of all anchors (reported)
            pred = [((leg[leg.anchor].resp_start.median() - E).total_seconds())] * len(g)
            print(f"scheme {k}: {len(g)} rows, {len(a)} anchors -> median date", file=sys.stderr)
        est = pd.Series(E + pd.to_timedelta(pred, unit="s"), index=g.index).dt.tz_convert(TZ)
        h, m = CONFIG["send_time"]
        day = est.dt.normalize()
        day = day + pd.to_timedelta((7 - day.dt.dayofweek).where(day.dt.dayofweek >= 5, 0), unit="D")  # weekend -> Monday
        leg.loc[g.index, "sent"] = (day + pd.Timedelta(hours=h, minutes=m)).dt.tz_convert("UTC")
leg["sent"] = pd.to_datetime(leg.sent, utc=True)
cap = leg.resp_start - pd.Timedelta(minutes=2)
over = leg.anchor & (leg.sent > cap)
leg.loc[over, "sent"] = cap[over]

# 3. visit date
leg["visit_utc"] = leg.sent - pd.Timedelta(hours=CONFIG["visit_to_send_h"])
visit_local = leg.visit_utc.dt.tz_convert(TZ)
if VISIT_RULE == "file_or_send":  # real visit date (Zagreb wall clock) when the file has one before the send
    fv = pd.to_datetime(leg.visit_date.str.strip(), format="%d/%m/%Y %H:%M:%S", errors="coerce").dt.tz_localize(TZ)
    use = fv.notna() & (fv < leg.sent.dt.tz_convert(TZ))
    visit_local = visit_local.where(~use, fv)
    leg["visit_utc"] = visit_local.dt.tz_convert("UTC")
    print(f"visit date: {int(use.sum())} from the file, {int((fv.notna() & ~use).sum())} file dates after the send "
          f"-> estimated, {int(fv.isna().sum())} estimated", file=sys.stderr)

# 6. year of birth
if CONFIG["yob_rule"] == "2026_minus_age":
    age = pd.to_numeric(leg.age, errors="coerce")
    leg["yob_out"] = (2026 - age).astype("Int64").astype(str).replace("<NA>", "")
    age_at_visit = visit_local.dt.year - (2026 - age)
elif CONFIG["yob_rule"] == "file":
    leg["yob_out"] = leg.year_of_birth.str.strip()
    age_at_visit = visit_local.dt.year - pd.to_numeric(leg.year_of_birth, errors="coerce")
else:  # "none"
    leg["yob_out"] = ""
    age_at_visit = pd.Series(float("nan"), index=leg.index)
if LAYOUT == 2:  # decision DEV-232/10: a year 1900-2026 or empty (junk such as '#VALUE!' would stop the load)
    y = pd.to_numeric(leg.yob_out.where(leg.yob_out.str.fullmatch(r"\d{4}"), ""), errors="coerce")
    leg["yob_out"] = y.where(y.between(1900, 2026)).astype("Int64").astype(str).replace("<NA>", "")

# 4. invite selection
leg["phone_clean"] = leg.phone.str.replace(r"\D", "", regex=True)
leg.loc[leg.phone_clean.str.len() < 8, "phone_clean"] = ""
ok_age = pd.Series(True, index=leg.index)
if CONFIG["age_rule"] is not None:
    ok_age = age_at_visit.isna() | (age_at_visit >= CONFIG["age_rule"])
invited, last = pd.Series(False, index=leg.index), {}
if INVITE_RULE == "all":  # the file lists sent messages; no phone -> invite only when a real response proves it
    invited = (leg.phone_clean != "") | leg.anchor
else:
    for i in leg.sort_values(["visit_utc", "seq"]).index:
        ph, t = leg.at[i, "phone_clean"], leg.at[i, "visit_utc"]
        if not ph:  # no phone, no SMS: invited only when a real response proves it
            invited[i] = bool(leg.at[i, "anchor"])
            continue
        prev = last.get(ph)
        ok = leg.at[i, "anchor"] or (ok_age[i] and (prev is None or t >= prev + pd.Timedelta(days=CONFIG["quarantine_days"])))
        if ok:
            invited[i] = True
            last[ph] = t

# 5. status
und = leg.cid.map(lambda x: int(hashlib.md5(x.encode()).hexdigest(), 16) % 1000 < CONFIG["undelivered_per_mille"])
leg["est_status"] = ""
linked = leg.anchor & (leg.resp_status != "Deleted")
if STATUS_RULE == "file":
    # real status from the file; answered -> DELIVERED (a response proves delivery); empty -> estimated
    fs = leg.status.str.strip().str.upper()
    assert fs[invited].isin(set(FILE_STATUS) | {""}).all(), f"unknown SMS status {set(fs[invited]) - set(FILE_STATUS)}"
    leg["status_source"] = ""
    leg.loc[invited, "est_status"] = fs[invited].map(FILE_STATUS).fillna("")
    leg.loc[invited & (fs != ""), "status_source"] = "file"
    fix = invited & linked & (leg.est_status != "DELIVERED")
    leg.loc[fix & (fs != ""), "status_source"] = "corrected"
    leg.loc[fix & (fs == ""), "status_source"] = "response"
    leg.loc[fix, "est_status"] = "DELIVERED"
    empty = invited & (leg.est_status == "")
    leg.loc[empty, "est_status"] = "DELIVERED"
    leg.loc[empty & und, "est_status"] = "UNDELIVERABLE"
    leg.loc[empty, "status_source"] = "estimated"
else:
    leg.loc[invited, "est_status"] = "DELIVERED"
    leg.loc[invited & ~leg.anchor & und, "est_status"] = "UNDELIVERABLE"
    leg["status_source"] = ""
    leg.loc[invited, "status_source"] = "estimated"

# output
out = d[["row_no"]].copy()
out["row_kind"] = "platform"
out.loc[raw_only, "row_kind"] = "legacy_raw"
out.loc[legacy, "row_kind"] = "legacy_visit"
out.loc[leg.index[invited], "row_kind"] = "legacy_invite"
for c in RAW_COLS:  # lowercase names: the staging table is created with unquoted (lowercase) columns
    out["raw_" + c.lower()] = d[c]
out["legacy_sguid"] = ""
out.loc[legacy, "legacy_sguid"] = leg.cid
out["link_sguid"] = ""
out.loc[leg.index[linked], "link_sguid"] = leg.loc[linked, "resp_sguid"]
out["sguid_reused"] = ""
out.loc[reused, "sguid_reused"] = "true"
out["phone_clean"] = d.phone.str.replace(r"\D", "", regex=True)
out.loc[out.phone_clean.str.len() < 8, "phone_clean"] = ""
out["est_visit_date"] = ""
out.loc[legacy, "est_visit_date"] = visit_local.dt.strftime("%Y-%m-%d %H:%M:00+00")
out["est_sent_at"] = ""
out.loc[leg.index[invited], "est_sent_at"] = leg.loc[invited, "sent"].dt.strftime("%Y-%m-%d %H:%M:%S+00")
out["est_status"] = ""
out.loc[legacy, "est_status"] = leg.est_status
out["has_response"] = ""
out.loc[leg.index[invited], "has_response"] = linked[invited].map({True: "true", False: "false"})
out["procedure_out"] = d.get("procedure", pd.Series("", index=d.index)).str.strip()
out.loc[platform | raw_only, "procedure_out"] = ""
out["derived_year_of_birth"] = ""
out.loc[legacy, "derived_year_of_birth"] = leg.yob_out
out["sort_ts"] = ""
out.loc[legacy, "sort_ts"] = leg.sent.dt.strftime("%Y-%m-%d %H:%M:%S")
if LAYOUT == 2:
    out["status_source"] = ""
    out.loc[legacy, "status_source"] = leg.status_source
    lang = d.language_code.str.strip().str.upper().replace(CONFIG.get("language_map", {}))
    out["language_out"] = lang.where(lang.str.fullmatch(r"[A-Z]{2}"), "")
    out.loc[platform | raw_only, "language_out"] = ""
    out["location_name"] = ""
    if CONFIG.get("location_map"):
        col, lmap = CONFIG["location_column"], CONFIG["location_map"]
        assert d.loc[legacy, col].str.strip().isin(set(lmap)).all(), "legacy row with an unknown Location"
        out.loc[legacy, "location_name"] = d.loc[legacy, col].str.strip().map(lmap)
out.to_csv(OUT, index=False)

# summary (stdout): counts, then estimated sends per quarter
print("row kinds", out.row_kind.value_counts().to_dict())
print("anchors", int(leg.anchor.sum()), "| linked responses", int(linked.sum()), "| deleted anchors", int((leg.anchor & ~linked).sum()),
      "| reused-id rows", int(reused.sum()), "| invites", int(invited.sum()))
inv = leg[invited]
q = pd.DataFrame({"q": inv.sent.dt.tz_convert(TZ).dt.to_period("Q").astype(str), "deliv": inv.est_status == "DELIVERED",
                  "resp": linked[invited]}).groupby("q").agg(sent=("deliv", "size"), delivered=("deliv", "sum"), responses=("resp", "sum"))
q["resp_rate"] = (q.responses * 1000 / q.delivered + 0.5).astype(int) / 10
print(q.to_string())
print("busiest estimated send day:", int(inv.sent.dt.date.value_counts().max()), "invites")
if LAYOUT == 2:
    print("status source", inv.status_source.value_counts().to_dict(), "| status", inv.est_status.value_counts().to_dict())
    print("sends capped before their response", int((over & invited).sum()))
    rate = 100 * linked[invited].sum() / (inv.est_status == "DELIVERED").sum()
    print(f"legacy response rate if linked {rate:.1f} % | platform {CONFIG['platform_response_rate']} %")
    assert abs(rate - CONFIG["platform_response_rate"]) <= 5, "legacy response rate more than 5 points from the platform"
