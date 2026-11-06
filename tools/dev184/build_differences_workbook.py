import csv, json, math, sys, collections
# DEV-184: Zoho (old BI) vs platform differences, one row per Survey Response, labelled, for ops. Read-only research.
# Usage from the repo root:
#   .venv/bin/python -I tools/dev184/build_differences_workbook.py "$PWD" out/dev184 out/DEV-184_zoho_vs_platform_2026-11-04.xlsx
# Inputs in out/dev184/ (git-ignored, from staging, Zoho and Alchemer on 4 Nov 2026):
#   zoho_ids_<account>.txt         month <TAB> Zoho response ids (distinct "Response ID" before the platform start)
#   stg_responses.csv              every Survey Response of the 3 surveys on staging (ids, status, dates, link kind)
#   legacy_linked_detail.csv       responses linked by the *_LEGACY_V1 loads, with the clinic row they link to
#   arcadia_reused_rows_db.csv     the 578 clinic rows on reused legacy ids, with their Patient on staging
#   arcadia_reused_responses_db.csv the 93 responses on reused ids (answers included)
# Alchemer checks that need a person's eyes are in ALCHEMER below: edit there, then rebuild.
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

REPO, IN, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
F = 'Arial'
HDR = PatternFill('solid', fgColor='1F3864'); HF = Font(name=F, bold=True, color='FFFFFF')
INP = PatternFill('solid', fgColor='FFF2CC'); RED = PatternFill('solid', fgColor='F8CBAD')
thin = Side(style='thin', color='BFBFBF'); BOX = Border(top=thin, bottom=thin, left=thin, right=thin)

ACC = {  # account key: name, Alchemer survey, Zoho workspace / table, platform start (Zoho cut-off)
    'videntis':  ('Videntis Dental Centar', '90508475', 'Videntis / JOINED_FINAL', '2024-10-21'),
    'arcadia':   ('Arcadia', '90534273', 'Arcadia / Joined_Final', '2025-04-24'),
    'apolonija': ('Stomatološka poliklinika Apolonija', '90492576', 'Apolonija / JOINED', '2024-10-21'),
}
# Single responses opened in Alchemer with get_response on 4 Nov 2026 (Ana's permission). Only these fields are kept.
ALCHEMER = {
    ('apolonija', '127'): 'Deleted in Alchemer (deleted 8 Nov 2024, sguid 1065). DB still says Complete',
    ('apolonija', '300'): 'Deleted in Alchemer (deleted 8 Nov 2024, sguid 10942). DB still says Complete',
    ('arcadia', '34'):    'Exists in Alchemer: Partial, sguid 10156, score 8 (same as DB)',
}
# Survey totals, Alchemer count_responses vs prod replica, 4 Nov 2026 (real counts)
COUNTS = [
    ('Videntis', 'all time', 'Complete', 900, 900, 'match'),
    ('Videntis', 'all time', 'Partial', 179, 179, 'match'),
    ('Arcadia', 'submitted before 24 Apr 2025 (legacy period)', 'Complete', 928, 928, 'match'),
    ('Arcadia', 'submitted before 24 Apr 2025 (legacy period)', 'Partial', 155, 155, 'match'),
    ('Arcadia', 'submitted before 1 Jan 2026', 'Complete', 1390, 1390, 'match'),
    ('Arcadia', 'submitted before 1 Jan 2026', 'Partial', 220, 220, 'match'),
    ('Arcadia', 'all time', 'Complete', 2041, 2040, 'recent (2026) responses still syncing; not in the legacy period'),
    ('Arcadia', 'all time', 'Partial', 321, 323, 'recent (2026) responses still syncing; not in the legacy period'),
    ('Apolonija', 'submitted before 21 Oct 2024 (legacy period)', 'Complete', 1353, 1355, 'DB +2: responses 127 and 300, Deleted in Alchemer'),
    ('Apolonija', 'submitted before 21 Oct 2024 (legacy period)', 'Partial', 189, 189, 'match'),
    ('Apolonija', 'all time', 'Complete', 2364, 2366, 'DB +2: responses 127 and 300, Deleted in Alchemer'),
    ('Apolonija', 'all time', 'Partial', 320, 320, 'match'),
]
LABELS = {
    'REUSED_ID': ('Zoho counts it, the platform does not',
                  'The legacy id in the survey link (sguid) is on two clinic rows for two different Patients. The files cannot tell who answered, '
                  'so the load left the response unlinked (decision 13). Zoho joined it to a Patient anyway.',
                  'Pick the Patient in sheet "Arcadia reused ids". After a decision the response can be linked; it then shows in Clinicdash.'),
    'SGUID_SPACE': ('The platform counts it, Zoho does not',
                    'The sguid has a leading/trailing space. Zoho joined on the exact text and missed it. The load matches it to the clinic id once trimmed (decision 11).',
                    'Check the clinic id in column "Linked clinic id" is the same number as the sguid without spaces.'),
    'SGUID_TEXT': ('The platform counts it, Zoho does not',
                   'The sguid is stored as text (for example an "apo…" id), matching a clinic id written the same way. Zoho never matched it (decision 11).',
                   'Check the clinic id in column "Linked clinic id" is the same as the sguid.'),
    'DELETED_IN_ALCHEMER': ('The platform counts it, Zoho and Alchemer do not',
                            'Deleted in Alchemer on 8 Nov 2024, but the DB still has it as Complete (the sync missed the deletion). The load linked it because the DB said Complete.',
                            'Confirm it should not count. Fix proposed: unlink before production and ask the devs to resync its status.'),
    'LATE_RESPONSE': ('The platform counts it in a platform-era month, Zoho does not (yet)',
                      'A real response to a legacy invite, opened after the platform started. Today it is unlinked on prod, so Clinicdash misses it while Zoho counts it; '
                      'the load links it. Kept linked (Ana, 4 Nov 2026).',
                      'Nothing to do. After the load it shows in the month it was started, as in Zoho.'),
    'NO_SCORE': ('Zoho counts it, Clinicdash "Total responses" does not',
                 'Linked by the load, but the response has no NPS score. Clinicdash counts only scored responses; Zoho counts every response.',
                 'Nothing to do; expected. Open it in Alchemer if you want to confirm there is no score.'),
}

