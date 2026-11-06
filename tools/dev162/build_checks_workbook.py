import csv, re, sys, collections
# DEV-162 / DEV-184 checklist (out/DEV-162_checks.xlsx). Usage from the repo root:
#   .venv/bin/python -I tools/dev162/build_checks_workbook.py "$PWD" out/dev162/unlinked.tsv out/DEV-162_checks.xlsx
# Check rows (C.., L..) and their status live in the list C below: edit there, then rebuild.
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

REPO, TSV, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
F = 'Arial'
HDR = PatternFill('solid', fgColor='1F3864'); HF = Font(name=F, bold=True, color='FFFFFF')
INP = PatternFill('solid', fgColor='FFF2CC')
thin = Side(style='thin', color='BFBFBF'); BOX = Border(top=thin, bottom=thin, left=thin, right=thin)

def load(p): return list(csv.DictReader(open(f'{REPO}/accounts/{p}', encoding='utf-8-sig')))
clin = {38: load('videntis/data/Pacijenti_JOINED_Videntis.csv'),
        45: load('arcadia/data/Pacijenti_Joined_Arcadia.csv'),
        39: load('apolonija/data/Pacijenti_JOINED_Apolonija.csv')}
ids = {a: {r['id'].strip() for r in rows} for a, rows in clin.items()}
NAME = {38: 'Videntis', 45: 'Arcadia', 39: 'Apolonija'}
un = list(csv.DictReader(open(TSV), delimiter='\t'))

def sheet(wb, title, headers, rows, widths, wrap=False, input_cols=()):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for c in ws[1]:
        c.fill, c.font, c.border = HDR, HF, BOX
        c.alignment = Alignment(wrap_text=True, vertical='center')
    for r in rows: ws.append(r)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font, c.border = Font(name=F), BOX
            c.alignment = Alignment(wrap_text=wrap, vertical='top')
            if c.column in input_cols: c.fill = INP
    for i, w in enumerate(widths, 1): ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    return ws

TESTLIKE = re.compile(r'test|^t+1?t*s+|^1111|^111222|^40275999993$', re.I)
def reason(a, r):
    sg = r['sg']
    if not sg.strip(): return 'Empty sguid'
    if r['t'] == 't' or TESTLIKE.search(sg.strip()): return 'Test link'
    if sg.strip() in ids[a]:
        return 'Linkable after sguid fix' if sg != sg.strip() or not sg.isdigit() else 'Linkable'
    return 'Invite missing from clinic file' if sg.strip().isdigit() else 'Text sguid, not in clinic file'

wb = Workbook(); wb.remove(wb.active)

# ---------- Read me ----------
rm = wb.create_sheet('Read me')
lines = [
 ('DEV-162 legacy import: what needs checking', True),
 ('Videntis (EU 38), Arcadia (EU 45), Apolonija (EU 39). Built 3 Nov 2026 from the EU prod replica and the clinic files.', False),
 ('', False),
 ('How to use', True),
 ('1. Go to the Checks sheet. Each row is one thing a person has to check or decide.', False),
 ('2. Fill only the yellow columns: Status, Answer / decision, Checked by, Date.', False),
 ('3. Status is a drop-down: Open, Decided, Checked, Later. "Later" rows belong to later steps (staging, ops, dev review, production).', False),
 ('4. The Detail sheet column names the sheet with the ids behind a row.', False),
 ('5. The Summary sheet counts rows by Status and updates by itself.', False),
 ('', False),
 ('Example of a filled row (Checks C03):', True),
 ('Status: Decided   |   Answer / decision: Leave the 93 responses unlinked; list them for ops   |   Checked by: Ana   |   Date: 2026-11-04', False),
 ('', False),
 ('Data', True),
 ('No names, phones or comments are in this file. Rows are identified by Alchemer response id, legacy id (sguid) or the line number in the clinic CSV (line 1 = header).', False),
 ('All numbers are real counts unless a row says "estimated".', False),
]
for i, (t, b) in enumerate(lines, 1):
    c = rm.cell(row=i, column=1, value=t); c.font = Font(name=F, bold=b, size=14 if i == 1 else 11)
rm.column_dimensions['A'].width = 140

