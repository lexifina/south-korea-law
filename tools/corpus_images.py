"""Byte-preserving legal images and the corpus-standard completeness check."""
import csv
import hashlib
import io
import json
import re
import subprocess
import warnings
from pathlib import Path
from urllib.parse import urlsplit

LIMIT = 25 * 1024 * 1024
LINK = re.compile(r'!\[([^\]\n]*)\]\((assets/([0-9a-f]{64})\.([a-z0-9]+))\)')
ANY_IMAGE = re.compile(r'!\[[^\]\n]*\]\([^\n)]*\)|<img\b', re.I)
OMISSION = re.compile(r'\[Image omitted: ([^;\]\n]+); ([^;\]\n]+); reason: (licence|not extractable|too large)\]')
MEDIA = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif', 'svg': 'image/svg+xml',
         'webp': 'image/webp', 'tif': 'image/tiff', 'tiff': 'image/tiff', 'bmp': 'image/bmp'}


def inventory_required(country, folder, published_repo=None):
    """A new target directory is not evidence that the corpus has never been published."""
    if country.get('image_inventory_required'):
        return True
    for repo in (published_repo, Path(folder) / 'repo'):
        if repo and (Path(repo) / '.git').exists():
            known = subprocess.run(['git', '-C', str(repo), 'cat-file', '-e', 'main:data/versions.json'],
                                   capture_output=True, timeout=120)
            if known.returncode == 0:
                return False
            # Native builders use their own version indexes. A dated law commit
            # touching provision Markdown is publication context too; a docs-only
            # scaffold or descriptor is not. Keep unsurveyed distinct from zero.
            law = subprocess.run(['git', '-C', str(repo), 'log', '-1', '--format=%H',
                                  '--extended-regexp', '--grep=^In-force: [0-9]{4}-[0-9]{2}-[0-9]{2}$',
                                  'main', '--', '*.md', ':!README.md', ':!REPRODUCE.md', ':!SOURCES.md',
                                  ':!LICENSE.md', ':!*/README.md', ':!tools/*', ':!data/*'],
                                 capture_output=True, timeout=120)
            if law.returncode == 0 and law.stdout.strip():
                return False
    # A successful publisher receipt survives a cold rebuild of its source folder.
    # A scaffold, a sign-off marker, or a mere "built" label is not a publication.
    receipt = Path(folder) / '.autopush.json'
    if receipt.is_file():
        try:
            previous = json.loads(receipt.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            previous = {}
        if not isinstance(previous, dict):
            previous = {}
        if (re.fullmatch('[0-9a-f]{64}', str(previous.get('built_sha', '')))
                and str(previous.get('result', '')).startswith('pushed (')):
            return False
    return True


def counts(version):
    text = '\n'.join(u.get('text', '') for u in version.get('units', {}).values())
    links = list(LINK.finditer(text))
    notices = list(OMISSION.finditer(text))
    decorative = {o['source_ref'] for o in version.get('images_omitted', []) if o.get('normative') is False}
    return {'source': version.get('source_images'), 'referenced': len(links), 'omitted': len(notices),
            'normative_omitted': sum(m[1] not in decorative for m in notices)}


def issues(act, version, *, require_inventory=True):
    text = '\n'.join(u['text'] for u in version.get('units', {}).values())
    result = []
    n = version.get('source_images')
    if 'source_images' not in version and not require_inventory:
        pass  # Unknown is distinct from an independently surveyed zero.
    elif type(n) is not int or n < 0:
        result.append('source_images inventory is missing or invalid')
    links = list(LINK.finditer(text))
    notices = list(OMISSION.finditer(text))
    if isinstance(n, int) and n != len(links) + len(notices):
        result.append(f'source images {n} != referenced {len(links)} + omitted {len(notices)}')
    if len(ANY_IMAGE.findall(text)) != len(links):
        result.append('image links must use assets/<sha256>.<ext>')
    if text.count('[Image omitted:') != len(notices):
        result.append('malformed image omission notice')
    declared = {(x.get('sha256'), x.get('caption', '')) for x in version.get('images', [])}
    for link in links:
        if (link[3], link[1]) not in declared:
            result.append(f'image {link[3]} or its caption has no source inventory record')
    wanted = {m[3] for m in links}
    for image in version.get('images', []):
        if image.get('sha256') not in wanted:
            result.append(f'unreferenced source image {image.get("sha256")}')
    omissions = {(o.get('source_ref'), o.get('description'), o.get('reason')) for o in version.get('images_omitted', [])}
    # Published text can already contain a valid omission notice without the v1
    # structured survey. Missing survey metadata is unknown, not a silent drop.
    # Once supplied (or required for a new/opted-in corpus), it must agree.
    if require_inventory or 'source_images' in version or 'images_omitted' in version:
        for notice in notices:
            if notice.groups() not in omissions:
                result.append('omission notice has no matching source inventory record')
    return [f'{act["slug"]} {version["from"]}: {message}' for message in result]


def require(act, version, *, required=False):
    if 'source_images' not in version and not required:
        warnings.warn(f'check 10: {act["slug"]} {version["from"]}: source_images not surveyed; '
                      'image completeness is unknown', UserWarning, stacklevel=2)
    errors = issues(act, version, require_inventory=required)
    if errors:
        raise ValueError('check 10: ' + '; '.join(errors))


def load(c, folder, repo=None):
    """Read only local official-source bytes; never download, re-encode, transcribe, or edit provision text."""
    root = Path(folder).resolve()
    attributes = ''
    if (root / 'repo' / '.gitattributes').is_file():
        attributes = (root / 'repo' / '.gitattributes').read_text(encoding='utf-8')
    elif repo and (Path(repo) / '.git').exists():
        old = subprocess.run(['git', 'show', 'main:.gitattributes'], cwd=repo, capture_output=True)
        if old.returncode == 0:
            attributes = old.stdout.decode('utf-8')
    if '**/assets/* binary' not in attributes.splitlines():
        attributes = attributes.rstrip('\n') + ('\n' if attributes else '') + '**/assets/* binary\n'
    for act in c['acts']:
        act['_image_attributes'] = attributes
        assets = {}
        inventory = {}
        for version in act['versions']:
            hosts = {urlsplit(url).hostname for url in (version.get('source_url'), act.get('url')) if url}
            for image in version.get('images', []):
                if not image.get('source_url') or urlsplit(image['source_url']).hostname not in hosts:
                    raise ValueError('image must come from the same official source as the act text')
                ext = image.get('ext') or Path(image.get('file', '')).suffix.lstrip('.').lower()
                if ext not in MEDIA or image.get('media_type', MEDIA[ext]) != MEDIA[ext]:
                    raise ValueError('image extension and media_type must agree')
                digest = image.get('sha256', '')
                if not re.fullmatch('[0-9a-f]{64}', digest):
                    raise ValueError('image needs the sha256 of its source bytes')
                relative = f'{act["slug"]}/assets/{digest}.{ext}'
                file = (root / image.get('file', '')).resolve()
                if not file.is_relative_to(root):
                    raise ValueError('image file escapes the source folder')
                if file.is_file():
                    raw = file.read_bytes()
                elif repo:
                    found = subprocess.run(['git', 'show', 'main:' + relative], cwd=repo, capture_output=True)
                    if found.returncode:
                        raise ValueError(f'official image bytes are unavailable: {relative}')
                    raw = found.stdout
                else:
                    raise ValueError(f'official image bytes are unavailable: {relative}')
                if len(raw) > LIMIT:
                    raise ValueError('image over 25 MB: supply a too large omission notice at its source position')
                if hashlib.sha256(raw).hexdigest() != digest:
                    raise ValueError('image sha256 differs from the official source bytes')
                assets[relative] = raw
                inventory[relative] = {'path': relative, 'act': act['slug'], 'sha256': digest, 'bytes': len(raw),
                                       'media_type': MEDIA[ext], 'source_url': image['source_url']}
        act['_image_bytes'], act['_image_inventory'] = assets, inventory


def files(act, provision_files):
    out = {}
    for text in provision_files.values():
        if not isinstance(text, str):
            continue
        for match in LINK.finditer(text):
            path = act['slug'] + '/' + match[2]
            if path not in act.get('_image_bytes', {}):
                raise ValueError(f'official bytes were not loaded for {path}')
            out[path] = act['_image_bytes'][path]
    if out:
        out['.gitattributes'] = act['_image_attributes']
    return out


def assets_document(c, records):
    first = {}
    for record in records:
        for path in record.get('all_files', []):
            if '/assets/' in path:
                first.setdefault(path, record['commit'])
    buf = io.StringIO()
    fields = ('path', 'act', 'sha256', 'bytes', 'media_type', 'source_url', 'first_commit')
    writer = csv.DictWriter(buf, fieldnames=fields, delimiter='\t', lineterminator='\n')
    writer.writeheader()
    for act in c['acts']:
        for path, row in sorted(act.get('_image_inventory', {}).items()):
            if path in first:
                writer.writerow({**row, 'first_commit': first[path]})
    return buf.getvalue()


def check(c, records, read_blob=None):
    errors, warnings = [], []
    referenced = set()
    for act in c['acts']:
        for version in act['versions']:
            candidates = [r for r in records if r['day'] == version['from']
                          and any(p.startswith(act['slug'] + '/') for p in r['files'])]
            new = any(r.get('standard') == '1' for r in candidates)
            output = errors if new else warnings
            required = c.get('country', {}).get('image_inventory_required', False)
            if 'source_images' not in version and not required:
                warnings.append(f'{act["slug"]} {version["from"]}: source_images not surveyed; '
                                'image completeness is unknown')
            output.extend(issues(act, version, require_inventory=required))
            for unit in version.get('units', {}).values():
                for link in LINK.finditer(unit['text']):
                    path = act['slug'] + '/' + link[2]
                    referenced.add(path)
                    if read_blob and candidates:
                        raw = read_blob(candidates[-1]['commit'] + ':' + path)
                        if raw is None or hashlib.sha256(raw).hexdigest() != link[3]:
                            output.append(f'{path}: stored image missing or not byte-exact')
    stored = {p for r in records for p in r.get('all_files', []) if '/assets/' in p}
    warnings.extend(f'{p}: no provision in the input history references this image' for p in sorted(stored - referenced))
    return {'errors': errors, 'warnings': warnings}
