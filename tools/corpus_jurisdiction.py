"""Closed jurisdiction levels, canonical codes, and hierarchy from the descriptor path."""
import re
import corpus_paths as P

WHOLE = {'national', 'federal', 'bund', 'union', 'uk'}
FIRST = {'state', 'province', 'region', 'canton', 'entity', 'territory', 'district',
         'autonomous city', 'autonomous community', 'subdivision', 'community', 'federal entity',
         'autonomous territorial unit', 'autonomous region', 'emirate',
         'metropolitan municipality with regional functions'}
LEVELS = {'country', 'supranational', 'municipality', 'regency'} | WHOLE | FIRST


def document(country, path, previous=None):
    old = previous or {}
    places = path.split('/')[:-1]
    if not places:
        raise ValueError('jurisdiction needs a descriptor path')
    iso = {v: k for k, v in P.COUNTRY_SLUGS.items()}.get(places[0], country['code'][:2].upper())
    if not re.fullmatch('[A-Z]{2}', iso):
        raise ValueError('country code must be ISO alpha-2')
    if len(places) == 1:
        level, code, parent = ('supranational' if iso == 'EU' else 'country'), iso, None
    elif len(places) == 2 and places[1] in WHOLE:
        level, code, parent = places[1], iso, places[0]
    elif len(places) == 2:
        level = country.get('jurisdiction_level') or (old.get('level') if old.get('level') in FIRST else None)
        # Match global-law describe.py: retain a source's type, otherwise subdivision.
        # A country's usual type is not evidence for an individual subdivision.
        level = level or 'subdivision'
        if level not in FIRST:
            raise ValueError(f'{path}: give an explicit jurisdiction_level from the closed first-level list')
        candidate = country.get('subdivision_code') or country['code']
        if candidate.upper() == iso:
            candidate = old.get('code', '')
        candidate = candidate.upper()
        code = candidate if candidate.startswith(iso + '-') else iso + '-' + candidate
        if not re.fullmatch(iso + r'-[A-Z0-9]{1,3}', code):
            raise ValueError(f'{path}: first-level code must be a country-prefixed ISO 3166-2 code')
        parent = places[0]
    elif len(places) == 3:
        parent = '/'.join(places[:-1])
        parent_code = country.get('parent_code') or '-'.join(country['code'].split('-')[:2])
        if not re.fullmatch(iso + r'-[A-Z0-9]{1,3}', parent_code):
            raise ValueError(f'{path}: parent_code must be a country-prefixed ISO 3166-2 code')
        if (country.get('jurisdiction_level') or old.get('level')) == 'canton':
            # A canton inside an entity can retain its own ISO subdivision code.
            # Geographic nesting does not turn the source's canton into a municipality.
            level = 'canton'
            candidate = str(country.get('subdivision_code') or old.get('code') or country['code']).upper()
            code = candidate if candidate.startswith(iso + '-') else iso + '-' + candidate
            if not re.fullmatch(iso + r'-[A-Z0-9]{1,3}', code):
                raise ValueError(f'{path}: canton code must be a country-prefixed ISO 3166-2 code')
        else:
            level = 'regency' if places[-1].endswith('-regency') else 'municipality'
            code = parent_code + '-' + places[-1].upper()
    else:
        raise ValueError('jurisdiction path is deeper than country/state/place')
    return {**old, 'path': '/'.join(places), 'code': code, 'level': level, 'parent': parent}
