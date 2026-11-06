import csv, collections, os, sys
# DEV-232: ops workbook for the Kvaternik, Mazalin and Optical Express legacy loads (EU staging, append only, no linking).
# One row per Survey Response of the legacy period, compared across Zoho (old BI), the prod replica (Clinicdash) and
# Alchemer, plus the lists ops must decide on. Ids only: no names, phones, source_id or comments.
# Usage from the repo root:
#   .venv/bin/python -I tools/dev232/build_ops_workbook.py "$PWD" out/dev232 out/DEV-232_ops_review_<date>.xlsx
# Inputs in out/dev232/ (git-ignored, 6 Nov 2026): stg_responses.csv (EU staging, after the loads), prod_responses_all.csv
# (prod replica), zoho_ids_<account>.txt (month <TAB> Zoho response ids, legacy months; Optical all months),
# zoho_monthly.csv (Zoho responses per month), alchemer_counts.csv. Plus each Account's data/ (load file).
# Alchemer is the source of truth for totals; Zoho is compared by response id for the legacy months, by count after.
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

REPO, IN, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
F = 'Arial'
HDR = PatternFill('solid', fgColor='1F3864'); HF = Font(name=F, bold=True, color='FFFFFF')
INP = PatternFill('solid', fgColor='FFF2CC'); EST = PatternFill('solid', fgColor='FCE4D6')
thin = Side(style='thin', color='BFBFBF'); BOX = Border(top=thin, bottom=thin, left=thin, right=thin)

ACC = {  # key: name, Alchemer survey, prod account id, Zoho workspace / table, platform start, staging batch, clinic file
    'kvaternik': ('Kvaternik', '90677816', 21, 'Poliklinika Kvaternik / JOINED_FINAL', '2024-03-05', 13097, 'Pacijenti_joined_Kvaternik.csv'),
    'mazalin': ('Poliklinika Mazalin', '90553181', 24, 'Poliklinika Mazalin / Joined', '2024-04-23', 13095, 'Pacijenti_Joined_Mazalin.csv'),
    'opticalexpress': ('Optical Express', '90535032', 44, 'Optical Express / Joined_final', '2025-03-04', 13099, 'Pacijenti_joined_OpticalExpress.csv'),
}
LABELS = {  # label: (where it shows, why, what ops do)
    'WOULD_LINK': ('Zoho counts it. Clinicdash does not, today or after this load',
                   'A real response to a legacy invite. The load adds the invite but does not link the response (append only, decision 2).',
                   'Question O1: link the legacy responses? If yes, it shows in Clinicdash in the month it was started.'),
    'ON_PLATFORM': ('Clinicdash and Zoho', 'Already linked to a platform invite before the load. Not touched.', 'Nothing.'),
    'DELETED': ('Neither (Deleted)', 'Deleted response. Never linked (as for every earlier Account).', 'Nothing.'),
    'INVITE_MISSING': ('Zoho may count it; Clinicdash does not', 'Numeric legacy sguid that is not in the clinic file, so there is no invite to attach it to.',
                       'Question O3: does the clinic have these rows?'),
    'NO_SGUID': ('Clinicdash does not', 'No sguid in the survey link (opened without an invite).', 'Nothing.'),
    'TEST_OR_TEXT': ('Clinicdash does not', 'Test link or a text sguid that is no clinic id.', 'Nothing.'),
}

def rd(path): return list(csv.DictReader(open(path, encoding='utf-8-sig')))

def sheet(wb, title, headers, rows, widths, input_cols=(), est_cols=()):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for c in ws[1]:
        c.fill, c.font, c.border = HDR, HF, BOX
        c.alignment = Alignment(wrap_text=True, vertical='center')
    for r in rows: ws.append(r)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font, c.border = Font(name=F), BOX
            c.alignment = Alignment(wrap_text=True, vertical='top')
            if c.column in input_cols: c.fill = INP
            if c.column in est_cols: c.fill = EST
    for i, w in enumerate(widths, 1): ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = 'B2'
    ws.auto_filter.ref = ws.dimensions
    return ws

