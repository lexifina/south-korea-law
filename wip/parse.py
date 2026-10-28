"""Turn the cached law.go.kr Open API responses into corpus.json (scripts/gitlaw_common/SCHEMA.md).

Reads only .cache/ (written by fetch.py); no network. Deterministic: the same cache gives the same bytes.

Units, one file each:
  art-NNNN[-BB]           제N조[의B]: one line for the article line, then one per 항, 호 and 목
  structure               the 편/장/절/관 headings, in order, one per line
  buchik-YYYYMMDD-NNNNN   one 부칙 (supplementary provisions) per promulgated law, keyed by its date and number

Dates: every version is law.go.kr's own version in force from its 시행일자 (efYd). Credits: every unit that
differs from the version before is credited to the law that version records (공포번호): the act's own
amendment, or the other law (타법개정) whose 부칙 amended it.
"""
import hashlib, json, os, re, sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch  # noqa: E402  (URL builders and cache paths only; parse never fetches)

RETRIEVED = '2026-10-28'

# Editorial notes law.go.kr adds to the consolidated text; they are not words of the law.
DATE = r'\d{4}\s*\.\s*\d{1,2}\s*\.\s*\d{1,2}\s*\.?'
INLINE = re.compile(r'\s*<(?:개정|신설|전문개정|본조신설|제목개정|타법개정|종전[^<>]*?)?\s*' + DATE + r'(?:\s*,\s*' + DATE + r')*\s*>')
INLINE2 = re.compile(r'\s*<(?:개정|신설|전문개정|본조신설|제목개정)\s[^<>]*>')
BRACKET_LINE = re.compile(r'^\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]$')
BRACKET_INLINE = re.compile(r'\s*\[(?:전문개정|본조신설|제목개정|종전|시행일|단순위헌|헌법불합치|한정위헌|한정합헌|위헌)[^\[\]]*\]')
ANN = re.compile(r'<(?:개정|신설|전문개정|본조신설|제목개정|타법개정)?[^<>]*?>|\[(?:전문개정|본조신설|제목개정|종전|시행일)[^\[\]]*\]')
ANN_DATE = re.compile(r'(\d{4})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})')


def ann_dates(raw):
    """Promulgation dates named in law.go.kr's amendment notes (<개정 2011.3.7>, [전문개정 ...], [본조신설 ...])."""
    out = set()
    for m in ANN.finditer(raw or ''):
        for y, mo, d in ANN_DATE.findall(m.group(0)):
            out.add(f'{y}{int(mo):02d}{int(d):02d}')
    return out


def squash(text):
    """Text with all spacing removed: law.go.kr re-spaced old texts (띄어쓰기) without any law."""
    return re.sub(r'\s+', '', text or '').replace('·', 'ㆍ').replace('・', 'ㆍ')


def norm_line(s):
    s = s.replace(' ', ' ').replace('　', ' ').replace('\t', ' ')
    s = s.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    s = INLINE.sub('', s)
    s = INLINE2.sub('', s)
    s = BRACKET_INLINE.sub('', s)
    s = re.sub(r' {2,}', ' ', s).strip()
    if BRACKET_LINE.match(s):
        return ''
    return s


def lines_of(text):
    out = []
    for raw in (text or '').split('\n'):
        s = norm_line(raw)
        if s:
            out.append(s)
    return out


def t(el, tag):
    x = el.find(tag)
    return (x.text or '') if x is not None else ''


def art_key(no, branch):
    k = f'art-{int(no):04d}'
    if branch and int(branch):
        k += f'-{int(branch):02d}'
    return k


def art_label(no, branch):
    return f'제{int(no)}조' + (f'의{int(branch)}' if branch and int(branch) else '')


