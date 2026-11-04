import csv, sys, collections
# DEV-184: Zoho (old BI) vs Clinicdash differences that ALREADY EXIST in the platform era, before and without the legacy load.
# Separate from build_differences_workbook.py (legacy). Read-only research. Usage from the repo root:
#   .venv/bin/python -I tools/dev184/build_platform_differences_workbook.py out/dev184 out/DEV-184_platform_era_differences_2026-11-04.xlsx
# Inputs in out/dev184/ (prod replica, Zoho and Alchemer on 4 Nov 2026):
#   platform_diffs.csv                  one row per differing response (ids, status, dates, label)
#   prod_clinicdash_monthly.csv         Clinicdash "Total responses" per month on prod today
#   zoho_platform_ids_<account>.txt     Zoho response ids per month (Videntis, Arcadia)
#   zoho_platform_counts_apolonija.txt  Zoho response count per month (Apolonija)
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

IN, OUT = sys.argv[1], sys.argv[2]
F = 'Arial'
HDR = PatternFill('solid', fgColor='1F3864'); HF = Font(name=F, bold=True, color='FFFFFF')
INP = PatternFill('solid', fgColor='FFF2CC'); RED = PatternFill('solid', fgColor='F8CBAD')
thin = Side(style='thin', color='BFBFBF'); BOX = Border(top=thin, bottom=thin, left=thin, right=thin)

ACC = {  # account key: name, Alchemer survey, Zoho workspace / table, platform start
    'videntis':  ('Videntis Dental Centar', '90508475', 'Videntis / JOINED_FINAL', '2024-10'),
    'arcadia':   ('Arcadia', '90534273', 'Arcadia / Joined_Final', '2025-04'),
    'apolonija': ('Stomatološka poliklinika Apolonija', '90492576', 'Apolonija / JOINED', '2024-10'),
}
# label: (what, why, Alchemer check, what to do, who)
LABELS = {
    'ZOHO_JOIN_DROP': (
        'Clinicdash counts it, Zoho does not',
        'Zoho has the response in its raw Alchemer table (Apolonija_export_FINAL: same monthly counts as our database), but the query table JOINED drops it '
        'when it joins to its patient table Pacijenti_JOINED. Same Location, channel and template as the responses Zoho keeps: nothing on our side explains it.',
        'Totals match Alchemer (count by month, 4 Nov 2026)',
        'Clinicdash is right. Zoho\'s JOINED misses these. Either fix the Zoho join or accept that the old BI under-reports Mar–Aug 2026.', 'BI owner (Zoho)'),
    'ZOHO_NOT_SYNCED_YET': (
        'Clinicdash counts it, Zoho does not (yet)',
        'Started in the last days (Nov 2026). Zoho has not imported it yet.',
        'Not needed', 'Nothing to do. Check again after Zoho\'s next import.', '—'),
    'NO_SCORE': (
        'Zoho counts it, Clinicdash "Total responses" does not',
        'The response is linked but has no NPS score. Clinicdash counts only scored responses; Zoho counts every response.',
        'DB: Complete, no score', 'Nothing to do; expected definition difference.', '—'),
    'FIXED_BY_LEGACY_LOAD': (
        'Zoho counts it, Clinicdash does not today; fixed by the legacy load',
        'Answer to a legacy invite, opened after the platform started. Today it is unlinked on prod. The legacy load links it (see the legacy file, label LATE_RESPONSE).',
        'DB: legacy numeric sguid', 'Nothing extra; the legacy load fixes it.', 'Ana (legacy load)'),
    'NO_SGUID': (
        'In Alchemer, in neither dashboard',
        'Opened from the generic survey link: no sguid in Alchemer either, so it cannot be tied to a Visit Msg. Zoho and Clinicdash both leave it out.',
        'Alchemer: no sguid (get_response, 4 Nov 2026)', 'Nothing to do, unless ops know who answered.', 'Ops (optional)'),
    'SECOND_ANSWER_SAME_INVITE': (
        'In Alchemer, in neither dashboard',
        'Alchemer lost the sguid, but the referer URL holds it (sguid 763945cb…). That invite (sent 21 Aug 2025) already has one linked response, so this is a second answer from the same invite.',
        'Alchemer: no sguid, referer has it (get_response, 4 Nov 2026)', 'Decide if a second answer should count. Default: leave unlinked (one response per invite).', 'Ops'),
    'DUPLICATE_BROKEN_COPY': (
        'Both count it; the database has an extra broken copy',
        'Stored twice: a good copy (API, 6 Oct 2026, linked, score 8) and a broken webhook copy (dated 1 Jan 1970, no score, no sguid, unlinked). Dashboards use the good copy, '
        'but the broken copy inflates "unlinked responses" counts. The only duplicate in the 3 surveys.',
        'Alchemer: Complete, started 5 Oct 2026, score 8 (get_response, 4 Nov 2026)', 'Ask the devs to delete the broken copy (DB id 309489) and check why the webhook stored it.', 'Devs'),
}

def rd(name): return list(csv.DictReader(open(f'{IN}/{name}', encoding='utf-8-sig')))

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

# 1) Differences, one row per response ------------------------------------------------------------------------------------
diff = []
for r in rd('platform_diffs.csv'):
    name, sid, *_ = ACC[r['acc']]
    what, why, chk, todo, who = LABELS[r['label']]
    diff.append([name, sid, int(r['rid']), r['status'], r['started'], r['score'], r['in_zoho'], r['in_clinicdash'],
                 r['label'], what, why, chk, todo, who, '', ''])
