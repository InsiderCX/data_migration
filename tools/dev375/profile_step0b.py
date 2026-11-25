"""Step 0 follow-up: date formats, duplicates. Aggregates and ids only.
usage: python3 -I profile_step0b.py <csv> <col> [<col> ...]   -> date format + range per column
       python3 -I profile_step0b.py --dups <responses csv>     -> duplicate Response ID analysis
       python3 -I profile_step0b.py --iddups <patient csv>      -> duplicate patient-file ids
"""
import csv, io, re, sys, collections
from datetime import datetime

FMTS = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y',
        '%m/%d/%Y %H:%M:%S', '%m/%d/%Y %H:%M', '%m/%d/%Y', '%d.%m.%Y %H:%M:%S', '%d.%m.%Y %H:%M', '%d.%m.%Y', '%d.%m.%Y.',
        '%d %b, %Y %H:%M', '%d %b, %Y, %H:%M', '%d %b, %Y', '%d %b %Y %H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S%z', '%Y-%m-%d %H:%M:%S.%f%z']

def read(path):
    t = open(path, encoding='utf-8-sig').read()
    rows = list(csv.reader(io.StringIO(t, newline='')))
    return rows[0], rows[1:]

def mask(v):
    return re.sub(r'[A-Za-z]', 'a', re.sub(r'\d', '9', v))

def dates(path, cols):
    hdr, body = read(path)
    for c in cols:
        i = hdr.index(c)
        vals = [r[i].strip() for r in body if r[i].strip()]
        masks = collections.Counter(mask(v) for v in vals)
        ok = {}
        for f in FMTS:
            n = 0; parsed = []
            for v in vals:
                try: parsed.append(datetime.strptime(v, f)); n += 1
                except ValueError: pass
            if n: ok[f] = (n, min(parsed), max(parsed))
        print(f'{path.split("/")[-1]} :: {c}: {len(vals)} filled; shapes {masks.most_common(4)}')
        for f, (n, a, b) in sorted(ok.items(), key=lambda x: -x[1][0])[:3]:
            print(f'     {f!r:26} parses {n:>7}  {a:%Y-%m-%d} .. {b:%Y-%m-%d}')

def dups(path):
    hdr, body = read(path)
    g = lambda r, h: r[hdr.index(h)].strip() if h in hdr else ''
    c = collections.Counter(g(r, 'Response ID') for r in body)
    d = {k for k, n in c.items() if n > 1}
    rows = [r for r in body if g(r, 'Response ID') in d]
    print(f'{path.split("/")[-1]}: {len(d)} duplicated Response IDs over {len(rows)} rows; max copies {max(c.values())}')
    by = collections.defaultdict(list)
    for r in rows: by[g(r, 'Response ID')].append(r)
    same_all = sum(1 for k, rs in by.items() if all(x == rs[0] for x in rs))
    same_sguid = sum(1 for k, rs in by.items() if len({g(x, 'URL Variable: sguid') for x in rs}) == 1)
    same_start = sum(1 for k, rs in by.items() if len({g(x, 'Time Started') for x in rs}) == 1)
    print(f'   identical rows: {same_all}; same sguid: {same_sguid}; same Time Started: {same_start}')
    # which columns are filled differ between copies -> hints at a survey block
    hint = [h for h in hdr if re.search(r'survey|anketa|form', h, re.I)]
    print('   survey-like columns:', hint)
    print('   first 3 duplicated Response IDs (ids only):', sorted(d, key=lambda x: int(x) if x.isdigit() else 0)[:3])
    print('   Response ID range:', min(int(k) for k in c if k.isdigit()), '..', max(int(k) for k in c if k.isdigit()))

def iddups(path):
    hdr, body = read(path)
    i = hdr.index('id')
    c = collections.Counter(r[i].strip() for r in body)
    d = {k: n for k, n in c.items() if n > 1}
    print(f'{path.split("/")[-1]}: duplicated ids {len(d)}; shapes', collections.Counter(mask(k)[:12] for k in d))
    rows = [r for r in body if r[i].strip() in d]
    by = collections.defaultdict(list)
    for r in rows: by[r[i].strip()].append(r)
    print('   identical duplicate rows:', sum(1 for rs in by.values() if all(x == rs[0] for x in rs)), 'of', len(by))
    print('   test-like ids:', sum(1 for k in c if 'test' in k.lower()))

if __name__ == '__main__':
    if sys.argv[1] == '--dups': dups(sys.argv[2])
    elif sys.argv[1] == '--iddups': iddups(sys.argv[2])
    else: dates(sys.argv[1], sys.argv[2:])