# ---------- Checks ----------
H = ['ID', 'Account', 'Step', 'Topic', 'What to check', 'Evidence (real numbers)', 'Recommendation', 'Who',
     'Status', 'Answer / decision', 'Checked by', 'Date', 'Detail sheet']
C = [
 ('C01','All',1,'Account and Survey ids','Each Account, Location and Survey is the right one, and all three are on EU','Videntis 38 / 59 / 19 (Alchemer 90508475). Arcadia 45 / 78 / 27 (90534273). Apolonija 39 / 60 / 20 (90492576). None exist on UK','Confirm','Ana','Open',''),
 ('C02','All',1,'Input files','The 6 files are the latest exports from ops (no newer version)','SHA-256 of each file is in docs/plans/2026-11-03_videntis-arcadia-apolonija.md','Confirm with ops','Ana','Open',''),
 ('C03','Arcadia',1,'Reused legacy ids (A1)','Which Patient answered each of the 93 responses on a reused id','289 ids (10113–10467) are on two different Patients. 93 of them have one response. Files cannot decide: dates of nearby rows separate only 2 of 93. Alchemer (3 Nov): the responses carry only sguid, no patient field. Zoho: the original Arcadia tables were Access Denied','Ask the clinic. If no answer: leave the 93 unlinked and list them','Ana','Open','A1 Arcadia reused ids'),
 ('C04','Videntis',1,'Invites missing from clinic file (V1)','Get the 70 missing invite rows, or accept them as unlinked','70 legacy responses (64 "77…", 4 "10xx", 2 test-like), Nov 2022 – Oct 2024, point to ids that are not in the clinic file. Zoho (3 Nov): not in the old legacy table either (10,933 rows, same as the file)','Ask the clinic. If no answer: leave unlinked and list','Ana / ops','Open','V1 Videntis missing'),
 ('C05','Apolonija',1,'Rows without an id (P1)','What the 25,547 rows without an id are','Only name, phone and (21,436 of them) a comment are filled. Every phone also appears on a row with an id','Keep as raw rows only (export stays identical) until ops answer','Ops','Open','P1 Apolonija no-id rows'),
 ('C06','Apolonija',1,'"#N/A" ids','29 clinic rows have the id "#N/A" (an Excel error, not a real id)','29 rows','Ask ops for the real ids. If none: import as legacy visits without an invite','Ops','Open','P1 Apolonija no-id rows'),
 ('C07','Apolonija',1,'Sguids with a leading space or "apo" ids','Link responses whose sguid matches a clinic id once the space is removed','45 match: 36 like " 402293" and 9 like " apo147". Not matching: " 101" and 7 "apo/appo" ids','Link the 45 (the link table stores the sguid exactly as Alchemer has it)','Ana','Open','Sguid fixes'),
 ('C08','Videntis',1,'"vid" ids','Link responses with sguid "vid66" and "vid62" (both are clinic ids)','2 match. "vid5" and "vid51" are not in the clinic file','Link the 2','Ana','Open','Sguid fixes'),
 ('C09','All',1,'Deleted responses','Link responses that Alchemer marks as Deleted?','Deleted among linkable responses: Apolonija 4 (3 as is + 1 after the sguid fix), Videntis 0, Arcadia 0. SIE linked 0 of its 9 Deleted','Do not link Deleted responses (same as SIE)','Ana','Open','Unlinked responses'),
 ('C10','All',2,'Send-date method','Accept the two changes to SIE\'s send-date method','Built 3 Nov: (1) dates interpolated between isotonic block midpoints instead of steps; (2) id groups with Spearman < 0.95 get the response send-time quantiles by id rank. Weekend dates move to Monday. Result: median 7 / 10 / 14 estimated invites per day (platform ~7 / 9 / 15); big days left are real batch days (e.g. Apolonija 16 Nov 2022: 246 real responses). One artifact day: Videntis 17 Jun 2024 (70 invites, 0 responses)','Accept (all values stay labelled estimated)','Ana','Open','Id groups'),
 ('C11','Videntis',1,'SL language','120 legacy rows are SL, and there is no SL template','Templates: 79 HR, 80 EN, 81 FR, 82 DE, 83 IT','Use the HR template for SL (same rule as SIE)','Ana','Open',''),
 ('C12','Arcadia',1,'Year of birth','Legacy rows have a real year_of_birth: use it as is','7,085 of 7,098 legacy rows filled','Use as is, nothing derived','Ana','Open',''),
 ('C13','All',1,'Legacy responses after platform start','One legacy response per Account started after the platform began. Link it like the others?','Videntis 1 (Oct 2024), Arcadia 1 (May 2026), Apolonija 1 (Jun 2025)','Link them: they answer a legacy invite','Ana','Open',''),
 ('C14','Arcadia',1,'Response dated 1 Jan 1970','Alchemer response 2267 has start date 1970-01-01 and no sguid','1 response','Not linkable. Report to dev as a data error','Ana','Open','Unlinked responses'),
 ('C15','All',1,'Date format','Survey and clinic dates are day-first (DD/MM/YYYY), Zagreb time','15 of 15 sampled responses match the DB exactly','None: verified','Claude','Checked',''),
 ('C16','All',1,'Responses missing from the DB','Survey-file responses that are not in the DB (decision 6)','0 for all three Accounts','None: nothing to list','Claude','Checked',''),
 ('C17','All',1,'Schema facts','Facts the scripts depend on still hold on prod','Facts 1–5, 7, 8 and 11 re-checked 3 Nov 2026. Prod already has SIE\'s legacy tables and trigger fallback','New 01 scripts reuse them','Claude','Checked',''),
 ('C18','Apolonija',1,'No age (decision 4)','year_of_birth stays empty; invite replay skips the age rule (limit 25)','30,928 legacy rows without age','Decided 3 Nov 2026','Ana','Decided',''),
 ('L01','Videntis',2,'Age meaning','"age" is age at the visit (as in SIE)? Check on existing Patients','No: it is age in 2026 (5,454 of 5,483 platform rows exact; age at visit only 2,070). Year of birth = 2026 − age','Used in the load file','Claude','Checked',''),
 ('L02','All',2,'Replay recall','Invite replay recovers ≥ 85% of real platform-era invites (decision 7)','Videntis 92.6%, Arcadia 89.4% (age rule 18), Apolonija 89.8% (no age rule; the platform does not apply its limit 25: 5,810 real invites to Patients under 25)','Passes','Claude','Checked',''),
 ('L03','All',2,'Load files','Load files built; SHA-256 recorded in the account cards','Built 3 Nov 2026. All original values kept; Videntis byte-identical','Done','Claude','Checked',''),
 ('C19','All',3,'Export quoting','The 04 export must reproduce the clinic file byte for byte','Arcadia 101 and Apolonija 157 lines quote values that need no quotes. Values are identical','Compare by value (the GUI export decides its own quoting anyway). Mock test: values identical for all three','Claude','Checked',''),
 ('L04','All',3,'Mock tests','Mock test passes for all three (load, validation, identical export, rollback)','3 Nov: load path (01, 02, 03, 04, 99) passes for all three, incl. phone matching, Deleted not linked, reused ids not linked, rollback to baseline, SIE untouched. Ops SQL (05–08) not written yet','Finish with 05–08','Claude','Open',''),
 ('L05','All',4,'Staging contents','Staging has each Account, Survey and unlinked responses (decision 2: no fresh snapshot)','3 Nov: all three present; unlinked 619 / 1,091 / 1,566 (prod 619 / 1,092 / 1,566); newest response 28 Sep 2026','OK','Claude','Checked',''),
 ('L06','All',4,'Staging load','Load counts and 03 validation match the account cards; differences only from staging age','3 Nov: all counts match; linked 504 / 979 / 1,517; NPS 78.4 / 89.1 / 83.6 (real). Only platform rows linked are lower (staging age)','OK','Claude','Checked',''),
 ('L07','All',4,'Export','04 export equals the clinic file for each Account','3 Nov: identical values for all three','OK','Claude','Checked',''),
 ('L08','All',4,'Rollback','99 rollback tested once per Account, then reloaded','3 Nov: works for all three; took 5 / 10 / 35 minutes','Make 99 faster before production (Apolonija holds locks 35 min), test again on staging','Claude','Open',''),
 ('C20','All',5,'Estimate artifacts at the start','First legacy quarter shows a high estimated response rate','Arcadia 2023 Q2 46.6% (27 responses on 66 est. sends); Apolonija 2022 Q4 25.6% (launch batch)','Tell ops to read the first two quarters together; label as estimated','Ana','Open',''),
 ('C21','All',4,'Staging vs Zoho (old BI)','Legacy responses and NPS per month on staging equal what Zoho showed','3 Nov: Videntis 24/24 months identical. Arcadia 16/22: −93 = exactly the reused-id responses (decision 13). Apolonija 20/24: +46 = 44 sguid fixes (decision 11) + 2 missing from the BI export. Sends not comparable (no legacy send data in Zoho)','Explained; ops to confirm','Claude','Checked',''),
 ('L09','Videntis',5,'Ops sign-off','Written ops confirmation','','','Ops','Later',''),
 ('L10','Arcadia',5,'Ops sign-off','Written ops confirmation','','','Ops','Later',''),
 ('L11','Apolonija',5,'Ops sign-off','Written ops confirmation','','','Ops','Later',''),
 ('L12','All',6,'Dev review','PR reviewed and approved by a dev; staging rerun where SQL changed (decision 10)','','','Dev','Later',''),
 ('L13','All',7,'Go / no-go','Backup, file hashes, CTO OK (also for any trigger change from C03)','','','Ana','Later',''),
 ('L14','All',7,'Clinicdash','Legacy period visible; platform period unchanged, for each Account','','','Ana','Later',''),
 ('L15','All',7,'Clean-up','Staging tables dropped; local patient files deleted','','','Ana','Later',''),
 ('L16','All',8,'Tell the clinic','Clinic and CSM know which legacy numbers are estimated','','','Ana','Later',''),
]
DONE = {'C03': 'Leave the 93 unlinked and listed for now; ask the clinic', 'C04': 'Leave the 70 unlinked and listed for now; ask the clinic',
        'C07': 'Link the 45', 'C08': 'Link the 2', 'C09': 'Do not link Deleted responses'}