def parse_version(xml_bytes):
    root = ET.fromstring(xml_bytes)
    info = root.find('기본정보')
    meta = {k: t(info, k) for k in ('법령ID', '공포일자', '공포번호', '시행일자', '제개정구분', '법령명_한글')}
    meta['법종구분'] = t(info, '법종구분')
    units, headings, changed_flag, ann = {}, [], set(), {}
    for a in root.iter('조문단위'):
        kind = t(a, '조문여부')
        if kind == '전문':
            headings += lines_of(t(a, '조문내용'))
            ann.setdefault('structure', set()).update(ann_dates(t(a, '조문내용')))
            continue
        key = art_key(t(a, '조문번호'), t(a, '조문가지번호'))
        lines = lines_of(t(a, '조문내용'))
        for h in a.findall('항'):
            lines += lines_of(t(h, '항내용'))
            for ho in h.findall('호'):
                lines += lines_of(t(ho, '호내용'))
                for mok in ho.findall('목'):
                    lines += lines_of(t(mok, '목내용'))
        if key in units:
            raise ValueError(f'duplicate unit {key}')
        units[key] = {'label': art_label(t(a, '조문번호'), t(a, '조문가지번호')), 'kind': 'art', 'text': '\n'.join(lines) + '\n'}
        ann[key] = ann_dates(''.join(a.itertext()))
        if t(a, '조문변경여부') == 'Y':
            changed_flag.add(key)
    if headings:
        units['structure'] = {'label': '편장절관 (headings)', 'kind': 'heading', 'text': '\n'.join(headings) + '\n'}
    for b in root.iter('부칙단위'):
        d, n = t(b, '부칙공포일자'), t(b, '부칙공포번호')
        key = f'buchik-{d}-{int(n):05d}' if n.strip().isdigit() else f'buchik-{d}'
        lines = lines_of(t(b, '부칙내용'))
        base = key
        i = 2
        while key in units:  # one law with two 부칙 blocks
            key = f'{base}-{i}'
            i += 1
        units[key] = {'label': f'부칙 ({d[:4]}.{int(d[4:6])}.{int(d[6:])}, 제{int(n) if n.strip().isdigit() else n}호)', 'kind': 'transitional',
                      'text': '\n'.join(lines) + '\n'}
    amend_text = lines_of(t(root.find('개정문'), '개정문내용') if root.find('개정문') is not None else '')
    return meta, units, changed_flag, amend_text, ann


def iso(d):
    return f'{d[:4]}-{d[4:6]}-{d[6:]}'


def law_title(amend_lines, meta, act_name):
    """The promulgated law's own title: the first line after '⊙법률 제N호' in the 개정문."""
    for i, s in enumerate(amend_lines):
        if s.startswith('⊙') and i + 1 < len(amend_lines):
            nxt = amend_lines[i + 1]
            if nxt and not nxt.startswith('['):
                return nxt
    kind = meta['제개정구분']
    return f'{act_name} {kind}' if kind else act_name


def law_key(meta):
    no = int(meta['공포번호'])
    if meta['법종구분'] == '헌법':
        return f'heonbeop-{no}', f'헌법 제{no}호'
    return f'law-{no}', f'법률 제{no}호'




def cached_listing(cfg):
    """The act's versions from the cached eflaw search pages, or None if not fetched."""
    listing, page = [], 1
    while True:
        p = fetch.path_for(fetch.search_url(cfg['query'], page))
        if not os.path.exists(p):
            return None
        d = json.load(open(p, encoding='utf-8'))['LawSearch']
        ls = d.get('law') or []
        ls = [ls] if isinstance(ls, dict) else ls
        listing += [x for x in ls if x['법령ID'] == cfg['id']]
        if page * 100 >= int(d['totalCnt']):
            return listing
        page += 1


