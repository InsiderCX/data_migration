# Pre-production check: what a clinic sees in Zoho vs what it will see in Clinicdash after the legacy load.
# Usage: .venv/bin/python -I tools/preprod/build_zoho_clinicdash_check.py <repo> <in dir> <out xlsx>
# Inputs (git-ignored, ids and counts only, in <in dir>):
#   prod_clinicdash_monthly_<date>.csv  prod replica, per Survey and month: Clinicdash "Total responses" rows (real)
#   legacy_links_<date>.csv             legacy responses each load file links: response id, month, score (real)
#   zoho_checkpoints_<date>.csv         Zoho Joined table per checkpoint: rows and distinct responses (real)
#   reasons.csv                         one line per checkpoint: result, reason, how to check by hand (written by a person)
#   spot_checks.csv                     response ids to open by hand, with what each should show
#   staging_checks.csv                  load checks that must be exact: expected vs staging (real)
# Clinicdash definitions follow the InsiderCX code (General dashboard): scored responses (NPS_SCORE 0-10) with a
# Visit Msg, dated by dateStarted in the Clinicdash User's time zone (Europe/Zagreb here); NPS half up to 1 decimal.
import csv
import math
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

REPO, IN, OUT = sys.argv[1:4]
DAY = "2026-11-17"
F = "Arial"
HDR = PatternFill("solid", fgColor="1F3864"); HF = Font(name=F, bold=True, color="FFFFFF")
FILL = {"match": PatternFill("solid", fgColor="E2EFDA"), "known": PatternFill("solid", fgColor="FFF2CC"),
        "unexplained": PatternFill("solid", fgColor="F8CBAD"), "info": PatternFill("solid", fgColor="DDEBF7")}
BOX = Border(*[Side(style="thin", color="BFBFBF")] * 4)
ACC = [("videntis", "Videntis", "90508475", False), ("arcadia", "Arcadia", "90534273", False),
       ("apolonija", "Apolonija", "90492576", False), ("kvaternik", "Kvaternik", "90677816", True),
       ("mazalin", "Mazalin", "90553181", True), ("opticalexpress", "Optical Express", "90535032", True)]


def rd(name):
    return list(csv.DictReader(open(f"{IN}/{name}", encoding="utf-8-sig")))


def nps(p, d, n):  # Clinicdash: floor(1000 * (p - d) / n + 0.5) / 10
    return "" if not n else math.floor(1000 * (p - d) / n + 0.5) / 10


def band(score):
    try:
        s = float(score)
    except ValueError:
        return None
    if not 0 <= s <= 10:
        return None
    r = int(s + 0.5)  # PostgreSQL round(): half away from zero; scores are >= 0
    return "p" if r >= 9 else "d" if r <= 6 else "n"


prod = rd(f"prod_clinicdash_monthly_{DAY}.csv")
links = rd(f"legacy_links_{DAY}.csv")
zoho = {(r["account"], r["checkpoint"]): r for r in rd(f"zoho_checkpoints_{DAY}.csv")}
why = {(r["account"], r["checkpoint"]): r for r in rd("reasons.csv")}


def clinicdash(alch, acc, cp, with_links):
    """(responses, promoters, passives, detractors) on prod today (+ the load's legacy links)."""
    rows = [r for r in prod if r["alchemer"] == alch and (cp == "total" or r["month"] == cp)]
    n, p, d = (sum(int(r[k]) for r in rows) for k in ("cd_total", "promoters", "detractors"))
    added = [0, 0, 0]
    if with_links:
        for r in links:
            if r["account"] == acc and (cp == "total" or r["month"] == cp):
                b = band(r["score"])
                if b:
                    added[0] += 1; added[1] += b == "p"; added[2] += b == "d"
    return (n, p, n - p - d, d), added


