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
PLACEHOLDER = '[출처가 이 날짜에 시행 중인 문구를 제공하지 않음.]\n'
EARLY = []  # decisions: provisions whose wording law.go.kr shows before its law took effect

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
            if nxt and not nxt.startswith('[') and '개정한다' not in nxt and '공포한다' not in nxt:
                return nxt
    kind = meta['제개정구분']
    return f'{act_name} {kind}' if kind else act_name


def law_key(meta):
    no = int(meta['공포번호'])
    if meta['법종구분'] == '헌법':
        return f'heonbeop-{no}', f'헌법 제{no}호'
    return f'law-{no}', f'법률 제{no}호'


REF = re.compile(r'제(\d+)조(?:의(\d+))?(?:\s*(?:내지|부터|~)\s*제(\d+)조(?:의(\d+))?)?')
HEAD_REF = re.compile(r'제\d+(?:편|장|절|관)')


def amend_refs(amend):
    """The provisions an amending law's 개정문 names for this act: the lines after '... 개정한다' up to its 부칙
    or the next omitted law ('생략')."""
    body, on = [], False
    for s in amend:
        if not on:
            on = '개정한다' in s.replace(' ', '')
            continue
        if re.match(r'^부\s*칙', s) or '생략' in s:
            if body:
                break
            continue
        body.append(s)
    keys, ranges, heads = set(), [], False
    for s in body:
        heads = heads or bool(HEAD_REF.search(s))
        for m in REF.finditer(s):
            a = art_key(m.group(1), m.group(2) or '0')
            keys.add(a)
            if m.group(3):
                ranges.append((a, art_key(m.group(3), m.group(4) or '0')))
    return {'keys': keys, 'ranges': ranges, 'heads': heads}


