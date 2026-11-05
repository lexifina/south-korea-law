"""Descriptor and path helpers for corpus standard v1."""
import re
import unicodedata

HISTORIES = {'in-force', 'replayed', 'as-enacted', 'current-only', 'metadata-only'}
WHOLE = {'national', 'federal', 'bund', 'union'}
COUNTRY_SLUGS = {
    'US': 'united-states', 'ID': 'indonesia', 'BR': 'brazil', 'AR': 'argentina', 'DE': 'germany',
    'CA': 'canada', 'ES': 'spain', 'IT': 'italy', 'MX': 'mexico', 'AU': 'australia',
    'CH': 'switzerland', 'AT': 'austria', 'KE': 'kenya', 'FM': 'micronesia', 'NR': 'nauru',
    'NL': 'netherlands', 'NO': 'norway', 'LI': 'liechtenstein', 'EU': 'european-union',
    'PK': 'pakistan', 'ZA': 'south-africa', 'NZ': 'new-zealand', 'AE': 'united-arab-emirates',
}
PARENT_PLACES = {'ID-JI': 'east-java', 'ID-JT': 'central-java', 'ID-JB': 'west-java', 'ID-YO': 'yogyakarta',
                 'BR-MG': 'minas-gerais', 'BR-BA': 'bahia', 'BR-SP': 'sao-paulo', 'AR-B': 'buenos-aires'}


def place_slug(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return re.sub('[^a-z0-9]+', '-', value).strip('-')


def descriptor_path(country):
    explicit = country.get('path')
    if explicit:
        if not re.fullmatch(r'[a-z0-9-]+(?:/[a-z0-9-]+){1,3}', explicit):
            raise ValueError('country.path must contain lowercase ASCII place slugs')
        parts = explicit.split('/')
        if len(parts) == 4 and parts[-2].endswith('-city'):
            parts[-2] = parts[-2][:-5]
        return '/'.join(parts)
    iso = country['code'][:2].upper()
    slug = country['slug']
    national = '-' not in country['code']
    country_slug = country.get('country_slug') or COUNTRY_SLUGS.get(iso)
    if national:
        return f'{country_slug or place_slug(slug)}/{country.get("whole_level", "national")}/{country.get("corpus_kind", "acts")}'
    if not country_slug or not slug.startswith(country_slug + '-'):
        raise ValueError('sub-national country.path is required when the country/place cannot be identified')
    place = slug[len(country_slug) + 1:]
    code_parts = country['code'].split('-')
    if len(code_parts) > 2:
        parent_code = '-'.join(code_parts[:2])
        parent = country.get('parent_path') or PARENT_PLACES.get(parent_code)
        if not parent:
            raise ValueError(f'country.path or parent_path is required for {country["code"]}')
        parent = parent.removeprefix(country_slug + '/')
        place = place.removeprefix(parent + '-')
        if place.endswith('-city'):
            place = place[:-5]
        return f'{country_slug}/{parent}/{place}/{country.get("corpus_kind", "acts")}'
    return f'{country_slug}/{place}/{country.get("corpus_kind", "acts")}'