rows = [[c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], 'Decided' if c[0] in DONE else c[8], DONE.get(c[0], ''),
         'Ana' if c[0] in DONE else '', datetime(2026, 11, 3).date() if c[0] in DONE else '', c[9]] for c in C]
ws = sheet(wb, 'Checks', H, rows, [6, 11, 6, 26, 48, 55, 45, 11, 10, 40, 12, 12, 22], wrap=True, input_cols=(9, 10, 11, 12))
dv = DataValidation(type='list', formula1='"Open,Decided,Checked,Later"', allow_blank=False)
ws.add_data_validation(dv); dv.add(f'I2:I{len(rows)+1}')
for r in range(2, len(rows) + 2): ws.cell(row=r, column=12).number_format = 'yyyy-mm-dd'
NCHK = len(rows) + 1

# ---------- Summary ----------
sm = wb.create_sheet('Summary', 1)
sm['A1'] = 'Checks by Account and Status'; sm['A1'].font = Font(name=F, bold=True, size=13)
hdr = ['Account', 'Open', 'Decided', 'Checked', 'Later', 'Total']
for j, h in enumerate(hdr, 1):
    c = sm.cell(row=2, column=j, value=h); c.fill, c.font, c.border = HDR, HF, BOX
accs = ['All', 'Videntis', 'Arcadia', 'Apolonija']
for i, a in enumerate(accs, 3):
    sm.cell(row=i, column=1, value=a)
    for j, st in enumerate(['Open', 'Decided', 'Checked', 'Later'], 2):
        sm.cell(row=i, column=j, value=f'=COUNTIFS(Checks!$B$2:$B${NCHK},$A{i},Checks!$I$2:$I${NCHK},{get_column_letter(j)}$2)')
    sm.cell(row=i, column=6, value=f'=SUM(B{i}:E{i})')