def dropdown(ws, col, options, n):
    dv = DataValidation(type='list', formula1='"' + ','.join(options) + '"', allow_blank=True)
    ws.add_data_validation(dv); dv.add(f'{col}2:{col}{n + 1}')

ACC_ID = {v[2]: k for k, v in ACC.items()}
stg = rd(f'{IN}/stg_responses.csv')
prodall = rd(f'{IN}/prod_responses_all.csv')
zmon = {(r['account'], r['month']): int(r['zoho']) for r in rd(f'{IN}/zoho_monthly.csv')}
# Zoho id checksums per month (count, sum, min, max of response ids): an id-level check without copying every id
zsum = {(r['account'], r['month']): tuple(int(r[k]) for k in ('n', 's', 'lo', 'hi')) for r in rd(f'{IN}/zoho_checksums.csv')}
for line in open(f'{IN}/zoho_ids_opticalexpress.txt'):
    m, s = line.rstrip('\n').split('\t'); ids = [int(x) for x in s.split()]
    zsum[('opticalexpress', m)] = (len(ids), sum(ids), min(ids), max(ids))
def checksum(rows, a_id, m):  # responses Zoho can see: linked to an invite, not Deleted, not test
    ids = [int(r['rid']) for r in rows if int(r['acc']) == a_id and r['status'] != 'Deleted' and r.get('is_test') != 't'
           and r['link'] != 'unlinked' and r['started_local'][:4] + r['started_local'][5:7] == m]
    return (len(ids), sum(ids), min(ids), max(ids)) if ids else (0, 0, 0, 0)
