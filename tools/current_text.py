"""Check 11: compare the committed tip with the source text in force on the checked day."""
import hashlib
import subprocess

import provision_index as I


def blob(text):
    raw = text.encode('utf-8') if isinstance(text, str) else text
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def ordinary_order(repo, planned):
    """Refuse a late ordinary write to an existing file before starting an import."""
    latest = {}
    for row in I.commit_records(repo):
        if row['branch'] != 'main' or row['kind'] == 'correction':
            continue
        for path in row['files']:
            latest[path] = max(latest.get(path, ''), row['day'])
    for entry in planned:
        for path in entry['files']:
            if not path.endswith('.md') or path.endswith('/README.md'):
                continue
            if entry['day'] < latest.get(path, ''):
                raise ValueError(f'{path}: older ordinary append {entry["day"]} follows {latest[path]}; '
                                 'supply a labelled correction, never overwrite the current text')
            latest[path] = entry['day']


def check(repo, c, day, overrides=None):
    """Expected blobs come from the input source versions, not the generated indexes.

    `overrides` preflights an entire planned append without changing any ref. Pinned mismatches warn;
    newly written law (Corpus-standard: 1) and planned appends fail. Documentation does not change this policy.
    """
    raw = subprocess.check_output(['git', '-c', 'core.quotePath=false', 'ls-tree', '-r', 'main'],
                                  cwd=repo, encoding='utf-8', timeout=120)
    tree = {line.split('\t', 1)[1]: line.split('\t', 1)[0].split()[2] for line in raw.splitlines()}
    if overrides is not None:
        for path, text in overrides.items():
            if text is None:
                tree.pop(path, None)
            else:
                tree[path] = blob(text)
    latest = {}
    for row in I.commit_records(repo):
        if row['branch'] == 'main':
            for path in row['files']:
                latest[path] = row
    errors, warnings = [], []
    for act in c['acts']:
        slug = act['slug']
        versions = [v for v in act['versions'] if v['from'] <= day]
        units = versions[-1]['units'] if versions else {}
        expected = {f'{slug}/{key}.md': blob(unit['text']) for key, unit in units.items()}
        actual = {p: oid for p, oid in tree.items()
                  if p.startswith(slug + '/') and p.endswith('.md') and p != slug + '/README.md'}
        for path in sorted(set(expected) | set(actual)):
            if expected.get(path) == actual.get(path):
                continue
            strict = overrides is not None or latest.get(path, {}).get('standard') == '1'
            (errors if strict else warnings).append(f'{path}: HEAD differs from source text in force on {day}')
    return {'tip_errors': len(errors), 'tip_warnings': len(warnings), 'tip_details': (errors + warnings)[:50]}