t = 3 + len(accs)
sm.cell(row=t, column=1, value='Total')
for j in range(2, 7):
    L = get_column_letter(j); sm.cell(row=t, column=j, value=f'=SUM({L}3:{L}{t-1})')
for row in sm.iter_rows(min_row=3, max_row=t, max_col=6):
    for c in row: c.font, c.border = Font(name=F, bold=(c.row == t)), BOX

r0 = t + 3
sm.cell(row=r0 - 1, column=1, value='Unlinked Survey Responses (real counts, EU prod replica, 3 Nov 2026)').font = Font(name=F, bold=True, size=13)
hdr2 = ['Account', 'Unlinked in DB', 'Linkable as is', 'Linkable after sguid fix (C07, C08)', 'Open: reused ids (C03)', 'Not linkable']
for j, h in enumerate(hdr2, 1):
    c = sm.cell(row=r0, column=j, value=h); c.fill, c.font, c.border = HDR, HF, BOX
    c.alignment = Alignment(wrap_text=True)
vals = [('Videntis', 619, 502, 2, 0), ('Arcadia', 1092, 979, 0, 93), ('Apolonija', 1566, 1476, 45, 0)]
for i, v in enumerate(vals, r0 + 1):
    for j, x in enumerate(v, 1): sm.cell(row=i, column=j, value=x)
    sm.cell(row=i, column=6, value=f'=B{i}-C{i}-D{i}-E{i}')