STG_CUT = '202609'
ID_UNTIL = {'kvaternik': '202404', 'mazalin': '202406', 'opticalexpress': '202503'}   # by-id window: the legacy months   # the staging copy ends mid Sep 2026 (latest response 17-28 Sep); later months are not comparable
all_rows, resp_rows, month_rows, load_rows, corrected, repeated, missing, other = [], [], [], [], [], [], [], []
for a, (name, sid, acc, zoho, start, batch, clinic) in ACC.items():
    load = rd(f'{REPO}/accounts/{a}/data/{a}_full_v1.csv')
    unl = {r['rid']: dict(r, alchemer_response_id=r['rid'], started_utc=r['started_local']) for r in stg
           if int(r['acc']) == acc and r['link'] == 'unlinked'}
    inv = {r['legacy_sguid']: r for r in load if r['row_kind'] == 'legacy_invite'}
    clinic_ids = {r['raw_id'].strip() for r in load}
    p = {r['rid']: dict(r, link='linked' if r['link'] != 'unlinked' else 'unlinked') for r in stg if int(r['acc']) == acc}
    z, zfile = {}, f'{IN}/zoho_ids_{a}.txt'
    if os.path.exists(zfile):
        for line in open(zfile):
            m, ids = line.rstrip('\n').split('\t')
            if m <= ID_UNTIL[a]: z.update({i: m for i in ids.split()})
    zm_ = sorted(set(z.values()))
    zmonths = [f'{y}{mm:02d}' for y in range(int(zm_[0][:4]), int(zm_[-1][:4]) + 1) for mm in range(1, 13)
               if zm_[0] <= f'{y}{mm:02d}' <= zm_[-1]]   # months in the window with no Zoho row count as 0
    # one row per response: every unlinked response, every response started before the platform, every Zoho id fetched
    keys = set(unl) | {k for k, r in p.items() if r['started_local'][:10] < start} | set(z)
    lab = {}
    for k in keys:
        r, u = p.get(k, {}), unl.get(k)
        sg = (u['sguid'] if u else r.get('sguid', '')).strip()
        status = u['status'] if u else r.get('status', '')
        if not u and r.get('link') == 'linked': lab[k] = 'ON_PLATFORM'
        elif status == 'Deleted': lab[k] = 'DELETED'
        elif sg in inv: lab[k] = 'WOULD_LINK'
        elif sg == '': lab[k] = 'NO_SGUID'
        elif sg.isdigit() and sg not in clinic_ids: lab[k] = 'INVITE_MISSING'
        else: lab[k] = 'TEST_OR_TEXT'
    for k in sorted(keys, key=int):
        r, u, L = p.get(k, {}), unl.get(k), lab[k]
        started = r.get('started_local') or (u['started_utc'] if u else '')
        sg = (u['sguid'] if u else r.get('sguid', '')).strip()
        zm = z.get(k)
        in_window = bool(zmonths) and started[:4].isdigit() and started[:4] + started[5:7] in zmonths
        where, why, todo = LABELS[L]
        if L == 'INVITE_MISSING': missing.append([name, int(k), u['status'] if u else r.get('status', ''), started, sg, 'yes' if zm else ('no' if in_window else 'not fetched'), ''])
        resp_rows.append([name, int(k), u['status'] if u else r.get('status', ''), started, r.get('score', ''),
                          sg if L != 'TEST_OR_TEXT' else '(text)', 'yes' if (u is None and r.get('link') == 'linked') else 'no',
                          'yes (' + zm + ')' if zm else ('no' if in_window else 'not fetched'),
                          'yes (if linked)' if L == 'WOULD_LINK' else ('yes' if L == 'ON_PLATFORM' else 'no'), L, where, why, todo])
    # legacy months (by id): Zoho vs DB vs Clinicdash today / if linked; Zoho vs DB vs Clinicdash today / if linked
    by = collections.defaultdict(collections.Counter)
    for k in keys:
        r, u = p.get(k, {}), unl.get(k)
        started = r.get('started_local') or (u['started_utc'] if u else '')
        ym = started[:4] + started[5:7]
        st = u['status'] if u else r.get('status', '')
        if st != 'Deleted' and r.get('is_test') != 't': by[ym]['db'] += 1
        if lab[k] == 'ON_PLATFORM' and r.get('score', '') not in ('', 'None'): by[ym]['today'] += 1
        if lab[k] == 'WOULD_LINK': by[ym]['would'] += 1
        if k in z: by[ym]['zoho'] += 1
    for ym in sorted(by):
        if ym not in zmonths and ym >= start[:4] + start[5:7]:
            continue  # stray unlinked responses after the platform start (test / no sguid): in sheet "Responses" only
        c = by[ym]
        zoho_n = c['zoho'] if ym in zmonths else None
        month_rows.append([name, f'{ym[:4]}-{ym[4:]}', zoho_n if zoho_n is not None else 'not fetched', c['db'], c['today'], c['today'],
                           c['would'], c['today'] + c['would'],
                           (zoho_n - (c['today'] + c['would'])) if zoho_n is not None else ''])
    # every month by count: Zoho vs staging vs prod; the difference explained
    sm, pm, um = collections.Counter(), collections.Counter(), collections.Counter()
    for r in stg:
        if int(r['acc']) != acc or r['status'] == 'Deleted' or r['is_test'] == 't': continue
        m = r['started_local'][:4] + r['started_local'][5:7]; sm[m] += 1
        if r['link'] == 'unlinked' and r['sguid'].strip() not in inv: um[m] += 1
    for r in prodall:
        if int(r['acc']) == acc and r['status'] != 'Deleted': pm[r['started_local'][:4] + r['started_local'][5:7]] += 1
    for m in sorted(set(sm) | set(pm) | {mm for (aa, mm) in zmon if aa == a}):
        zn, sn, pn, wl = zmon.get((a, m), 0), sm[m], pm[m], by[m]['would'] if m in by else 0
        d = sn - zn
        if m >= STG_CUT: why = 'Staging copy ends mid Sep 2026: compare with prod (' + str(pn) + ')'
        elif d == 0: why = 'match'
        elif d == um[m] + (0 if m in zmonths else 0) and d > 0: why = f'{d} unlinked response(s) without an invite (no sguid / test / invite missing): Zoho\'s patient join drops them'
        elif d < 0 and pn - zn == 0: why = f'{-d} response(s) reached prod after the staging copy was made (prod {pn} = Zoho)'
        elif d < 0 and pn - zn == um[m]: why = f'{pn - sn} response(s) reached prod after the staging copy; {um[m]} unlinked without an invite'
        else: why = 'see sheet "Responses"'
        if m in zmonths:
            idc = 'identical by id once the legacy responses are counted (sheet "Responses")'
        elif (a, m) in zsum:
            ours = checksum(stg if m < STG_CUT else prodall, acc, m)
            idc = 'identical' if ours == zsum[(a, m)] else (
                'staging lacks the 7 late responses; prod identical' if checksum(prodall, acc, m) == zsum[(a, m)] else
                'Zoho not refreshed yet (newest responses)' if m >= '202611' else 'DIFFERENT: see Ana')
        else:
            idc = ''
        all_rows.append([name, f'{m[:4]}-{m[4:]}', zn, sn, pn, d, wl, why, idc])
    # what the load added (staging batch), by status source
    li = [r for r in load if r['row_kind'] == 'legacy_invite']
    src = collections.Counter(r['status_source'] for r in li); st = collections.Counter(r['est_status'] for r in li)
    ans = sum(r['has_response'] == 'true' for r in li); dl = st['DELIVERED']
    load_rows.append([name, batch, len(li), dl, f'{100 * dl / len(li):.1f}%', ans, f'{100 * ans / dl:.1f}%', 0,
                      ', '.join(f'{k} {v}' for k, v in sorted(src.items())),
                      ', '.join(f'{k} {v}' for k, v in sorted(st.items(), key=lambda t: -t[1])),
                      f"{min(r['est_sent_at'] for r in li)[:16]} – {max(r['est_sent_at'] for r in li)[:16]} UTC"])
    for r in li:
        if r['status_source'] == 'corrected':
            rid = next((k for k, u in unl.items() if u['sguid'].strip() == r['legacy_sguid'] and u['status'] != 'Deleted'), '')
            corrected.append([name, r['legacy_sguid'], r['raw_status'], 'DELIVERED', int(rid) if rid else '', ''])
    for r in load:
        if r['row_kind'] == 'legacy_raw':
            repeated.append([name, int(r['row_no']) + 1, r['raw_id'].strip(), r['raw_visit_date'][:10], r['raw_status'] or '(empty)',
                             'yes' if r['phone_clean'] else 'no', 'no', ''])
        if a == 'kvaternik' and r['raw_year_of_birth'].strip() and not r['raw_year_of_birth'].strip().isdigit():
            other.append([name, 'O6', int(r['row_no']) + 1, r['raw_id'].strip(), 'Shifted columns: year_of_birth "' + r['raw_year_of_birth'] + '", a date in language_code. Loaded with year of birth empty', ''])
        if a == 'opticalexpress' and r['row_kind'] == 'legacy_invite' and not r['legacy_sguid'].isdigit():
            other.append([name, 'O7', int(r['row_no']) + 1, '(text id)', 'Test row in the clinic file (text id; its only response is Deleted). Loaded as an invite, as the file says', ''])
        if a == 'opticalexpress' and r['row_kind'] == 'legacy_visit':
            other.append([name, '-', int(r['row_no']) + 1, r['raw_id'].strip(), 'No usable phone and no response: loaded as a visit without invite', ''])

