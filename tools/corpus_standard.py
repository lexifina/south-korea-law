"""Corpus standard v1: canonical output and explicit historical read adapters."""
import datetime as dt
import re
KINDS = frozenset({'law', 'baseline', 'correction', 'uncredited', 'printing', 'court', 'treaty', 'documentation'})
LAW_KINDS = frozenset({'constitution', 'constitutional-amendment', 'act', 'code', 'decree', 'decree-law',
                       'regulation', 'ordinance', 'legal-notice', 'referendum', 'other'})


def instrument_kind(law):
    explicit = law.get('law_kind')
    if explicit:
        if explicit not in LAW_KINDS:
            raise ValueError(f'unknown law_kind: {explicit!r}')
        return explicit
    old = law.get('kind', 'law').replace(' ', '-')
    return old if old in LAW_KINDS else 'act' if old in ('law', 'act') else 'other'


def law_commit_kind(law):
    value = law.get('kind', 'law')
    return value if value in ('court', 'treaty', 'printing', 'uncredited') else 'law'


def legacy_kind(value, subject='', author='', words_changed='', corrects=''):
    """Section 6 read-only mapping; never used to write new trailers."""
    k = (value or '').strip().lower()
    if k == 'correction':
        return 'correction' if corrects else 'law'
    if author == 'Lexifina' or k == 'documentation':
        return 'documentation'
    if k == 'publisher':
        if 'oldest version available' in subject.lower():
            return 'baseline'
        if '(unexplained)' in subject.lower() or words_changed == 'yes':
            return 'uncredited'
    if k.startswith(('baseline', 'first published')) or k in (
            'consolidated', 'current', 'current-only', 'current-text', 'consolidation',
            'tekst jednolity (current text)'):
        return 'baseline'
    if k in ('unexplained', 'change no law explains') or k.startswith((
            'editorial', 'notes only', 'style only', 'no act named')) or k.endswith(' (not credited)'):
        return 'uncredited'
    if k.startswith('court'):
        return 'court'
    return k if k in KINDS else 'law'


def planned_kind(corpus, entry):
    if entry['kind'] == 'start':
        law = entry['act'].get('first_law')
        return law_commit_kind(corpus['laws'][law]) if law else 'baseline'
    if entry['kind'] == 'law':
        return law_commit_kind(corpus['laws'][entry['law']])
    return 'uncredited' if entry['kind'] == 'unexplained' else entry['kind']


def iso_day(value):
    try:
        return isinstance(value, str) and len(value) == 10 and dt.date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def text_as_of(corpus, act, version):
    if version.get('text_as_of'):
        return version['text_as_of']
    # The exact source capture day is available for this version. Never extract a date from explanatory prose.
    if version.get('in_force_unknown'):
        return version.get('retrieved') or version['from']
    return None


def date_trailers(corpus, act, version, law=None):
    """Validate only a newly written version; pinned commits are not subjected to new requirements."""
    day = version['from']
    law = law or {}
    captured = text_as_of(corpus, act, version)
    basis = version.get('in_force_basis') or law.get('in_force_basis')
    retrieved = {s.get('retrieved') for s in corpus.get('sources', [])} | {version.get('retrieved')}
    source_date_known = bool(version.get('in_force_known') or law.get('enacted') == day or law.get('published') == day)
    if (day == captured or (day in retrieved and not source_date_known)) and not basis:
        raise ValueError(f'{act["slug"]} {day}: retrieval/capture-day In-force requires in_force_basis')
    if day < '1500-01-01' and not corpus['country'].get('record_note'):
        raise ValueError(f'{act["slug"]} {day}: dates before 1500 require country.record_note')
    result = []
    if captured:
        if not iso_day(captured):
            raise ValueError('text_as_of must be YYYY-MM-DD')
        result.append(f'Text-as-of: {captured}')
    if basis:
        if not isinstance(basis, str) or not basis.strip() or '\n' in basis or '\r' in basis:
            raise ValueError('in_force_basis must be one nonempty line')
        result.append(f'In-force-basis: {basis.strip()}')
    retroactive = version.get('retroactive') or law.get('retroactive')
    if retroactive:
        if not isinstance(retroactive, str) or not retroactive.strip() or retroactive.strip() == 'yes':
            raise ValueError('retroactive must name the source provision, not just yes')
        result.append('Retroactive: ' + (retroactive if retroactive.startswith('yes; ') else 'yes; ' + retroactive))
    consolidated = version.get('consolidated')
    if consolidated:
        if not iso_day(consolidated):
            raise ValueError('new Consolidated values must be ISO dates; use source_url for a URL')
        result.append(f'Consolidated: {consolidated}')
    return result


def legacy_text_source(trailers):
    value = trailers.get('Text-source') or trailers.get('Consolidated')
    return value if value and not iso_day(value) else None


def future_branch(country):
    name = country.get('future_branch', 'futuro')
    if (not isinstance(name, str) or name in ('main', 'HEAD') or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9/_-]*', name)
            or '//' in name or name.endswith('/') or any(p.startswith('-') for p in name.split('/'))):
        raise ValueError('future_branch must be a valid branch distinct from main')
    return name