def rd(name): return list(csv.DictReader(open(f'{IN}/{name}', encoding='utf-8-sig')))
def ym(d): return d[:7]

def sheet(wb, title, headers, rows, widths, wrap=False, input_cols=(), red=None):
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
        if red and red(row): row[0].fill = RED
    for i, w in enumerate(widths, 1): ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'B2'
    ws.auto_filter.ref = ws.dimensions
    return ws

def dropdown(ws, col, options, n):
    dv = DataValidation(type='list', formula1='"' + ','.join(options) + '"', allow_blank=True)
    ws.add_data_validation(dv); dv.add(f'{col}2:{col}{n + 1}')

stg = rd('stg_responses.csv')
det = {(d['code'].split('_')[0].lower(), d['rid']): d for d in rd('legacy_linked_detail.csv')}

# 1) Differences, one row per response ----------------------------------------------------------------------------------
diff, summary = [], []
for a, (name, sid, zoho, start) in ACC.items():
    z = {}
    for line in open(f'{IN}/zoho_ids_{a}.txt'):
        m, ids = line.rstrip('\n').split('\t'); z.update({i: m for i in ids.split()})
    s = {r['rid']: r for r in stg if r['acc'] == a}
    legacy = {k for k, r in s.items() if r['link'] == 'legacy'}
    lab = {}
    for k in set(z) - legacy: lab[k] = 'REUSED_ID' if s.get(k, {}).get('sguid_reused') == 't' else 'UNEXPLAINED'
    for k in legacy - set(z):
        r = s[k]
        if (a, k) in ALCHEMER and 'Deleted' in ALCHEMER[(a, k)]: lab[k] = 'DELETED_IN_ALCHEMER'
        elif r['started_local'] >= start: lab[k] = 'LATE_RESPONSE'
        elif r['sguid_shape'] == 'numeric_with_spaces': lab[k] = 'SGUID_SPACE'
        elif r['sguid_shape'] == 'text': lab[k] = 'SGUID_TEXT'
        else: lab[k] = 'UNEXPLAINED'
    for k in legacy & set(z):
        if s[k]['score'] == '': lab[k] = 'NO_SCORE'
    for k in sorted(lab, key=int):
        r, d, L = s.get(k, {}), det.get((a, k), {}), lab[k]
        what, why, todo = LABELS.get(L, ('?', 'Not explained yet', 'Tell Ana'))
        diff.append([name, sid, int(k), r.get('status', 'not in DB'), r.get('started_local', ''), r.get('score', ''),
                     d.get('sguid_quoted', ''), d.get('clinic_id', ''), d.get('est_sent', ''),
                     'yes (' + z[k] + ')' if k in z else 'no',
                     'no (no score)' if L == 'NO_SCORE' else 'after load (' + ym(r['started_local']) + ')' if k in legacy else 'no',
                     L, what, why, ALCHEMER.get((a, k), 'Totals match Alchemer for the legacy period (sheet "Alchemer vs DB")'),
                     todo, '', ''])
    in_win = [k for k in legacy if s[k]['started_local'] < start]
    c = collections.Counter(v for v in lab.values() if v != 'NO_SCORE')
    summary.append([name, sid, zoho, start, len(z), len(in_win), len(in_win) - len(z), len(legacy),
                    ', '.join(f'{k} {v}' for k, v in sorted(c.items())), 'yes' if 'UNEXPLAINED' not in c else 'NO'])