wb = Workbook(); wb.remove(wb.active)
readme = [
    ['What this is', 'Legacy history of Kvaternik, Poliklinika Mazalin and Optical Express, loaded on EU staging on 6 Nov 2026 (Linear DEV-232). Please answer the yellow cells in "Checklist" and the decision sheets.'],
    ['Append only', 'The load ONLY ADDS rows: legacy Patients, Patient Visits and survey invites (Visit Msgs). Nothing that already existed was changed. The legacy Survey Responses are NOT linked to the new invites (Ana, 6 Nov 2026). That is the main reason Clinicdash and Zoho differ for the legacy months. Question O1 decides it.'],
    ['Real vs estimated', 'REAL: Survey Responses, scores, dates started, SMS delivery status from the clinic files, visit dates (Mazalin, part of Optical), Patients. ESTIMATED (orange cells): send dates (all three), Optical delivery status where the file is empty and no response proves it (1,078 invites, 88.2% delivered = the platform rate). CORRECTED: 36 answered invites whose file status was not delivered are set to DELIVERED (sheet "Corrected statuses").'],
    ['Data cut-off', 'Staging (where the load is): copy of prod from mid Sep 2026, loads of 6 Nov 2026 (batches Kvaternik 13097, Mazalin 13095, Optical Express 13099). Prod replica, Alchemer, Zoho and the clinic files: 6 Nov 2026. Months from Sep 2026 on are newer than the staging copy.'],
    ['How we compared', 'Alchemer is the source of truth: its Complete/Partial totals match staging exactly for all three Accounts (sheet "Alchemer vs DB"; one Mazalin exception, B1). Zoho vs staging: by response id for the legacy months (sheet "Responses"); for the newer months by a checksum of the response ids per month (sheet "All months", last column). Every difference has an explanation.'],
    ['Definitions', 'Months by "Time Started" (Zagreb), as Clinicdash NPS. "Clinicdash today" = responses linked to an invite and with a score. "If linked" = today + the legacy responses the load would link if ops say yes. Response rate = responses / delivered.'],
    ['Patient data', 'This workbook has ids only (Alchemer response id, legacy invite id, clinic file line). If you need names for a decision, ask Ana for a restricted file.'],
]
sheet(wb, 'Read me', ['Topic', 'Text'], readme, [22, 140])
checklist = [
    ['A1', 'All three', 'Link the legacy Survey Responses to the legacy invites? Kvaternik 132, Mazalin 437, Optical 634 (sheet "Responses", label WOULD_LINK). Today they are not linked (append only). If yes, Clinicdash shows them in the month they were started, exactly as Zoho does (sheet "Legacy months": 0 difference in all 30 months), and the legacy response rate becomes 19.0% / 18.2% / 17.4% (estimated; platform 21.4% / 19.0% / 17.5%).', ''],
    ['A2', 'Optical Express', '56 legacy ids appear twice in the clinic file (113 rows), each time with a different phone, none answered. They are NOT loaded (kept only for the export back). Keep one, both or none? (sheet "Repeated ids")', ''],
    ['A3', 'Optical Express', '32 responses carry a legacy id that is not in the clinic file (15 of them are from Jan 2025, which is why Zoho shows no responses that month; most others Nov 2024 – Feb 2025). Does the clinic have those rows? Until then they stay unlinked (sheet "Missing invites").', ''],
    ['A4', 'Mazalin, Optical', '36 answered invites had a non-delivered SMS status in the file (Mazalin 15, Optical 21). We set them to DELIVERED because a response proves delivery. OK? (sheet "Corrected statuses")', ''],
    ['A5', 'All three', 'Send dates are estimated (Kvaternik one bulk send 21 Feb 2024; Mazalin 12 Feb and 27 Mar 2024; Optical from the id order, which is weaker than usual: 0.933, bar 0.95; 299 Optical sends set to 2 minutes before the real response). Optical delivery is estimated for 1,078 invites with an empty status (88.2%). Confirm no real send dates exist and that the estimates may be shown, labelled.', ''],
    ['A6', 'Kvaternik, Optical', 'Kvaternik: 1 clinic row has shifted columns, loaded with year of birth empty. Optical: 1 clinic row is a test, loaded as an invite. OK, or fix/remove? (sheet "Other rows")', ''],
    ['B1', 'Poliklinika Mazalin', 'Not caused by the load: 1 response submitted 16-20 Dec 2024 is Complete in Alchemer but Partial in our DB (Alchemer 3,853 Complete / 1,311 Partial before 1 Sep 2026; DB 3,852 / 1,312). Acknowledge; devs resync its status.', ''],
    ['B2', 'All three', 'Not caused by the load: responses without an invite (no sguid, test links) are in our DB but not in Zoho or Clinicdash, in a few platform months (sheet "All months", explanation column). Nothing to do; acknowledge.', ''],
    ['C1', 'All three', 'Sign-off per Account: "Legacy data OK for production" (with the answers above).', ''],
]
ws = sheet(wb, 'Checklist', ['#', 'Account', 'Question', 'Answer (ops)'], checklist, [6, 18, 110, 40], input_cols=(4,))
sheet(wb, 'Load summary', ['Account', 'Staging batch', 'Legacy invites', 'Delivered', 'Delivery rate', 'Real responses on these invites',
                           'Response rate if linked (estimated)', 'Linked now', 'Status source', 'Statuses', 'Send dates (estimated)'],
      load_rows, [20, 10, 10, 10, 10, 14, 14, 8, 40, 50, 36], est_cols=(7, 11))
