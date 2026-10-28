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