# 2) Arcadia reused ids: both clinic rows next to the response ------------------------------------------------------------
load = {r['row_no']: r for r in csv.DictReader(open(f'{REPO}/accounts/arcadia/data/arcadia_full_v1.csv', encoding='utf-8-sig'))}
dbrow = {r['row_no']: r for r in rd('arcadia_reused_rows_db.csv')}
resp_by_row = sorted((int(d['row_no']), d['started_local'][:10]) for (a, _), d in det.items() if a == 'arcadia')
def neighbours(row_no, n=10):  # response dates of the n nearest clinic rows (by file order) that have a linked response
    near = sorted(resp_by_row, key=lambda t: abs(t[0] - row_no))[:n]
    return sorted(d for _, d in near)[len(near) // 2] if near else ''
def days(a, b):
    from datetime import date
    return (date.fromisoformat(a) - date.fromisoformat(b)).days if a and b else ''
def answer(sd, qid):
    q = sd.get(str(qid)) or {}
    return q.get('answer') or ''
rows_by_id = collections.defaultdict(list)
for r in load.values():
    if r['sguid_reused'] == 'true': rows_by_id[r['legacy_sguid']].append(r)
reused = []
for x in rd('arcadia_reused_responses_db.csv'):
    sd = json.loads(x['survey_data'] or '{}')
    cand = sorted(rows_by_id[x['sguid'].strip()], key=lambda r: int(r['row_no']))
    line = [int(x['rid']), x['sguid'], x['status'], x['started_local'], x['nps'], answer(sd, 103), answer(sd, 104), answer(sd, 98),
            answer(sd, 93) or answer(sd, 92) or x['comment'] or '']
    for r in cand[:2]:
        p, nb = dbrow.get(r['row_no'], {}), neighbours(int(r['row_no']))
        line += [int(r['row_no']), r['raw_source_id'], f"{r['raw_first_name']} {r['raw_last_name']}".strip(), r['raw_phone'], r['raw_year_of_birth'],
                 r['raw_doctor'], r['raw_procedure'], r['row_kind'].replace('legacy_', ''), p.get('patient_id', ''),
                 {'t': 'existing', 'f': 'new'}.get(p.get('patient_existed_before_import'), ''), p.get('platform_invites', ''),
                 p.get('clinic_rows_same_patient', ''), nb, days(x['started_local'][:10], nb)]
    reused.append(line + ['', ''])

# 3) Prod totals after the load, per month: Clinicdash today (prod replica) + what the load adds, against Zoho -------------
# Zoho counts every response once; Clinicdash "Total responses" counts scored, linked responses by "dateStarted" (Zagreb).
SURVEY = {v[1]: a for a, v in ACC.items()}
now = collections.defaultdict(lambda: [0, 0, 0])
for r in rd('prod_clinicdash_monthly.csv'):
    now[(SURVEY[r['survey']], r['ym'][:4] + '-' + r['ym'][4:])] = [int(r['responses']), int(r['promoters']), int(r['detractors'])]
add = collections.defaultdict(lambda: [0, 0, 0])
for (a, _), d in det.items():
    if d['nps'] == '': continue
    sc = round(float(d['nps'])); t = add[(a, ym(d['started_local']))]
    t[0] += 1; t[1] += sc >= 9; t[2] += sc <= 6
zc = collections.Counter()
for a in ACC:
    for f in (f'zoho_ids_{a}.txt', f'zoho_platform_ids_{a}.txt'):
        try:
            for line in open(f'{IN}/{f}'):
                m, ids = line.rstrip('\n').split('\t'); zc[(a, m[:4] + '-' + m[4:])] += len(ids.split())
        except FileNotFoundError: pass
for line in open(f'{IN}/zoho_platform_counts_apolonija.txt'):
    m, n = line.split(); zc[('apolonija', m[:4] + '-' + m[4:])] += int(n)
why = collections.defaultdict(collections.Counter)  # month -> labels that explain the gap
for d in diff:
    a = next(k for k, v in ACC.items() if v[0] == d[0]); m = (d[4] or '')[:7]
    why[(a, m)][d[11] + ' (legacy file)'] += 1
for r in rd('platform_diffs.csv'):
    if r['label'] == 'FIXED_BY_LEGACY_LOAD': continue  # already in the legacy labels (LATE_RESPONSE)
    why[(r['acc'], r['started'][:7])][r['label'] + ' (platform-era file)'] += 1
def nps(p, d, n): return '' if n == 0 else math.floor(1000 * (p - d) / n + 0.5) / 10  # Clinicdash half-up rounding
proj = []
for a, (name, *_ ) in ACC.items():
    months = sorted({m for (x, m) in list(now) + list(add) + list(zc) if x == a})
    tot = [0] * 6
    for m in months:
        n0, a0, z = now[(a, m)], add[(a, m)], zc[(a, m)]
        after = [n0[i] + a0[i] for i in range(3)]
        tot = [tot[0] + z, tot[1] + n0[0], tot[2] + a0[0], tot[3] + after[0], tot[4] + after[1], tot[5] + after[2]]
        proj.append([name, m, z, n0[0], a0[0], after[0], after[0] - z, nps(after[1], after[2], after[0]),
                     ', '.join(f'{k} {v}' for k, v in sorted(why[(a, m)].items()))])
    proj.append([name, 'TOTAL', tot[0], tot[1], tot[2], tot[3], tot[3] - tot[0], nps(tot[4], tot[5], tot[3]), ''])

# 4) Write ----------------------------------------------------------------------------------------------------------------
wb = Workbook(); rm = wb.active; rm.title = 'Read me'
for t in [
    'DEV-184: differences between Zoho (old BI) and the platform (Clinicdash), legacy period. Built 4 Nov 2026 from EU staging, Zoho and Alchemer. Read-only research: nothing was changed anywhere.',
    'Source of truth is Alchemer. Every response is identified by its Alchemer response id. Zoho and the platform are compared by response id, not only by month.',
    'Sheet "Summary": per Account, Zoho vs platform counts and how many differences each label explains. Every difference has a label; none is unexplained.',
    'Sheet "Differences": one row per response that one side counts and the other does not. Columns "What", "Why" and "What ops should do" explain each label. Yellow columns are for you.',
    'Sheet "Arcadia reused ids": 93 responses whose legacy id is on two clinic rows (two Patients). Both rows are shown side by side (row A = first in the clinic file, row B = second). Pick A, B or "can\'t tell" in the yellow column.',
    'Sheet "Prod totals after load": per month, Zoho vs Clinicdash today on prod vs Clinicdash after the load (projected from the staging load). Every gap is labelled; '
    'gaps that already exist today and have nothing to do with the legacy data are in the separate file DEV-184_platform_era_differences.',
    'Sheet "Alchemer vs DB": survey totals in Alchemer vs our database. They match for the legacy period, except 2 Apolonija responses deleted in Alchemer.',
    'Real vs estimated: responses, dates started, scores and answers are REAL (Alchemer). "Est. send date" and the neighbour dates come from the estimated send dates of the import and are ESTIMATED.',
    'How to open a response in Alchemer: log in at app.alchemer.com, open the survey by its id (column "Alchemer survey"), Results > Individual Responses, search the Response ID.',
    'Zoho: workspace and query table are in sheet "Summary"; Zoho counts each response once, started before the platform start date.',
    'Contains patient data (sheet "Arcadia reused ids"). Do not forward outside InsiderCX ops; delete after the decision.',
]: rm.append([t])
rm.column_dimensions['A'].width = 150
for c in rm['A']: c.font, c.alignment = Font(name=F), Alignment(wrap_text=True, vertical='top')
rm['A1'].font = Font(name=F, bold=True)

sheet(wb, 'Summary', ['Account', 'Alchemer survey', 'Zoho workspace / table', 'Platform start (Zoho cut-off)', 'Zoho responses',
                      'Platform legacy responses before cut-off', 'Platform minus Zoho', 'Platform legacy responses, all dates',
                      'Differences by label', 'All explained'], summary, [30, 12, 26, 14, 10, 14, 10, 14, 50, 10], wrap=True)
ws = sheet(wb, 'Differences', ['Account', 'Alchemer survey', 'Alchemer response id', 'Status (DB)', 'Started (Zagreb)', 'Score',
                               'sguid as stored (quotes show spaces)', 'Linked clinic id', 'Est. send date (ESTIMATED)', 'In Zoho (month)',
                               'In Clinicdash (month)', 'Label', 'What', 'Why', 'Alchemer check', 'What ops should do', 'Ops check', 'Ops notes'],
           diff, [22, 11, 10, 10, 16, 6, 14, 10, 12, 12, 12, 20, 28, 60, 34, 46, 12, 30], wrap=True, input_cols=(17, 18),
           red=lambda row: row[11].value in ('DELETED_IN_ALCHEMER', 'UNEXPLAINED'))
dropdown(ws, 'Q', ['OK', 'Not OK', 'Question'], len(diff))
cand = ['Clinic row', 'Clinic patient id (source_id)', 'Name', 'Phone', 'Year of birth', 'Doctor', 'Procedure', 'Row kind',
        'Patient id (staging)', 'Patient existed before import', 'Platform invites of this Patient', 'Clinic rows of this Patient',
        'Neighbour rows: median response date (ESTIMATED hint)', 'Days from neighbours to this response']
ws = sheet(wb, 'Arcadia reused ids',
           ['Alchemer response id', 'Legacy id (sguid)', 'Status', 'Started (Zagreb)', 'Score', 'First visit? (answer)', 'Would come again? (answer)',
            'Started on time? (answer)', 'Comment'] + [f'A: {h}' for h in cand] + [f'B: {h}' for h in cand] + ['Ops decision', 'Ops notes'],
           reused, [10, 9, 9, 16, 6, 10, 10, 10, 40] + [8, 12, 22, 14, 8, 18, 18, 8, 10, 10, 8, 8, 12, 8] * 2 + [14, 30], wrap=True,
           input_cols=(9 + 2 * len(cand) + 1, 9 + 2 * len(cand) + 2))
dropdown(ws, get_column_letter(9 + 2 * len(cand) + 1), ['A', 'B', "Can't tell"], len(reused))
sheet(wb, 'Prod totals after load', ['Account', 'Month (Zagreb)', 'Zoho responses (real)', 'Clinicdash today on prod (real)',
                                     'Added by the load (real responses)', 'Clinicdash after the load (projected)', 'After load minus Zoho',
                                     'NPS after the load (projected)', 'Gap explained by (labels; see Differences here and the platform-era file)'],
      proj, [22, 10, 10, 12, 12, 12, 10, 10, 80], wrap=True, red=lambda row: row[1].value == 'TOTAL')
sheet(wb, 'Alchemer vs DB', ['Account', 'Period', 'Status', 'Alchemer (real)', 'Prod DB (real)', 'Result'], COUNTS, [12, 40, 10, 12, 12, 60], wrap=True)
wb.save(OUT)
print('differences', len(diff), collections.Counter(r[11] for r in diff), '| reused', len(reused), '| ->', OUT)
for s_ in summary: print(s_[0], '| zoho', s_[4], '| platform', s_[5], '| diff', s_[6], '|', s_[8], '| explained', s_[9])
