"""Provision intervals and commit provenance, including published correction overlays."""
import csv
import datetime as dt
import io
import subprocess

import corpus_standard as S

FIELDS = ('path', 'act', 'from', 'to', 'status', 'kind', 'law', 'text_as_of', 'commit', 'text_source', 'sha256')


def before(day):
    return (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat()


def after(day):
    return (dt.date.fromisoformat(day) + dt.timedelta(days=1)).isoformat()


def commit_records(repo, future='futuro'):
    def git(*args):
        return subprocess.check_output(['git', '-c', 'gc.auto=0', '-c', 'core.quotePath=false', *args],
                                       cwd=repo, encoding='utf-8', timeout=120)
    refs = git('for-each-ref', '--format=%(refname)', 'refs/heads/main', f'refs/heads/{future}',
               f'refs/remotes/origin/{future}').splitlines()
    if not refs:
        return []
    main_commits = set(git('rev-list', 'main').split()) if 'refs/heads/main' in refs else set()
    fmt = '%x00%H%x1f%s%x1f%an'
    keys = ('In-force', 'Kind', 'Law', 'Text-as-of', 'Text-source', 'Consolidated', 'Corrects', 'Files', 'Words-changed', 'Corpus-standard')
    fmt += ''.join(f'%x1f%(trailers:key={key},valueonly,separator=%x1e)' for key in keys)
    out = git('log', '--reverse', '--no-merges', '--no-renames', '--name-only', '--format=' + fmt, *refs)
    records = []
    for raw in out.split('\0')[1:]:
        header, _, names = raw.partition('\n')
        values = header.split('\x1f')
        if len(values) != 3 + len(keys):
            raise ValueError('cannot parse commit provenance')
        sha, subject, author = values[:3]
        trailers = dict(zip(keys, (v.strip() for v in values[3:])))
        day = trailers['In-force']
        if not day:
            continue
        kind = S.legacy_kind(trailers['Kind'], subject, author, trailers['Words-changed'], trailers['Corrects'])
        if kind == 'documentation':
            continue
        files = [p for p in names.splitlines() if p.endswith('.md') and not p.endswith('/README.md')]
        if trailers['Files']:
            files = trailers['Files'].split('\x1e')
        ranges = []
        for value in trailers['Corrects'].split('\x1e'):
            bits = value.split()
            if len(bits) == 2 and '..' in bits[1]:
                lo, hi = bits[1].split('..', 1)
                ranges.append((bits[0], lo, hi))
        records.append({'commit': sha, 'day': day, 'kind': kind, 'law': trailers['Law'], 'files': files,
                        'branch': 'main' if sha in main_commits else future,
                        'all_files': names.splitlines(), 'standard': trailers['Corpus-standard'],
                        'text_as_of': trailers['Text-as-of'], 'text_source': S.legacy_text_source(trailers) or '',
                        'ranges': ranges})
    return records


def provision_rows(c, records):
    """Version/credit events select provenance from the independently recorded commit log."""
    rows = []
    for act in c['acts']:
        slug = act['slug']
        events = {}
        previous = {}
        for index, version in enumerate(act['versions']):
            units = version['units']
            for key in sorted(set(previous) | set(units)):
                credits = version.get('credits', {}).get(key, [])
                if index and previous.get(key, {}).get('text') == units.get(key, {}).get('text') and not credits:
                    continue
                path = f'{slug}/{key}.md'
                credited = credits or ([act['first_law']] if index == 0 and act.get('first_law') else [])
                def law_order(law_key):
                    law = c['laws'][law_key]
                    return law.get('published') or law.get('enacted') or '9999', law.get('enacted') or '9999', law_key
                law_key = max(credited, key=law_order) if credited else None
                law = c['laws'].get(law_key, {})
                label = law.get('label', '')
                kind = S.law_commit_kind(law) if law_key else 'baseline' if index == 0 else 'uncredited'
                candidates = [r for r in records if r['day'] == version['from'] and r['kind'] != 'correction'
                              and (path in r['files'] or (label and r['law'] == label))]
                if label:
                    owned = [r for r in candidates if r['law'] == label]
                    candidates = owned or candidates
                if version['from'] <= c.get('_docs_date', '9999-12-31'):
                    candidates = [r for r in candidates if r.get('branch', 'main') == 'main'] or candidates
                origin = candidates[-1] if candidates else None
                captured = S.text_as_of(c, act, version) or ''
                first = captured if kind == 'baseline' and captured else version['from']
                events.setdefault(path, []).append({'path': path, 'act': slug, 'from': first,
                    'to': version.get('to') or '', 'status': 'in force' if key in units else 'repealed',
                    'kind': kind, 'law': label, 'text_as_of': captured,
                    'commit': origin['commit'] if origin else '',
                    'text_source': version.get('source_url') or act.get('url') or '',
                    'sha256': version.get('sha256') or '', '_day': version['from']})
            previous = units
        for path, versions in events.items():
            fixes = []
            for r in records:
                if r['kind'] != 'correction' or path not in r['files']:
                    continue
                for target, lo, hi in r['ranges']:
                    if target != slug:
                        continue
                    if not hi:
                        later = [p['day'] for p in records if p['kind'] != 'correction'
                                 and p['day'] > lo and any(f.startswith(slug + '/') for f in p['files'])]
                        hi = before(min(later)) if later else ''
                    fixes.append((lo, hi, r))
            for index, original in enumerate(versions):
                next_from = versions[index + 1]['from'] if index + 1 < len(versions) else None
                end = original['to'] or (max(original['from'], before(next_from)) if next_from else '')
                boundaries = {original['from']}
                for lo, hi, _ in fixes:
                    if lo > original['from'] and (not end or lo <= end):
                        boundaries.add(lo)
                    if hi and hi < '9999-12-31':
                        boundary = after(hi)
                        if boundary > original['from'] and (not end or boundary <= end):
                            boundaries.add(boundary)
                cuts = sorted(boundaries)
                for j, start in enumerate(cuts):
                    row = {k: v for k, v in original.items() if not k.startswith('_')}
                    row['from'] = start
                    row['to'] = before(cuts[j + 1]) if j + 1 < len(cuts) else end
                    if next_from and row['status'] == 'in force':
                        row['status'] = 'replaced'
                    elif row['kind'] == 'baseline' and row['text_as_of']:
                        row['status'] = 'as captured'
                    for lo, hi, fix in fixes:
                        if lo <= start and (not hi or start <= hi):
                            row.update(commit=fix['commit'], kind='correction')
                            for field in ('text_as_of', 'text_source'):
                                if fix.get(field):
                                    row[field] = fix[field]
                    if not row['commit']:
                        # A backfilled version may have no ordinary commit at its
                        # own date. When its bounded correction ends, the original
                        # published ordinary commit at that boundary resumes, even
                        # if the corrected input has no new wording/credit event.
                        resumed = [r for r in records if r['kind'] != 'correction'
                                   and r['day'] == start and path in r['files']]
                        if start <= c.get('_docs_date', '9999-12-31'):
                            resumed = [r for r in resumed if r.get('branch', 'main') == 'main'] or resumed
                        if resumed:
                            origin = resumed[-1]
                            row.update(commit=origin['commit'], kind=origin['kind'], law=origin['law'])
                    if not row['commit']:
                        raise ValueError(f'no published commit for {path} from {row["from"]}')
                    rows.append(row)
    return sorted(rows, key=lambda r: (r['path'], r['from']))


def document(c, repo, records=None):
    if records is None:
        records = commit_records(repo, c['country'].get('future_branch', 'futuro')) if repo else []
    rows = provision_rows(c, records) if repo else []
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDS, delimiter='\t', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()