tt = r0 + 1 + len(vals)
sm.cell(row=tt, column=1, value='Total')
for j in range(2, 7):
    L = get_column_letter(j); sm.cell(row=tt, column=j, value=f'=SUM({L}{r0+1}:{L}{tt-1})')
for row in sm.iter_rows(min_row=r0 + 1, max_row=tt, max_col=6):
    for c in row:
        c.font, c.border = Font(name=F, bold=(c.row == tt)), BOX
        if c.column > 1: c.number_format = '#,##0'
sm.cell(row=tt + 1, column=1, value='Inputs in columns B–E are counts from the prod replica and the clinic files; "Not linkable" is calculated. The Unlinked responses sheet lists every not-linkable response by id.').font = Font(name=F, italic=True, size=9)
for j, w in enumerate([14, 14, 14, 22, 18, 14], 1): sm.column_dimensions[get_column_letter(j)].width = w

# ---------- A1 Arcadia reused ids ----------
P = clin[45]
pos = collections.defaultdict(list)
for i, r in enumerate(P):
    if r['id'].strip().isdigit(): pos[r['id'].strip()].append(i)
S = list(csv.DictReader(open(f'{REPO}/accounts/arcadia/data/Survey_responses_Arcadia.csv', encoding='utf-8-sig')))
resp = {}
for r in S:
    sg = r['URL Variable: sguid'].strip()
    if sg.isdigit() and sg not in resp:
        resp[sg] = (int(r['Response ID']), datetime.strptime(r['Time Started'].strip(), '%d/%m/%Y %H:%M:%S').date(), r['Status'])
a1 = []
for k, v in sorted(pos.items(), key=lambda x: int(x[0])):
    if len(v) < 2: continue
    rr = resp.get(k)
    a1.append([int(k), v[0] + 2, v[1] + 2, 'yes' if P[v[0]]['doctor'] == P[v[1]]['doctor'] else 'no',
               rr[0] if rr else None, rr[1] if rr else None, rr[2] if rr else None, '', ''])
ws = sheet(wb, 'A1 Arcadia reused ids', ['Legacy id', 'Clinic CSV line, Patient 1', 'Clinic CSV line, Patient 2', 'Same doctor', 'Alchemer response id', 'Response started', 'Response status', 'Belongs to (1 / 2 / unknown)', 'Source of answer'],
           a1, [11, 16, 16, 12, 14, 14, 13, 18, 22], input_cols=(8, 9))
for r in range(2, len(a1) + 2): ws.cell(row=r, column=6).number_format = 'yyyy-mm-dd'

# ---------- V1 Videntis missing ----------
v1 = [[int(r['rid']), r['sg'], datetime.strptime(r['d'], '%Y-%m-%d').date(), r['st'], '', ''] for r in un
      if r['a'] == '38' and reason(38, r) in ('Invite missing from clinic file', 'Test link') and r['sg'].strip().isdigit()]
ws = sheet(wb, 'V1 Videntis missing', ['Alchemer response id', 'Sguid (legacy invite id)', 'Response started', 'Response status', 'Found in Zoho / clinic? (yes / no)', 'Note'],
           v1, [14, 22, 14, 13, 22, 30], input_cols=(5, 6))
for r in range(2, len(v1) + 2): ws.cell(row=r, column=3).number_format = 'yyyy-mm-dd'