wb = Workbook()
rm = wb.active; rm.title = "Read me"
for t in [
    f"Zoho vs Clinicdash before the legacy imports go to production ({DAY}). Six Accounts, three checkpoints each: "
    "all-time total, one legacy month, September 2026.",
    "Goal: a clinic must see the same numbers in Clinicdash as in Zoho. Every difference has a reason and a count; "
    "'unexplained' must be zero before production.",
    "Zoho (real): the Account's Joined query table behind its monthly charts, by 'Time Started'. 'Rows' is what a chart "
    "that counts rows shows; 'distinct' counts each Alchemer response once. Which of the two the charts use is confirmed by hand (sheet Spot checks).",
    "Clinicdash today (real): prod replica on 17 Nov 2026. Clinicdash after the load (projected): today + the legacy "
    "responses the load links (real responses, the link is what the load adds).",
    "Clinicdash rules (InsiderCX code, General dashboard): responses with a Visit Msg and a score 0-10, dated by "
    "'dateStarted' in the Clinicdash User's time zone (Europe/Zagreb); no filter on status or test data; NPS = "
    "% promoters (9-10) - % detractors (0-6), half up to 1 decimal. NPS Trends shows one line per Location (no Account total).",
    "Kvaternik, Mazalin, Optical Express: loaded append-only on staging. 'After the load' links their legacy responses "
    "as Karlo decided in COPS-234 (A1); 'today' columns show what staging has now (legacy months 0).",
    "Not compared (not comparable): sends, delivery and response rate (legacy ones are estimated), breakdowns that exist only in Zoho.",
    "Contains Alchemer response ids only, no patient data. Git-ignored.",
]:
    rm.append([t])
rm.column_dimensions["A"].width = 140
for c in rm["A"]:
    c.font, c.alignment = Font(name=F), Alignment(wrap_text=True, vertical="top")

ws = wb.create_sheet("Checkpoints")
H = ["Account", "Checkpoint", "Zoho rows (real)", "Zoho distinct responses (real)", "Zoho distinct with score",
     "Zoho promoters", "Zoho detractors", "Zoho NPS (distinct)", "Clinicdash today on prod (real)",
     "Added by the load (scored responses, real)", "Clinicdash after load: responses (projected)", "promoters", "passives",
     "detractors", "NPS", "After load minus Zoho distinct with score", "Result", "Reason", "Check by hand"]
ws.append(H)
for a, name, alch, dev232 in ACC:
    for cp in [k[1] for k in zoho if k[0] == a]:
        z = zoho[(a, cp)]
        zn, zp, zd = int(z["d_scored"]), int(z["d_prom"]), int(z["d_det"])
        today, added = clinicdash(alch, a, cp, False)[0], clinicdash(alch, a, cp, True)[1]
        n, p, d = today[0] + added[0], today[1] + added[1], today[3] + added[2]
        w = why.get((a, cp), {})
        label = "Total, all time" if cp == "total" else f"{cp[:4]}-{cp[4:]}"
        ws.append([name, label, int(z["rows"]), int(z["distinct"]), zn, zp, zd, nps(zp, zd, zn), today[0], added[0],
                   n, p, n - p - d, d, nps(p, d, n), n - zn, w.get("result", ""), w.get("reason", ""), w.get("manual", "")])
for c in ws[1]:
    c.fill, c.font, c.border, c.alignment = HDR, HF, BOX, Alignment(wrap_text=True, vertical="center")
for row in ws.iter_rows(min_row=2):
    for c in row:
        c.font, c.border, c.alignment = Font(name=F), BOX, Alignment(wrap_text=True, vertical="top")
    res = row[16].value
    if res in FILL:
        for c in row[15:18]:
            c.fill = FILL[res]
for i, wdt in enumerate([14, 14, 9, 10, 10, 9, 9, 9, 11, 11, 12, 9, 9, 9, 8, 12, 12, 60, 45], 1):
    ws.column_dimensions[get_column_letter(i)].width = wdt
ws.freeze_panes = "C2"


def table(title, rows, widths):
    t = wb.create_sheet(title)
    t.append(list(rows[0].keys()))
    for r in rows:
        t.append(list(r.values()))
    for c in t[1]:
        c.fill, c.font, c.border, c.alignment = HDR, HF, BOX, Alignment(wrap_text=True, vertical="center")
    for row in t.iter_rows(min_row=2):
        for c in row:
            c.font, c.border, c.alignment = Font(name=F), BOX, Alignment(wrap_text=True, vertical="top")
    for i, wdt in enumerate(widths, 1):
        t.column_dimensions[get_column_letter(i)].width = wdt
    t.freeze_panes = "A2"


table("Must be exact", rd("staging_checks.csv"), [16, 46, 16, 16, 10, 50])
table("Spot checks", rd("spot_checks.csv"), [16, 12, 12, 40, 60])
wb.save(OUT)
print("saved", OUT)
