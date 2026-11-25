"""Step 0 profile: aggregates only, no patient values printed.
usage: python3 -I profile_step0.py <patient csv> <responses csv> <id column in patient file>
"""
import csv, re, sys, collections

CURRENT = ['id', 'first_name', 'last_name', 'source_id', 'phone', 'lead_source', 'year_of_birth',
           'gender_code', 'country_code', 'language_code', 'visit_date', 'procedure', 'comment',
           'doctor', 'status', 'sent_at']
SAFE_VALUES = {'lead_source', 'gender_code', 'country_code', 'language_code', 'status', 'location',
               'location_id', 'Spol', 'Spol2', 'Izvor', 'Jezik', 'R', 'Status', 'Language'}
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)

def load(path):
    raw = open(path, 'rb').read()
    info = {'bytes': len(raw), 'bom': raw.startswith(b'\xef\xbb\xbf'), 'crlf': b'\r\n' in raw}
    try:
        text = raw.decode('utf-8-sig'); info['enc'] = 'utf-8'
    except UnicodeDecodeError as e:
        text = raw.decode('cp1250'); info['enc'] = f'NOT utf-8 ({e.start})'
    import io
    rows = list(csv.reader(io.StringIO(text, newline='')))
    hdr, body = rows[0], rows[1:]
    info['rows'] = len(body)
    info['ragged'] = sum(1 for r in body if len(r) != len(hdr))
    info['multiline_cells'] = sum(1 for r in body for c in r if '\n' in c or '\r' in c)
    info['dup_header'] = [h for h, n in collections.Counter(hdr).items() if n > 1]
    return hdr, body, info

def shape(v):
    v = v.strip()
    if not v: return 'empty'
    if v.isdigit(): return 'numeric'
    if UUID.match(v): return 'uuid'
    if 'test' in v.lower(): return 'test'
    return 'other'

def profile_patients(path, idcol):
    hdr, body, info = load(path)
    print(f'## patient file {path.split("/")[-1]}')
    print('  ', info)
    print('   missing vs current format:', [c for c in CURRENT if c not in hdr])
    print('   extra vs current format:', [c for c in hdr if c not in CURRENT])
    for i, h in enumerate(hdr):
        vals = [r[i] if i < len(r) else '' for r in body]
        filled = sum(1 for v in vals if v.strip())
        dist = len(set(v.strip() for v in vals if v.strip()))
        line = f'   {h!r:28} filled {filled:>7} ({100*filled/max(len(vals),1):5.1f}%) distinct {dist:>7}'
        if h in SAFE_VALUES and dist <= 15:
            line += '  ' + str(collections.Counter(v.strip() for v in vals).most_common(15))
        if h in ('visit_date', 'sent_at') and filled:
            d = sorted(v.strip()[:10] for v in vals if v.strip())
            line += f'  range {d[0]} .. {d[-1]}'
        if h in ('Dob', 'year_of_birth'):
            nums = [int(v) for v in vals if v.strip().isdigit()]
            if nums: line += f'  numeric {len(nums)} min {min(nums)} max {max(nums)}'
        print(line)
    j = hdr.index(idcol)
    ids = [r[j].strip() for r in body]
    c = collections.Counter(ids)
    print(f'   id column {idcol!r}: shapes {dict(collections.Counter(map(shape, ids)))}, '
          f'duplicated ids {sum(1 for k, n in c.items() if k and n > 1)} (rows {sum(n for k, n in c.items() if k and n > 1)})')
    return set(k for k in ids if k)

def profile_responses(path, ids):
    hdr, body, info = load(path)
    print(f'## responses {path.split("/")[-1]}')
    print('  ', info, 'columns', len(hdr))
    g = lambda r, h: r[hdr.index(h)].strip() if h in hdr and hdr.index(h) < len(r) else ''
    rid = [g(r, 'Response ID') for r in body]
    c = collections.Counter(rid)
    print('   Response ID duplicates:', sum(1 for k, n in c.items() if n > 1), 'empty:', sum(1 for k in rid if not k))
    print('   Status:', dict(collections.Counter(g(r, 'Status') for r in body)))
    if 'Language' in hdr: print('   Language:', collections.Counter(g(r, 'Language') for r in body).most_common(8))
    d = sorted(g(r, 'Time Started')[:10] for r in body if g(r, 'Time Started'))
    print('   Time Started range:', d[0] if d else None, '..', d[-1] if d else None)
    years = collections.Counter(x[:4] if re.match(r'\d{4}', x) else x[-4:] for x in d)
    print('   by year (raw prefix/suffix):', dict(sorted(years.items())))
    sg = [g(r, 'URL Variable: sguid') for r in body]
    print('   sguid shapes:', dict(collections.Counter(map(shape, sg))))
    num = [s for s in sg if s.isdigit()]
    print(f'   numeric sguid found in patient file ids: {sum(1 for s in num if s in ids)} of {len(num)}; '
          f'any sguid found: {sum(1 for s in sg if s and s in ids)} of {sum(1 for s in sg if s)}')
    for h in ('URL Variable: p', 'URL Variable: source', 'URL Variable: k', 'URL Variable: slanguage'):
        if h in hdr:
            v = [g(r, h) for r in body]
            print(f'   {h}: filled {sum(1 for x in v if x)}, distinct {len(set(v))}',
                  collections.Counter(v).most_common(6) if len(set(v)) <= 6 else '')

if __name__ == '__main__':
    ids = profile_patients(sys.argv[1], sys.argv[3])
    profile_responses(sys.argv[2], ids)