# ---------- P1 Apolonija no-id rows ----------
AP = clin[39]
p1 = [[i + 2, 'no id' if not r['id'].strip() else '#N/A', 'yes' if r['comment'].strip() else 'no'] for i, r in enumerate(AP) if not r['id'].strip() or r['id'].strip() == '#N/A']
ws = sheet(wb, 'P1 Apolonija no-id rows', ['Clinic CSV line', 'Id value', 'Has comment'], p1, [15, 12, 13])

# ---------- Sguid fixes ----------
fx = []
for r in un:
    a = int(r['a']); sg = r['sg']
    if a in (38, 39) and sg.strip() and not TESTLIKE.search(sg.strip()) and (sg != sg.strip() or not sg.strip().isdigit()):
        fx.append([NAME[a], int(r['rid']), f'"{sg}"', sg.strip(), 'yes' if sg.strip() in ids[a] else 'no', r['st']])
sheet(wb, 'Sguid fixes', ['Account', 'Alchemer response id', 'Sguid as stored (quotes show spaces)', 'Sguid trimmed', 'In clinic file', 'Response status'], fx, [12, 14, 30, 16, 13, 14])

# ---------- Unlinked responses ----------
ul = []
for r in un:
    a = int(r['a'])
    ul.append([NAME[a], int(r['rid']), r['sg'] if r['sg'] else '(empty)', datetime.strptime(r['d'], '%Y-%m-%d').date(), r['st'], 'yes' if r['t'] == 't' else 'no', reason(a, r)])
ws = sheet(wb, 'Unlinked responses', ['Account', 'Alchemer response id', 'Sguid', 'Response started', 'Status', 'Test flag', 'Reason'], ul, [12, 14, 34, 14, 11, 9, 30])
for r in range(2, len(ul) + 2): ws.cell(row=r, column=4).number_format = 'yyyy-mm-dd'

# ---------- Id groups ----------
ig = [['Videntis', '5 digits "10…"', 52, 0.707, 'Nov 2022 – Jan 2023'], ['Videntis', '5 digits "77…"', 51, 0.962, 'Feb – May 2023'],
      ['Videntis', '6 digits "77…"', 331, 0.999, 'May 2023 – Oct 2024'], ['Videntis', '7 digits "77…"', 48, 0.987, 'Aug – Oct 2024'],
      ['Arcadia', '4 digits "10…"', 33, 0.590, 'Jun – Aug 2023'], ['Arcadia', '5 digits "10…" (incl. reused)', 131, 0.574, 'Jul 2023 – Apr 2025'],
      ['Arcadia', '5 digits "11…"', 74, 0.959, 'Sep – Dec 2023'], ['Arcadia', '6 digits "11…"', 833, 0.997, 'Nov 2023 – Apr 2025'],
      ['Apolonija', '5 digits "10…"', 192, 0.438, 'Nov 2022 – Aug 2023'], ['Apolonija', '6 digits "10…"', 119, 0.216, 'Nov 2022 – Sep 2023'],
      ['Apolonija', '6 digits "40…"', 36, 0.041, 'Dec 2022 – Jan 2023'], ['Apolonija', '6 digits "77…"', 376, 0.968, 'Feb – Dec 2023'],
      ['Apolonija', '7 digits "77…"', 738, 0.995, 'Sep 2023 – Oct 2024']]
for g in ig: g.append(f'=IF(D{ig.index(g)+2}>=0.95,"ok","weak")')
ws = sheet(wb, 'Id groups', ['Account', 'Legacy id group', 'Responses', 'Spearman (id vs response time)', 'Period', 'Meets 0.95'], ig, [12, 28, 11, 16, 22, 11])
for r in range(2, len(ig) + 2): ws.cell(row=r, column=4).number_format = '0.000'

wb.calculation.fullCalcOnLoad = True
wb.save(OUT)
print('checks', len(rows), '| A1', len(a1), 'with response', sum(1 for x in a1 if x[4]), '| V1', len(v1), '| P1', len(p1), '| fixes', len(fx), 'linkable', sum(1 for x in fx if x[4] == 'yes'), '| unlinked', len(ul))
print('reasons', collections.Counter((x[0], x[6]) for x in ul))
print('deleted & linkable (fixes):', sum(1 for x in fx if x[4] == 'yes' and x[5] == 'Deleted'))