sheet(wb, 'All months', ['Account', 'Month started', 'Zoho responses', 'Staging responses (not Deleted, not test)', 'Prod responses (6 Nov 2026)',
                         'Staging − Zoho', 'Legacy responses on staging, not linked', 'Explanation',
                         'Same response ids as Zoho? (responses with an invite; count, sum, min and max of ids)'], all_rows, [20, 12, 12, 16, 14, 10, 14, 70, 34])
sheet(wb, 'Legacy months', ['Account', 'Month started', 'Zoho responses', 'DB responses (not Deleted, not test)', 'Clinicdash today',
                      'Clinicdash after this load', 'Legacy responses, not linked', 'Clinicdash if linked', 'Zoho − if linked'],
      month_rows, [20, 12, 12, 14, 12, 14, 14, 14, 12])
ws = sheet(wb, 'Responses', ['Account', 'Alchemer response id', 'Status', 'Started (Zagreb)', 'Score', 'sguid (legacy invite id)',
                             'Linked today', 'In Zoho', 'In Clinicdash', 'Label', 'Where it shows', 'Why', 'What ops do'],
           resp_rows, [18, 10, 10, 18, 7, 22, 9, 14, 12, 15, 34, 60, 50])
sheet(wb, 'Corrected statuses', ['Account', 'Legacy invite id (sguid)', 'Status in the file', 'Status loaded', 'Alchemer response id', 'OK? (ops)'],
      corrected, [20, 24, 16, 14, 12, 20], input_cols=(6,))
