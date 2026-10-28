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
CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'


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
    units, headings, changed_flag = {}, [], set()
    for a in root.iter('조문단위'):
        kind = t(a, '조문여부')
        if kind == '전문':
            headings += lines_of(t(a, '조문내용'))
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
    return meta, units, changed_flag, amend_text


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


def main():
    acts_cfg = json.load(open(os.path.join(HERE, 'acts.json'), encoding='utf-8'))
    laws, acts, decisions_extra, log = {}, [], [], []
    requests = 0
    reqlog = os.path.join(fetch.CACHE, 'requests.jsonl')
    if os.path.exists(reqlog):
        requests = sum(1 for _ in open(reqlog, encoding='utf-8'))
    for cfg in acts_cfg:
        # the listing as cached: every page of the eflaw search for this act's name
        listing, page = [], 1
        while True:
            p = fetch.path_for(fetch.search_url(cfg['query'], page))
            if not os.path.exists(p):
                listing = None
                break
            d = json.load(open(p, encoding='utf-8'))['LawSearch']
            ls = d.get('law') or []
            ls = [ls] if isinstance(ls, dict) else ls
            listing += [x for x in ls if x['법령ID'] == cfg['id']]
            if page * 100 >= int(d['totalCnt']):
                break
            page += 1
        if not listing:
            print(f"{cfg['slug']}: not fetched, skipped", file=sys.stderr)
            continue
        jobs = sorted({(x['시행일자'], x['공포일자'], int(x['공포번호']), x['법령일련번호']) for x in listing})
        versions, prev_units, first_meta = [], None, None
        for efyd, _, _, mst in jobs:
            url = fetch.version_url(mst, efyd)
            p = fetch.path_for(url)
            if not os.path.exists(p):
                print(f"{cfg['slug']}: missing {mst}@{efyd}", file=sys.stderr)
                continue
            raw = open(p, 'rb').read()
            meta, units, flagged, amend = parse_version(raw)
            key, label = law_key(meta)
            title = law_title(amend, meta, cfg['name'])
            if key not in laws:
                laws[key] = {'label': label, 'title': title, 'kind': 'law', 'enacted': iso(meta['공포일자']),
                             'published': iso(meta['공포일자']),
                             'url': f'https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq={mst}&efYd={efyd}',
                             'temporary_until': None, 'restores': None, 'note': None}
            v = {'from': iso(efyd), 'source_url': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'units': units}
            if prev_units is None:
                first_meta = meta
                v['credits'] = {}
            else:
                diff = sorted(k for k in set(units) | set(prev_units) if units.get(k) != prev_units.get(k))
                v['credits'] = {k: [key] for k in diff}
                log.append({'act': cfg['slug'], 'from': iso(efyd), 'law': key, 'kind': meta['제개정구분'], 'changed': len(diff),
                            'flagged_not_changed': sorted(k for k in flagged if k in units and k not in diff and k.startswith('art')),
                            'changed_not_flagged': sorted(k for k in diff if k.startswith('art') and k not in flagged)})
                if not diff:
                    v['note'] = (f'law.go.kr records {label} as in force for this act from this day, '
                                 'but the text is the same as the version before (after removing editorial notes).')
                    v.pop('units')
            if versions and versions[-1]['from'] == v['from']:
                v['same_day'] = True
            versions.append(v)
            prev_units = units if 'units' in v else prev_units
        first_key = law_key(first_meta)[0]
        enacted = first_meta['제개정구분'] == '제정'
        acts.append({'slug': cfg['slug'], 'short': cfg.get('short', cfg['name']), 'title': cfg['name'],
                     'url': f"https://www.law.go.kr/법령/{cfg['name'].replace(' ', '')}",
                     'first_law': first_key if enacted else None,
                     'earlier_laws': [] if enacted else [first_key],
                     'versions': versions})
    corpus = {
        'country': {
            'code': 'KR', 'name': 'South Korea', 'slug': 'south-korea', 'lang': 'ko', 'tz': 'Asia/Seoul',
            'future_branch': 'future',
            'publisher': {'name': '법제처 국가법령정보센터 (National Law Information Center)', 'email': 'nlic@law.go.kr.invalid'},
            'default_in_force_rule': {
                'text': '대한민국헌법 제53조 제7항: 법률은 특별한 규정이 없는 한 공포한 날로부터 20일을 경과함으로써 효력을 발생한다 '
                        '(a law takes effect 20 days after promulgation unless it provides otherwise). '
                        'Every version here carries law.go.kr\'s own 시행일자 (in-force date), which already applies the rule or the law\'s own 부칙.',
                'source': 'https://www.law.go.kr/법령/대한민국헌법'},
            'licence_note': ('Statute text: not protected by copyright (저작권법 제7조 제1호). Source: 법제처 국가법령정보센터 '
                             '(www.law.go.kr), Open API (open.law.go.kr), Korea Open Government License (공공누리).'),
        },
        'sources': [{
            'name': '법제처 국가법령정보센터 Open API (National Law Information Center, Ministry of Government Legislation)',
            'url': 'https://www.law.go.kr/DRF/', 'retrieved': RETRIEVED, 'requests': requests,
            'licence': 'Statutes are not copyright works (저작권법 제7조); site content under 공공누리 (KOGL)',
            'notes': 'lawSearch.do?target=eflaw lists every version by 시행일자; lawService.do?target=eflaw&MST=&efYd=&type=XML gives each version\'s full text. OC=test.'}],
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': [
            'Every version is law.go.kr\'s own point-in-time text, one per (법령일련번호 MST, 시행일자) pair of the eflaw search, dated by its 시행일자 (in-force date), not the promulgation date (legalize-kr dates by promulgation).',
            'Where several laws take effect for one act on one day, each gets its own version on that day (same_day), ordered by promulgation date and number, as law.go.kr lists them.',
            'Credits come from law.go.kr\'s version records: every unit that differs from the version before is credited to the law (공포번호) that version records. For 타법개정 that is the other law whose 부칙 made the change; its title is taken from the version\'s 개정문.',
            'Editorial notes law.go.kr adds to the consolidated text are removed before comparing: <개정 …>, <신설 …>, the dates after 삭제, and bracketed notes such as [전문개정 …], [본조신설 …], [제목개정 …], [종전 …] and Constitutional Court notes ([단순위헌 …], [헌법불합치 …]). 조문참고자료 is not read.',
            'Constitutional Court (헌법재판소) decisions that void provisions without a statutory amendment are not shown as commits: law.go.kr does not change the wording for them, only adds a note.',
            'Headings (편/장/절/관) form one file, structure.md, so renaming a chapter is one line; each 부칙 is its own file, keyed by its law\'s promulgation date and number.',
            'Annexes (별표, 서식) are not included.',
        ] + decisions_extra,
        'ai_use': ['Claude Code (claude-opus-5-5) wrote fetch.py and parse.py. No model wrote, summarised or transcribed any legal text; every word comes from the law.go.kr API responses.'],
    }
    out = os.path.join(HERE, 'corpus.json')
    with open(out + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write('\n')
    os.replace(out + '.tmp', out)
    with open(os.path.join(HERE, 'parse.log'), 'w', encoding='utf-8', newline='\n') as f:
        for e in log:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    for a in acts:
        print(a['slug'], len(a['versions']), 'versions', file=sys.stderr)


if __name__ == '__main__':
    main()
