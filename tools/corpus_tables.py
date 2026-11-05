"""Public corpus indexes derived from source facts and committed versions."""
import datetime as dt
import corpus_standard as S
import corpus_images as M

ACT_STATUSES = {'in force', 'repealed', 'expired', 'not yet in force', 'as captured'}


def version_status(c, act, version, day):
    given = version.get('status') or act.get('status')
    if given:
        if given not in ACT_STATUSES:
            raise ValueError(f'unknown act status {given!r}')
        return given
    if version.get('from', day) > day:
        return 'not yet in force'
    expired = act.get('expired') or act.get('expires')
    if expired and expired <= day:
        return 'expired'
    if (act.get('repealed') and act['repealed'] <= day) or (
            'units' in version and not version['units'] and len(act.get('versions', [])) > 1
            and not act.get('corpus_withdrawal')):
        return 'repealed'
    if S.text_as_of(c, act, version) or (not act.get('first_law') and not version.get('in_force_known')):
        return 'as captured'
    return 'in force'


def acts_document(c, day):
    rows = []
    for act in c['acts']:
        law = c['laws'].get(act.get('first_law'), {})
        versions = act.get('versions', [])
        current = [v for v in versions if v['from'] <= day]
        latest = current[-1] if current else versions[0] if versions else {}
        status = version_status(c, act, latest, day)
        kind = act.get('law_kind') or S.instrument_kind(law or {'kind': act.get('kind', 'other')})
        if kind not in S.LAW_KINDS:
            raise ValueError(f'{act["slug"]}: invalid law_kind {kind!r}')
        repealed = act.get('repealed') or (latest.get('from') if status == 'repealed' else None)
        repealing = act.get('repealed_by') or latest.get('repealed_by')
        if repealing in c['laws']:
            repealing = c['laws'][repealing]['label']
        rows.append({'slug': act['slug'], 'path': act['slug'], 'id': act.get('id') or law.get('label'),
                     'eli': act.get('eli') or law.get('eli'), 'title': act['title'], 'short': act['short'],
                     'law_kind': kind, 'enacted': act.get('enacted') or law.get('enacted'),
                     'published': act.get('published') or law.get('published'),
                     'in_force': act.get('in_force') or (versions[0]['from'] if versions and act.get('first_law') else None),
                     'repealed': repealed, 'repealed_by': repealing, 'status': status, 'url': act.get('url')})
        images = M.counts(latest)
        images_complete = images['source'] is not None and not images['normative_omitted'] \
            and images['source'] == images['referenced'] + images['omitted']
        rows[-1].update(images=images['referenced'], images_omitted=images['omitted'],
                        images_source=images['source'], images_complete=images_complete,
                        complete=images_complete and latest.get('complete', act.get('complete')) is True)
    return {'acts': rows}


def versions_document(c, day):
    acts = []
    for act in c['acts']:
        versions = []
        for i, v in enumerate(act['versions']):
            following = act['versions'][i + 1] if i + 1 < len(act['versions']) else None
            end = v.get('to') or (max(v['from'], (dt.date.fromisoformat(following['from']) - dt.timedelta(days=1)).isoformat())
                                   if following else None)
            status = version_status(c, act, v, day)
            if v['from'] <= day and following and following['from'] <= day and v['units']:
                status = 'replaced'
            versions.append({'from': v['from'], 'to': end, 'status': status,
                             'text_as_of': S.text_as_of(c, act, v), 'units': len(v['units']),
                             'source_url': v.get('source_url'), 'sha256': v.get('sha256')})
        acts.append({'slug': act['slug'], 'short': act['short'], 'title': act['title'], 'url': act.get('url'),
                     'versions': versions})
    return {'country': c['country']['code'], 'acts': acts}


def ledger_kind(c, entry):
    value = entry['kind']
    if value == 'start':
        return 'law' if entry.get('law') else 'baseline'
    if value == 'publisher':
        starts = {a['slug']: a['versions'][0]['from'] for a in c['acts'] if a['versions']}
        return 'baseline' if any(starts.get(a) == entry['day'] for a in entry['acts']) else 'uncredited'
    return S.legacy_kind(value, corrects='known' if value == 'correction' else '')
