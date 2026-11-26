"""Step 1 discovery (playbook §1.2-1.4). Aggregates and ids only.
usage: python3 -I discovery.py <account dir> <patient csv> <id col> <vm ids json-tool-result> <responses csv>
Writes data/db_visit_msg_ids_2026-11-25.csv.
"""
import ast, csv, io, json, re, sys, collections
from datetime import datetime

acc, pfile, idcol, vmjson, rfile = sys.argv[1:6]
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
TEST = re.compile(r"test|^t+1?t*s+|^1111\d{8,}$|^111222666$|^40275999993$", re.I)  # same as builder

def read(p):
    rows = list(csv.reader(io.StringIO(open(p, encoding='utf-8-sig').read(), newline='')))
    return rows[0], rows[1:]

def shape(v):
    if not v: return 'empty'
    if TEST.search(v): return 'test'
    if v.isdigit(): return 'numeric'
    if UUID.match(v): return 'uuid'
    return 'text'

vm = {r['visit_msg_id'] for r in ast.literal_eval(json.load(open(vmjson))['result'][0]['text'])}
with open(f'{acc}/data/db_visit_msg_ids_2026-11-25.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['visit_msg_id']); [w.writerow([x]) for x in sorted(vm)]

h, body = read(pfile)
ids = [r[h.index(idcol)].strip() for r in body]
idc = collections.Counter(ids)
on_platform = [x for x in ids if x in vm]
legacy = [x for x in ids if x not in vm]
print(f'== {acc}')
print(f'visit_msg on prod {len(vm)}; file rows {len(ids)}: on platform (id = visit_msg.id) {len(on_platform)}, legacy {len(legacy)}'
      f' (legacy shapes {dict(collections.Counter(map(shape, legacy)))}); platform Visit Msgs not in file {len(vm - set(ids))}')
if 'sent_at' in h:
    si = h.index('sent_at')
    print('  legacy rows with sent_at filled:', sum(1 for r in body if r[h.index(idcol)].strip() not in vm and r[si].strip()),
          '| platform rows without sent_at:', sum(1 for r in body if r[h.index(idcol)].strip() in vm and not r[si].strip()))
if 'visit_date' in h:
    vi = h.index('visit_date'); ys = collections.Counter()
    for r in body:
        if r[h.index(idcol)].strip() not in vm:
            v = r[vi].strip()
            ys[v[6:10] + '-' + v[3:5] if v else 'no date'] += 1
    print('  legacy rows by visit month:', dict(sorted(ys.items())))

ur = list(csv.DictReader(open(f'{acc}/data/db_unlinked_responses_2026-11-25.csv')))
leg_unique = {x for x in legacy if idc[x] == 1}
leg_rep = {x for x in legacy if idc[x] > 1}
grp = collections.Counter(); yr = collections.Counter()
for r in ur:
    s = r['sguid'].strip(); st = r['status']
    k = shape(s)
    if r['is_test'] == 'True': k = 'test (flag)'
    elif k in ('numeric', 'uuid'):
        if s in leg_unique: k += ' = legacy id'
        elif s in leg_rep: k += ' = repeated legacy id'
        elif s in vm: k += ' = platform Visit Msg (should be linked!)'
        else: k += ' not in file'
    grp[(k, 'Deleted' if st == 'Deleted' else 'live')] += 1
    yr[r['started_utc'][:4]] += 1
print(f'unlinked responses {len(ur)} by year {dict(sorted(yr.items()))}')
for (k, d), n in sorted(grp.items()):
    print(f'  {k:45} {d:8} {n}')
# one-to-one: legacy ids with more than one live unlinked response
live = collections.Counter(r['sguid'].strip() for r in ur if r['status'] != 'Deleted' and r['sguid'].strip() in leg_unique)
print('  legacy ids answered more than once (live):', sum(1 for n in live.values() if n > 1))

# response file vs DB
rh, rb = read(rfile)
keys = {(r[rh.index('Response ID')].strip(), r[rh.index('URL Variable: sguid')].strip()) for r in rb}
dbk = {(r['alchemer_response_id'], r['sguid'].strip()) for r in ur}
print(f'  unlinked DB responses missing from the survey export: {len(dbk - keys)} '
      f'(by status {dict(collections.Counter(r["status"] for r in ur if (r["alchemer_response_id"], r["sguid"].strip()) not in keys))})')