diff.sort(key=lambda d: (d[0], d[2]))

# 2) Months, platform era: Zoho vs Clinicdash today on prod ---------------------------------------------------------------
SURVEY = {v[1]: a for a, v in ACC.items()}
cd = {(SURVEY[r['survey']], r['ym'][:4] + '-' + r['ym'][4:]): int(r['responses']) for r in rd('prod_clinicdash_monthly.csv')}
zc = collections.Counter()
for a in ('videntis', 'arcadia'):
    for line in open(f'{IN}/zoho_platform_ids_{a}.txt'):
        m, ids = line.rstrip('\n').split('\t'); zc[(a, m[:4] + '-' + m[4:])] += len(ids.split())
for line in open(f'{IN}/zoho_platform_counts_apolonija.txt'):
    m, n = line.split(); zc[('apolonija', m[:4] + '-' + m[4:])] += int(n)
why = collections.defaultdict(collections.Counter)
for r in rd('platform_diffs.csv'): why[(r['acc'], r['started'][:7])][r['label']] += 1
months, summary = [], []
for a, (name, sid, zoho, start) in ACC.items():
    ms = sorted({m for (x, m) in list(cd) + list(zc) if x == a and m >= start})
    tz = tc = 0
    for m in ms:
        z, c = zc[(a, m)], cd.get((a, m), 0); tz += z; tc += c
        months.append([name, m, z, c, c - z, ', '.join(f'{k} {v}' for k, v in sorted(why[(a, m)].items()))])
    lab = collections.Counter(r['label'] for r in rd('platform_diffs.csv') if r['acc'] == a)
    summary.append([name, sid, zoho, start, tz, tc, tc - tz, ', '.join(f'{k} {v}' for k, v in sorted(lab.items()))])

# 3) Write ----------------------------------------------------------------------------------------------------------------
wb = Workbook(); rm = wb.active; rm.title = 'Read me'
for t in [
    'DEV-184: differences between Zoho (old BI) and Clinicdash that ALREADY EXIST in the platform era (after each Account started on the platform). '
    'They have nothing to do with the legacy import; those are in the separate file DEV-184_legacy_differences. Built 4 Nov 2026 from the prod replica, Zoho and Alchemer. Read-only research.',
    'Source of truth is Alchemer. Responses are compared by Alchemer response id. Clinicdash = "Total responses": linked responses with a score, dated by when the Patient started the Survey (Zagreb time).',
    'Sheet "Summary": per Account, platform-era totals and the labels that explain the gap.',
    'Sheet "Differences": one row per response. "What ops should do" and "Who" say how to close each one. Yellow columns are for you.',
    'Sheet "Months": Zoho vs Clinicdash per month; every non-zero gap is explained by the labels in the last column.',
    'Biggest item: Apolonija, Mar–Aug 2026, 136 responses missing from Zoho\'s JOINED table (Zoho\'s join drops them). Clinicdash is right; the old BI under-reports.',
    'All numbers are REAL (no estimates in this file).',
    'How to open a response in Alchemer: log in at app.alchemer.com, open the survey by its id (column "Alchemer survey"), Results > Individual Responses, search the Response ID.',
]: rm.append([t])
rm.column_dimensions['A'].width = 150
for c in rm['A']: c.font, c.alignment = Font(name=F), Alignment(wrap_text=True, vertical='top')
rm['A1'].font = Font(name=F, bold=True)
sheet(wb, 'Summary', ['Account', 'Alchemer survey', 'Zoho workspace / table', 'Platform start', 'Zoho responses (platform era)',
                      'Clinicdash today (platform era)', 'Clinicdash minus Zoho', 'Differing responses by label'],
      summary, [30, 12, 26, 12, 12, 12, 12, 70], wrap=True)
ws = sheet(wb, 'Differences', ['Account', 'Alchemer survey', 'Alchemer response id', 'Status (DB)', 'Started (Zagreb)', 'Score', 'In Zoho',
                               'In Clinicdash today', 'Label', 'What', 'Why', 'Alchemer check', 'What ops should do', 'Who', 'Ops check', 'Ops notes'],
           diff, [22, 11, 10, 10, 12, 6, 12, 14, 24, 28, 70, 30, 46, 14, 12, 30], wrap=True, input_cols=(15, 16),
           red=lambda row: row[8].value in ('DUPLICATE_BROKEN_COPY', 'SECOND_ANSWER_SAME_INVITE'))
dv = DataValidation(type='list', formula1='"OK,Not OK,Question"', allow_blank=True)
ws.add_data_validation(dv); dv.add(f'O2:O{len(diff) + 1}')
sheet(wb, 'Months', ['Account', 'Month (Zagreb)', 'Zoho responses', 'Clinicdash today', 'Clinicdash minus Zoho', 'Explained by'],
      months, [30, 10, 10, 10, 10, 60], red=lambda row: row[4].value not in (0, None))
wb.save(OUT)
print('differences', len(diff), collections.Counter(d[8] for d in diff), '->', OUT)
for s in summary: print(s[0], '| zoho', s[4], '| clinicdash', s[5], '| diff', s[6], '|', s[7])
unexplained = [m for m in months if m[4] != 0 and not m[5]]
print('months with a gap and no label:', unexplained)