def build_act(cfg, laws, log):
    listing = cached_listing(cfg)
    if not listing:
        return None
    recs = []
    for x in sorted({(x['시행일자'], x['공포일자'], int(x['공포번호']), x['법령일련번호']) for x in listing}):
        efyd, pd, pn, mst = x
        url = fetch.version_url(mst, efyd)
        p = fetch.path_for(url)
        if not os.path.exists(p):
            log.append({'act': cfg['slug'], 'missing': f'{mst}@{efyd}'})
            continue
        raw = open(p, 'rb').read()
        meta, units, flagged, amend, ann = parse_version(raw)
        key, label = law_key(meta)
        if key not in laws:
            laws[key] = {'label': label, 'title': law_title(amend, meta, cfg['name']), 'kind': 'law',
                         'enacted': iso(meta['공포일자']), 'published': iso(meta['공포일자']),
                         'url': f'https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq={mst}',
                         'temporary_until': None, 'restores': None, 'note': None}
        recs.append({'efyd': efyd, 'P': (pd, pn), 'mst': mst, 'url': url, 'sha': hashlib.sha256(raw).hexdigest(),
                     'units': units, 'ann': ann, 'law': key, 'pd': pd})
    groups = {}
    for r in recs:
        groups.setdefault(r['efyd'], []).append(r)
    versions, state, maxP, first = [], None, None, None
    history = {}  # unit key -> list of texts it has had, to spot reversions
    for efyd in sorted(groups):
        grp = sorted(groups[efyd], key=lambda r: r['P'])
        rep = grp[-1]
        note = None
        if state is None:
            new = dict(rep['units'])
            first = rep
        elif rep['P'] >= maxP:
            new = dict(rep['units'])
        else:
            # Promulgated before a law already in force: law.go.kr composed this version from the text as it stood
            # when its law was promulgated, so it lacks later-promulgated changes. Apply only this law's own changes.
            cands = [r for r in recs if (r['P'], r['efyd']) < (rep['P'], rep['efyd']) and r['efyd'] <= efyd]
            base = max(cands, key=lambda r: (r['P'], r['efyd']))
            delta = sorted(k for k in set(rep['units']) | set(base['units']) if rep['units'].get(k) != base['units'].get(k))
            new = dict(state)
            conflicts = []
            for k in delta:
                if state.get(k) != base['units'].get(k) and squash((state.get(k) or {}).get('text')) != squash((base['units'].get(k) or {}).get('text')):
                    conflicts.append(k)
                if k in rep['units']:
                    new[k] = rep['units'][k]
                else:
                    new.pop(k, None)
            note = (f"law.go.kr's text for this version was composed before laws promulgated after "
                    f"{iso(rep['pd'])} took effect; only the changes it makes to the text as of {iso(base['efyd'])} "
                    f"({laws[base['law']]['label']}) are applied to the text in force the day before.")
            log.append({'act': cfg['slug'], 'from': iso(efyd), 'out_of_order': rep['law'], 'base': f"{base['law']}@{base['efyd']}",
                        'delta': len(delta), 'conflicts': conflicts})
        maxP = rep['P'] if maxP is None else max(maxP, rep['P'])
        if state is None:
            v = {'from': iso(efyd), 'source_url': rep['url'], 'sha256': rep['sha'], 'units': new, 'credits': {}}
        else:
            changed = sorted(k for k in set(new) | set(state) if new.get(k) != state.get(k))
            if not changed:
                log.append({'act': cfg['slug'], 'from': iso(efyd), 'no_change': [r['law'] for r in grp]})
                state = new
                continue
            credits, spacing, uncredited, reverted = {}, [], [], []
            glaws = [r['law'] for r in grp]
            for k in changed:
                o, n = state.get(k), new.get(k)
                if o and n and squash(o['text']) == squash(n['text']):
                    spacing.append(k)
                    continue
                if n and k in history and n['text'] in history[k][:-1]:
                    reverted.append(k)
                if k.startswith('buchik-'):
                    no = k.split('-')[2]
                    named = [l for l in glaws if l.split('-')[-1] == str(int(no))]
                    if named:
                        credits[k] = named
                        continue
                if len(set(glaws)) == 1:
                    credits[k] = [glaws[0]]
                else:
                    dates = rep['ann'].get(k, set())
                    named = sorted({r['law'] for r in grp if r['pd'] in dates}, key=lambda l: glaws.index(l))
                    if named:
                        credits[k] = named
                    else:
                        uncredited.append(k)
            v = {'from': iso(efyd), 'source_url': rep['url'], 'sha256': rep['sha'],
                 'changes': {k: new.get(k) for k in changed}, 'credits': credits}
            if spacing:
                n0 = (f'{len(spacing)} provision(s) differ from the version before only in spacing (띄어쓰기), '
                      'which law.go.kr revised in its own database; no law is credited for that.')
                note = (note + ' ' + n0) if note else n0
            log.append({'act': cfg['slug'], 'from': iso(efyd), 'laws': glaws, 'changed': len(changed), 'spacing': len(spacing),
                        'uncredited': uncredited, 'reverted': reverted})
        if note:
            v['note'] = note
        versions.append(v)
        for k, u in new.items():
            h = history.setdefault(k, [])
            if not h or h[-1] != u['text']:
                h.append(u['text'])
        state = new
    enacted = laws[first['law']] and first['law'] and parse_kind(first) == '제정'
    return {'slug': cfg['slug'], 'short': cfg.get('short', cfg['name']), 'title': cfg['name'],
            'url': 'https://www.law.go.kr/법령/' + cfg['name'].replace(' ', ''),
            'first_law': first['law'] if enacted else None,
            'earlier_laws': [] if enacted else [first['law'