def names(refs, k):
    if k == 'structure':
        return refs['heads']
    return k in refs['keys'] or any(a <= k <= b for a, b in refs['ranges'])


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
                     'units': units, 'ann': ann, 'law': key, 'pd': pd, 'kind': meta['제개정구분'], 'refs': amend_refs(amend)})
    # The earliest day any law promulgated on a given day takes effect for this act (annotations name laws by
    # promulgation date only, so laws promulgated the same day are taken together).
    first_in_force = {}
    for r in recs:
        first_in_force[r['pd']] = min(first_in_force.get(r['pd'], r['efyd']), r['efyd'])
    by_day = {}
    for r in recs:
        by_day.setdefault(r['efyd'], []).append(r)
    versions, state, maxP, first, history = [], None, None, None, {}
    for efyd in sorted(by_day):
        grp = sorted(by_day[efyd], key=lambda r: r['P'])
        rep = grp[-1]
        glaws = []
        for r in grp:
            if r['law'] not in glaws:
                glaws.append(r['law'])
        notes = []
        if state is None:
            first = rep
            state = dict(rep['units'])
            versions.append({'from': iso(efyd), 'source_url': rep['url'], 'sha256': rep['sha'], 'units': dict(state), 'credits': {}})
            for k, u in state.items():
                history[k] = [u['text']]
            maxP = rep['P']
            continue
        if rep['P'] >= maxP:
            cand = dict(rep['units'])
        else:
            # Promulgated before a law already in force (it takes effect later): law.go.kr composed this text before
            # that law, so it lacks its changes. Apply only this law's own changes, against the record before it by
            # promulgation.
            cands = [r for r in recs if (r['P'], r['efyd']) < (rep['P'], rep['efyd']) and r['efyd'] <= efyd]
            base = max(cands, key=lambda r: (r['P'], r['efyd']))
            delta = sorted(k for k in set(rep['units']) | set(base['units']) if rep['units'].get(k) != base['units'].get(k))
            cand = dict(state)
            for k in delta:
                if k in rep['units']:
                    cand[k] = rep['units'][k]
                else:
                    cand.pop(k, None)
            notes.append(f"law.go.kr composed this text when {laws[rep['law']]['label']} was promulgated ({iso(rep['pd'])}), before "
                         f"laws promulgated later but in force earlier; only its own changes (against law.go.kr's version of "
                         f"{iso(base['efyd'])}) are applied to the text in force the day before.")
            log.append({'act': cfg['slug'], 'from': iso(efyd), 'out_of_order': rep['law'], 'base': f"{base['law']}@{base['efyd']}", 'delta': len(delta)})
        maxP = max(maxP, rep['P'])
        # Text that appears before its law: a changed provision whose amendment note names a law that takes effect
        # for this act only later. Keep the text in force the day before if this day's laws did not touch it;
        # otherwise the source does not give the text in force on this day.
        own = {r['pd'] for r in grp}
        early = []
        for k in sorted(set(cand) | set(state)):
            if cand.get(k) == state.get(k) or k not in cand:
                continue
            dates = rep['ann'].get(k, set())
            later = sorted(d for d in dates if d in first_in_force and first_in_force[d] > efyd)
            if not later:
                continue
            if dates & own:
                cand[k] = {**cand[k], 'text': PLACEHOLDER}
                early.append({'unit': k, 'later': later, 'fix': 'placeholder'})
            elif k in state:
                cand[k] = state[k]
                early.append({'unit': k, 'later': later, 'fix': 'kept'})
            else:
                cand.pop(k)
                early.append({'unit': k, 'later': later, 'fix': 'absent'})
        changed = sorted(k for k in set(cand) | set(state) if cand.get(k) != state.get(k))
        if not changed:
            log.append({'act': cfg['slug'], 'from': iso(efyd), 'no_change': glaws})
            continue
        credits, spacing, reverted, uncredited = {}, [], [], []
        for k in changed:
            o, n = state.get(k), cand.get(k)
            if o and n and squash(o['text']) == squash(n['text']):
                spacing.append(k)
                continue
            if n and n['text'] == PLACEHOLDER:
                continue  # the publisher's: the source lacks the text
            if n and n['text'] in history.get(k, [])[:-1]:
                reverted.append(k)
            if k.startswith('buchik-'):
                named = [l for l in glaws if l.split('-')[-1] == str(int(k.split('-')[2]))]
                if named:
                    credits[k] = named
                    continue
            # Credit only on the source's own evidence: the law rewrote the whole act, its 개정문 (the amending
            # text) names the provision, or law.go.kr's amendment notes on the provision name its promulgation day.
            dates = rep['ann'].get(k, set())
            named = [l for l in glaws if any(r['kind'] in ('제정', '전부개정') or names(r['refs'], k) or r['pd'] in dates
                                             for r in grp if r['law'] == l)]
            if named:
                credits[k] = named
            else:
                uncredited.append(k)
        v = {'from': iso(efyd), 'source_url': rep['url'], 'sha256': rep['sha'],
             'changes': {k: cand.get(k) for k in changed}, 'credits': credits}
        if len(grp) > 1:
            notes.append('law.go.kr records ' + ', '.join(dict.fromkeys(laws[r['law']]['label'] for r in grp)) +
                         ' in force for this act on this day; the text is its version for the last of them, and each provision is '
                         'credited to the law(s) its amendment notes name.')
        if spacing:
            notes.append(f'{len(spacing)} provision(s) differ from the day before only in spacing (띄어쓰기), '
                         'which law.go.kr revised in its own database; no law is credited for that.')
        if early:
            notes.append(f'{len(early)} provision(s) in law.go.kr\'s text carry wording from a law that takes effect later; '
                         'they are corrected as listed in the decisions.')
            for e in early:
                EARLY.append(f"{cfg['name']} {state.get(e['unit'], cand.get(e['unit'], {})).get('label', e['unit'])} on {iso(efyd)}: "
                             f"law.go.kr's text already has wording from the law(s) promulgated "
                             f"{', '.join(iso(d) for d in e['later'])}, which take effect for this act later; "
                             + {'kept': 'the text in force the day before is kept.',
                                'absent': 'the provision is left out until that law takes effect.',
                                'placeholder': 'this day\'s law also changed it, so it reads "' + PLACEHOLDER.strip() + '".'}[e['fix']])
        if notes:
            v['note'] = ' '.join(notes)
        log.append({'act': cfg['slug'], 'from': iso(efyd), 'laws': glaws, 'changed': len(changed), 'spacing': len(spacing),
                    'reverted': reverted, 'uncredited': uncredited, 'early': early})
        versions.append(v)
        for k in changed:
            if k in cand:
                history.setdefault(k, []).append(cand[k]['text'])
        state = cand
    latest = max(recs, key=lambda r: (r['efyd'], r['P']))
    log.append({'act': cfg['slug'], 'end_mismatch': sorted(k for k in set(state) | set(latest['units'])
                                                           if state.get(k) != latest['units'].get(k))})
    enacted = first['kind'] == '제정'
    return {'slug': cfg['slug'], 'short': cfg.get('short', cfg['name']), 'title': cfg['name'],
            'url': 'https://www.law.go.kr/법령/' + cfg['name'].replace(' ', ''),
            'first_law': first['law'] if enacted else None,
            'earlier_laws': [] if enacted else [first['law']],
            'versions': versions}


DECISIONS = [
    "Every version is law.go.kr's own point-in-time text: one per 시행일자 (in-force date) in the eflaw search, dated by that day, not by promulgation (legalize-kr dates by promulgation).",
    "Where several laws take effect for one act on one day, the day's text is law.go.kr's version for the last of them by promulgation date and number.",
    "A changed provision is credited to a law of that day only on the source's own evidence: the law is the act's 제정 or 전부개정; or the law's 개정문 (its amending text, in law.go.kr's version record) names the provision; or law.go.kr's amendment note on the provision (<개정 ...>, [전문개정 ...], [본조신설 ...]) names the law's promulgation day; or the provision is that law's own 부칙. Everything else is committed by the publisher as unexplained, including the transcription differences between law.go.kr's historical versions (for example 표견대리/표현대리 in 민법 제129조). For 타법개정 the law is the other law whose 부칙 made the change; its title comes from the version's 개정문.",
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
        'decisions': DECISIONS + EARLY + [
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