ws = sheet(wb, 'Repeated ids', ['Account', 'Clinic file line', 'Legacy id', 'Visit date', 'SMS status', 'Has phone', 'Has a response', 'Keep? (ops)'],
           repeated, [18, 10, 14, 12, 14, 9, 10, 16], input_cols=(8,))
dropdown(ws, 'H', ['keep', 'drop'], len(repeated))
sheet(wb, 'Missing invites', ['Account', 'Alchemer response id', 'Status', 'Started', 'sguid', 'In Zoho', 'Clinic has the row? (ops)'],
      missing, [18, 10, 10, 22, 14, 12, 24], input_cols=(7,))
sheet(wb, 'Other rows', ['Account', '#', 'Clinic file line', 'Legacy id', 'What', 'Answer (ops)'], other, [18, 5, 10, 38, 90, 24], input_cols=(6,))
alc = [[ACC[r['account']][0], r['period'], r['status'], int(r['alchemer']), int(r['stg']), int(r['prod']), r['result']] for r in rd(f'{IN}/alchemer_counts.csv')]
sheet(wb, 'Alchemer vs DB', ['Account', 'Period (date submitted)', 'Status', 'Alchemer (source of truth)', 'Staging', 'Prod replica', 'Result'],
      alc, [20, 40, 10, 12, 10, 10, 70])
wb.save(OUT)
c = collections.Counter((r[0], r[9]) for r in resp_rows)
print('responses', len(resp_rows), dict(c)); print('months', len(month_rows), '| corrected', len(corrected), '| repeated', len(repeated),
      '| missing', len(missing), '| other', len(other))
