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
    for efyd, pd, pn, mst in sorted({(x['시행일자'], x['공포일자'], int(x['공포번호']), x['법령일련번호']) for x in listing}):
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
                     'units': units, 'ann': ann, 'law': key, 'pd': pd, 'kind': meta['제개정구분']})
    #@@REPLAY@@
    enacted = first['kind'] == '제정'
    return {'slug': cfg['slug'], 'short': cfg.get('short', cfg['name']), 'title': cfg['name'],
            'url': 'https://www.law.go.kr/법령/' + cfg['name'].replace(' ', ''),
            'first_law': first['law'] if enacted else None,
            'earlier_laws': [] if enacted else [first['law']],
            'versions': versions}


DECISIONS = [
    "Every version is law.go.kr's own point-in-time text: one per 시행일자 (in-force date) in the eflaw search, dated by that day, not by promulgation (legalize-kr dates by promulgation).",
    "Where several laws take effect for one act on one day, the day's text is law.go.kr's version for the last of them by promulgation date and number; each changed provision is credited to the law(s) of that day whose promulgation date law.go.kr's own amendment notes (<개정 ...>, [전문개정 ...], [본조신설 ...]) name for it, and is otherwise left uncredited.",
    "Otherwise credits come from law.go.kr's version records: every provision that differs from the day before is credited to the law (공포번호) that version records. For 타법개정 that is the other law whose 부칙 made the change; its title is taken from the version's 개정문.",
    "A version promulgated before a law already in force (because it takes effect later) was composed by law.go.kr from the text as it stood at its promulgation, so it lacks that later law's changes. Only its own changes (its text against law.go.kr's version before it by promulgation) are applied to the text in force the day before; each such version says so in its note.",
    "Provisions whose text differs from the day before only in spacing (law.go.kr re-spaced old texts, 띄어쓰기) are committed by the publisher as unexplained, never credited to a law.",
    "Editorial notes law.go.kr adds to the consolidated text are removed: <개정 ...>, <신설 ...>, the dates after 삭제, and bracketed notes such as [전문개정 ...], [본조신설 ...], [제목개정 ...], [종전 ...] and Constitutional Court notes ([단순위헌 ...], [헌법불합치 ...]). 조문참고자료 is not part of the text.",
    "Constitutional Court (헌법재판소) decisions that void provisions without a statutory amendment are not commits: law.go.kr keeps the words and adds only a note.",
    "Headings (편/장/절/관) form one file per act, structure.md; each 부칙 is its own file, keyed by its law's promulgation date and number.",
    "Annexes (별표, 서식) are not included.",
]


def main():
    acts_cfg = json.load(open(os.path.join(HERE, 'acts.json'), encoding='utf-8'))
    laws, acts, log = {}, [], []
    reqlog = os.path.join(fetch.CACHE, 'requests.jsonl')
    requests = sum(1 for _ in open(reqlog, encoding='utf-8')) if os.path.exists(reqlog) else 0
    for cfg in acts_cfg:
        a = build_act(cfg, laws, log)
        if a:
            acts.append(a)
            print(a['slug'], len(a['versions']), 'versions', file=sys.stderr)
    used = {l for a in acts for v in a['versions'] for ls in v['credits'].values() for l in ls}
    used |= {a['first_law'] for a in acts if a['first_law']} | {l for a in acts for l in a['earlier_laws']}
    no_change = [e for e in log if 'no_change' in e]
    corpus = {
        'country': {
            'code': 'KR', 'name': 'South Korea', 'slug': 'south-korea', 'lang': 'ko', 'tz': 'Asia/Seoul',
            'future_branch': 'future',
            'publisher': {'name': '법제처 국가법령정보센터 (National Law Information Center)', 'email': 'nlic@law.go.kr.invalid'},
            'default_in_force_rule': {
                'text': ('대한민국헌법 제53조 제7항: 법률은 특별한 규정이 없는 한 공포한 날로부터 20일을 경과함으로써 효력을 발생한다 '
                         '(a law takes effect 20 days after promulgation unless it provides otherwise). Every version here carries '
                         "law.go.kr's own 시행일자 (in-force date), which already applies this rule or the law's own 부칙."),
                'source': 'https://www.law.go.kr/법령/대한민국헌법'},
            'licence_note': ('Statute text is not protected by copyright (저작권법 제7조 제1호). Source: 법제처 국가법령정보센터 '
                             '(www.law.go.kr), Open API (open.law.go.kr).'),
        },
        'sources': [{
            'name': '법제처 국가법령정보센터 Open API (National Law Information Center, Ministry of Government Legislation)',
            'url': 'https://www.law.go.kr/DRF/', 'retrieved': RETRIEVED, 'requests': requests,
            'licence': 'Statutes are not copyright works (저작권법 제7조); law.go.kr offers its data for reuse (공공누리 / KOGL)',
            'notes': ("lawSearch.do?target=eflaw lists every version by 시행일자; lawService.do?target=eflaw&MST=&efYd=&type=XML "
                      "gives each version's full text. OC=test (the API's public demonstration id).")}],
        'laws': {k: v for k, v in sorted(laws.items()) if k in used},
        'acts': acts,
        'applies': [],
        'decisions': DECISIONS + [
            f"law.go.kr lists {', '.join(e['no_change'])} in force for {e['act']} on {e['from']}, but the text equals the day before's after removing editorial notes; no commit."
            for e in no_change],
        'ai_use': ['Claude Code (claude-opus-5-5) wrote fetch.py and parse.py. No model wrote, summarised or transcribed any legal text; every word comes from the law.go.kr API responses.'],
    }
    out = os.path.join(HERE, 'corpus.json')
    with open(out + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1)
        f.write('\n')
    os.replace(out + '.tmp', out)
    with open(os.path.join(HERE, 'parse.log'), 'w', encoding='utf-8', newline='\n') as f:
        for e in log:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()


